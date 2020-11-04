from .release_store import DynamoReleaseStore


class DynamoDbReleaseStore:
    def __init__(self, project_id, **kwargs):
        self._underlying = DynamoReleaseStore(project_id, **kwargs)

    def describe_initialisation(self):
        return self._underlying.describe_initialisation()
        return f"Create DynamoDb table {self.table_name}"

    def initialise(self):
        return self._underlying.initialise()

    def put_release(self, release):
        return self._underlying.put_release()

    def get_latest_release(self):
        return self._underlying.get_most_recent_release()

    def get_latest_releases(self, limit=1):
        return self._underlying.get_recent_releases(count=limit)

    def get_release(self, release_id):
        return self._underlying.get_release(release_id=release_id)

    def get_recent_deployments(self, environment_id=None, limit=10):
        """
        Returns the N most recent deployments.
        """
        return self._underlying.get_recent_deployments(
            environment=environment_id, count=limit
        )

    def add_deployment(self, release_id, deployment, dry_run=False):
        if not dry_run:
            return self._underlying.add_deployment(
                release_id=release_id, deployment=deployment
            )
