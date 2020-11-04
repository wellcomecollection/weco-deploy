import abc

from . import iam


class ReleaseStore(abc.ABC):
    @abc.abstractmethod
    def describe_initialisation(self):
        pass


class MemoryReleaseStore(ReleaseStore):
    def __init__(self):
        self.cache = {}

    def describe_initialisation(self):
        return "Create in-memory release store"


class DynamoReleaseStore(ReleaseStore):
    def __init__(self, project_id, region_name, role_arn):
        self.project_id = project_id
        self.table_name = f"wellcome-releases-{project_id}"
        session = iam.get_session(
            session_name="ReleaseToolDynamoDbReleaseStore",
            role_arn=role_arn,
            region_name=region_name
        )
        self.dynamo_db = session.resource("dynamodb")
        self.table = self.dynamo_db.Table(self.table_name)

    def describe_initialisation(self):
        return f"Create DynamoDB table {self.table_name}"
