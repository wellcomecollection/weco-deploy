import abc

from boto3.dynamodb.conditions import Key

from . import iam
from .exceptions import WecoDeployError


class ReleaseStoreError(WecoDeployError):
    pass


class ReleaseNotFoundError(ReleaseStoreError):
    """
    Raised if a release store is asked to retrieve a release ID which does not exist.
    """

    pass


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

    @abc.abstractmethod
    def put_release(self, release):
        """
        Store a new release.  Returns None.
        """
        pass

    @abc.abstractmethod
    def get_release(self, release_id):
        """
        Retrieve a previously stored release.
        """
        pass

    @abc.abstractmethod
    def get_recent_releases(self, *, limit):
        """
        Return the most recent ``limit`` releases, as sorted by creation date.
        """
        pass

    def get_most_recent_release(self):
        """
        Return the most recent release, as sorted by creation date.
        """
        try:
            return self.get_recent_releases(limit=1)[0]
        except IndexError:
            raise ReleaseNotFoundError("There are no releases yet")

    @abc.abstractmethod
    def get_recent_deployments(self, *, environment=None, limit=10):
        """
        Return the most recent ``limit`` deployments in a given environment.
        """
        pass

    @abc.abstractmethod
    def add_deployment(self, *, release_id, deployment):
        """
        Store a new deployment.
        """
        pass


class MemoryReleaseStore(ReleaseStore):
    def __init__(self):
        self.cache = {}

    def describe_initialisation(self):
        return "Create in-memory release store"

    def initialise(self):
        pass

    def put_release(self, release):
        self.cache[release["release_id"]] = release

    def get_release(self, release_id):
        try:
            return self.cache[release_id]
        except KeyError:
            raise ReleaseNotFoundError(release_id)

    def get_recent_releases(self, *, limit):
        sorted_releases = sorted(
            self.cache.values(),
            key=lambda c: c["date_created"],
            reverse=True
        )
        return sorted_releases[:limit]

    def get_recent_deployments(self, *, environment=None, limit=10):
        deployments = []

        for release in self.cache.values():
            deployments.extend(release["deployments"])

        if environment:
            deployments = [d for d in deployments if d["environment"] == environment]

        return sorted(
            deployments,
            key=lambda d: d["date_created"],
            reverse=True
        )[:limit]

    def add_deployment(self, *, release_id, deployment):
        self.cache[release_id]["deployments"].append(deployment)
        self.cache[release_id]["last_date_deployed"] = deployment["date_created"]


class DynamoReleaseStore(ReleaseStore):
    def __init__(self, project_id, region_name, role_arn):
        self.project_id = project_id
        session = iam.get_session(
            session_name="ReleaseToolDynamoDbReleaseStore",
            role_arn=role_arn,
            region_name=region_name,
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

    def put_release(self, release):
        self.table.put_item(Item=release)

    def get_release(self, release_id):
        resp = self.table.get_item(Key={"release_id": release_id})
        try:
            return resp["Item"]
        except KeyError:
            raise ReleaseNotFoundError(release_id)

    def get_recent_releases(self, *, limit):
        # The GSI project_gsi uses date_created as a range key, so we can
        # sort by the contents of this column.
        query_resp = self.table.query(
            IndexName="project_gsi",
            ScanIndexForward=False,
            Limit=limit,
            # Note: as far as I know, this expression is a no-op -- everything
            # in a given table will have the same release ID.  We need to have
            # a KeyConditionExpression for a Query to work, and we need a Query
            # to get the sorting.
            KeyConditionExpression=Key("project_id").eq(self.project_id),
        )

        return query_resp["Items"]

    def get_recent_deployments(self, *, environment=None, limit=10):
        known_deployments = []

        params = {
            "IndexName": "deployment_gsi",
            "KeyConditionExpression": Key("project_id").eq(self.project_id),
            # Query results are always sorted by the sort key value.  Setting
            # this parameter to False means they are returned in descending order,
            # i.e. newer deployments come first.
            #
            # The sort key on this GSI is last_date_deployed.
            "ScanIndexForward": False,
        }

        items_seen = 0

        while len(known_deployments) < limit or items_seen < limit:
            resp = self.table.query(**params)

            for release in resp["Items"]:
                for deployment in release["deployments"]:
                    deployment["release_id"] = release["release_id"]

                    # Filter on environment_id - this does not play well with filter
                    # resulting in fewer than expected items (this filters on top of
                    # the limit) but it's hard to do better with the data structured
                    # as it is.
                    if environment and deployment["environment"] == environment:
                        known_deployments.append(deployment)
                    elif environment is None:
                        known_deployments.append(deployment)

            items_seen += len(resp["Items"])

            try:
                params["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
            except KeyError:
                break

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

    def add_deployment(self, *, release_id, deployment):
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
