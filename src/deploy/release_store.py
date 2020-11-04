import abc

from botocore.exceptions import ClientError

from . import iam


class ReleaseStore(abc.ABC):
    @abc.abstractmethod
    def describe_initialisation(self):
        """
        Returns a human-readable string to describe the initialisation process.
        """
        pass

    @abc.abstractmethod
    def initialise(self):
        """
        Do any initialisation steps to make the store ready for use.
        """
        pass


class MemoryReleaseStore(ReleaseStore):
    def __init__(self):
        self.cache = {}

    def describe_initialisation(self):
        return "Create in-memory release store"

    def initialise(self):
        pass


class DynamoReleaseStore(ReleaseStore):
    def __init__(self, project_id, region_name, role_arn):
        self.project_id = project_id
        session = iam.get_session(
            session_name="ReleaseToolDynamoDbReleaseStore",
            role_arn=role_arn,
            region_name=region_name
        )
        self.dynamodb = session.resource("dynamodb")
        self.table = self.dynamodb.Table(f"wellcome-releases-{project_id}")

    @property
    def table_name(self):
        return self.table.name

    def describe_initialisation(self):
        return f"Create DynamoDB table {self.table_name}"

    def initialise(self):
        # Attempt to load the description of the table from DynamoDB.  If this
        # fails, we know the table doesn't exist yet and we should try to
        # create it.
        try:
            self.table.load()
        except self.dynamodb.meta.client.exceptions.ResourceNotFoundException:
            self._create_table()

    def _create_table(self):
        self.dynamodb.create_table(
            TableName=self.table_name,
            KeySchema=[
                {
                    'AttributeName': 'release_id',
                    'KeyType': 'HASH'
                }
            ],
            AttributeDefinitions=[
                {
                    'AttributeName': 'release_id',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'project_id',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'date_created',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'last_date_deployed',
                    'AttributeType': 'S'
                }
            ],
            GlobalSecondaryIndexes=[
                {
                    'IndexName': 'project_gsi',
                    'KeySchema': [
                        {
                            'AttributeName': 'project_id',
                            'KeyType': 'HASH'
                        },
                        {
                            'AttributeName': 'date_created',
                            'KeyType': 'RANGE'
                        },
                    ],
                    'Projection': {
                        'ProjectionType': 'ALL'
                    },
                    'ProvisionedThroughput': {
                        'ReadCapacityUnits': 1,
                        'WriteCapacityUnits': 1
                    }
                },
                {
                    'IndexName': 'deployment_gsi',
                    'KeySchema': [
                        {
                            'AttributeName': 'project_id',
                            'KeyType': 'HASH'
                        },
                        {
                            'AttributeName': 'last_date_deployed',
                            'KeyType': 'RANGE'
                        },
                    ],
                    'Projection': {
                        'ProjectionType': 'ALL'
                    },
                    'ProvisionedThroughput': {
                        'ReadCapacityUnits': 1,
                        'WriteCapacityUnits': 1
                    }
                }
            ],
            ProvisionedThroughput={
                'ReadCapacityUnits': 1,
                'WriteCapacityUnits': 1
            }
        )
