from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key

from .iam import Iam


class DynamoDbReleaseStore:
    def __init__(self, project_id, region_name, role_arn):
        self.project_id = project_id
        self.table_name = f"wellcome-releases-{project_id}"
        self.session = Iam.get_session(
            session_name="ReleaseToolDynamoDbReleaseStore",
            role_arn=role_arn,
            region_name=region_name
        )
        self.dynamo_db = self.session.resource("dynamodb")
        self.table = self.dynamo_db.Table(self.table_name)

    def describe_initialisation(self):
        return f"Create DynamoDb table {self.table_name}"

    def initialise(self):
        try:
            self.table.table_status
        except ClientError as client_error:
            if client_error.response['Error']['Code'] == 'ResourceNotFoundException':
                self._create_table()
            else:
                raise (
                    f"Unknown exception occurred while querying for {self.table_name} {client_error.response}"
                )

    def put_release(self, release):
        self.table.put_item(Item=release)

        return release

    def get_latest_release(self):
        items = self.table.query(IndexName='project_gsi',
                                 KeyConditionExpression=Key('project_id').eq(self.project_id),
                                 ScanIndexForward=False,
                                 Limit=1)
        if items['Count'] == 1:
            return items['Items'][0]
        else:
            return None

    def get_latest_releases(self, limit=1):
        items = self.table.query(IndexName='project_gsi',
                                 KeyConditionExpression=Key('project_id').eq(self.project_id),
                                 ScanIndexForward=False,
                                 Limit=limit)
        return items['Items']

    def get_release(self, release_id):
        try:
            return self.table.get_item(Key={"release_id": release_id})["Item"]
        except KeyError:
            raise RuntimeError(f"No such release: {release_id}")

    def get_recent_deployments(self, limit=10):
        """
        Returns the N most recent deployments.
        """
        known_deployments = []

        resp = self.table.query(
            IndexName='deployment_gsi',
            KeyConditionExpression=Key('project_id').eq(self.project_id),
            Limit=limit,
            # Query results are always sorted by the sort key value.  Setting
            # this parameter to False means they are returned in descending order,
            # i.e. newer deployments come first.
            #
            # The sort key on this GSI is last_date_deployed.
            ScanIndexForward=False,
        )

        for release in resp["Items"]:
            for deployment in release["deployments"]:
                deployment["release_id"] = release["release_id"]
                known_deployments.append(deployment)

        known_deployments = sorted(
            known_deployments, key=lambda d: d["date_created"], reverse=True
        )

        # We then truncate the list to the limit, otherwise we might be
        # presenting an incomplete list of deployments.
        #
        # Consider:
        #
        #   - Release A
        #       deployed @ 1pm
        #       deployed @ 6pm
        #   - Release B
        #       deployed @ 2pm
        #   - Release C
        #       deployed @ 5pm
        #
        # If we requested limit=2, then DynamoDB would return the releases
        # with the two most recent "last_date_deployed" fields.  This would
        # present the following timeline:
        #
        #   - 1pm: Release A
        #   - 5pm: Release C
        #   - 6pm: Release A
        #
        # What happened to release B???
        #
        # We know we have the last N deployments with no gaps, but beyond
        # that we can't be sure.
        return known_deployments[:limit]

    def add_deployment(self, release_id, deployment, dry_run=False):
        if not dry_run:
            self.table.update_item(
                Key={
                    'release_id': release_id
                },
                UpdateExpression="SET #deployments = list_append(#deployments, :d)",
                ExpressionAttributeNames={
                    '#deployments': 'deployments',
                },
                ExpressionAttributeValues={
                    ':d': [deployment],
                }
            )

            self.table.update_item(
                Key={
                    'release_id': release_id
                },
                UpdateExpression="SET last_date_deployed = :d",
                ExpressionAttributeValues={
                    ':d': deployment['date_created'],
                }
            )

        return release_id

    def _create_table(self):
        self.dynamo_db.create_table(
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
