from logging import Logger
from typing import Iterator

from pbench.server import PbenchServerConfig
from pbench.server.api.resources import (
    API_OPERATION,
    JSON,
    Schema,
    Parameter,
    ParamType,
)
from pbench.server.api.resources.query_apis import ElasticBulkBase
from pbench.server.database.models.datasets import Dataset, Metadata


class DatasetsPublish(ElasticBulkBase):
    """
    Change the "access" authorization of a Pbench dataset by modifying the
    "authorization": {"access": value} subdocument of each Elasticsearch
    document associated with the specified dataset.
    """

    def __init__(self, config: PbenchServerConfig, logger: Logger):
        super().__init__(
            config,
            logger,
            Schema(
                Parameter("name", ParamType.STRING, required=True),
                Parameter("access", ParamType.ACCESS, required=True),
            ),
            action="update",
            role=API_OPERATION.UPDATE,
        )

    def generate_actions(self, json_data: JSON, dataset: Dataset) -> Iterator[dict]:
        """
        Generate a series of Elasticsearch bulk update actions driven by the
        dataset document map.

        Args:
            json_data: Type-normalized client JSON input
                access: The desired access level of the dataset
            dataset: the Dataset object

        Returns:
            A generator for Elasticsearch bulk update actions
        """
        access = json_data["access"]
        map = Metadata.getvalue(dataset=dataset, key=Metadata.INDEX_MAP)

        self.logger.info("Starting publish operation for dataset {}", dataset)

        # Generate a series of bulk update documents, which will be passed to
        # the Elasticsearch bulk helper.
        #
        # Note that the "doc" specifies explicit instructions for updating only
        # the "access" field of the "authorization" subdocument: no other data
        # will be modified.

        for index, ids in map.items():
            for id in ids:
                yield {
                    "_op_type": self.action,
                    "_index": index,
                    "_id": id,
                    "doc": {"authorization": {"access": access}},
                }

    def complete(self, dataset: Dataset, json_data: JSON, summary: JSON) -> None:
        """
        Complete the publish operation by updating the access of the Dataset
        object.

        Note that an exception will be caught outside this class; the Dataset
        object will remain in the previous state to allow a retry.

        Args:
            dataset: Dataset object
            json_data: client JSON payload
                access: new dataset access setting
            summary: summary of the bulk operation
                ok: count of successful updates
                failure: count of failures
        """
        if summary["failure"] == 0:
            dataset.access = json_data["access"]
            dataset.update()
