import abc
import contextlib
import datetime
import secrets

from botocore.exceptions import ParamValidationError
import moto
import pytest

from deploy.release_store import DynamoReleaseStore, MemoryReleaseStore, ReleaseNotFoundError


@pytest.fixture
def project_id():
    return f"project-{secrets.token_hex()}"


class ReleaseStoreTestsMixin:
    @abc.abstractmethod
    @contextlib.contextmanager
    def create_release_store(self, project_id):
        pass

    def test_description(self, project_id):
        with self.create_release_store(project_id) as release_store:
            description = release_store.describe_initialisation()
            assert isinstance(description, str)
            assert len(description) > 0

    def test_can_initialise(self, project_id):
        with self.create_release_store(project_id) as release_store:
            release_store.initialise()

            # Calling initialise() a second time should have no effect
            release_store.initialise()

    def test_can_put_and_get_a_release(self, project_id):
        release = {
            "release_id": f"release-{secrets.token_hex()}",
            "project_id": project_id,
            "date_created": datetime.datetime.now().isoformat(),
            "last_date_deployed": datetime.datetime.now().isoformat()
        }

        with self.create_release_store(project_id) as release_store:
            release_store.initialise()

            assert release_store.put_release(release) is None
            assert release_store.get_release(release["release_id"]) == release

    def test_cannot_get_a_nonexistent_release(self, project_id):
        with self.create_release_store(project_id) as release_store:
            release_store.initialise()

            release_id = f"release-{secrets.token_hex()}"
            with pytest.raises(ReleaseNotFoundError, match=release_id):
                release_store.get_release(release_id)

    def test_can_get_recent_releases(self, project_id):
        releases = [
            {
                "release_id": f"release-{i}",
                "project_id": project_id,
                "date_created": datetime.datetime(2001, 1, i).isoformat(),
                "last_date_deployed": datetime.datetime.now().isoformat()
            }
            for i in range(1, 10)
        ]

        with self.create_release_store(project_id) as release_store:
            release_store.initialise()

            for r in releases:
                release_store.put_release(r)

            assert release_store.get_recent_releases(limit=3) == [
                releases[-1], releases[-2], releases[-3]
            ]

            assert release_store.get_recent_releases(limit=5) == [
                releases[-1], releases[-2], releases[-3], releases[-4], releases[-5]
            ]

            assert release_store.get_most_recent_release() == releases[-1]

    def test_get_most_recent_release_if_no_releases_is_error(self, project_id):
        with self.create_release_store(project_id) as release_store:
            release_store.initialise()

            with pytest.raises(ReleaseNotFoundError, match="There are no releases yet"):
                release_store.get_most_recent_release()

    def test_gets_recent_deployments(self, project_id):
        with self.create_release_store(project_id) as release_store:
            release_store.initialise()

            releases = [
                {
                    "release_id": f"release-{secrets.token_hex()}",
                    "project_id": project_id,
                    "date_created": datetime.datetime.now().isoformat(),
                    "last_date_deployed": datetime.datetime.now().isoformat(),
                    "deployments": [
                        {"id": "1", "date_created": datetime.datetime(2001, 1, 1).isoformat(), "environment": "prod"},
                        {"id": "2", "date_created": datetime.datetime(2001, 1, 2).isoformat(), "environment": "prod"},
                        {"id": "3", "date_created": datetime.datetime(2001, 1, 3).isoformat(), "environment": "staging"},
                        {"id": "4", "date_created": datetime.datetime(2001, 1, 4).isoformat(), "environment": "prod"},
                        {"id": "5", "date_created": datetime.datetime(2001, 1, 5).isoformat(), "environment": "staging"},
                    ]
                },
                {
                    "release_id": f"release-{secrets.token_hex()}",
                    "project_id": project_id,
                    "date_created": datetime.datetime.now().isoformat(),
                    "last_date_deployed": datetime.datetime.now().isoformat(),
                    "deployments": [
                        {"id": "6", "date_created": datetime.datetime(2001, 1, 6).isoformat(), "environment": "prod"},
                        {"id": "7", "date_created": datetime.datetime(2001, 1, 7).isoformat(), "environment": "prod"},
                        {"id": "8", "date_created": datetime.datetime(2001, 1, 8).isoformat(), "environment": "staging"},
                        {"id": "9", "date_created": datetime.datetime(2001, 1, 9).isoformat(), "environment": "prod"},
                        {"id": "10", "date_created": datetime.datetime(2001, 1, 10).isoformat(), "environment": "staging"},
                    ]
                },
            ]

            for r in releases:
                release_store.put_release(r)

            resp = release_store.get_recent_deployments(limit=0)
            assert resp == []

            resp = release_store.get_recent_deployments(limit=4)
            assert [d["id"] for d in resp] == ["10", "9", "8", "7"]

            resp = release_store.get_recent_deployments(limit=6)
            assert [d["id"] for d in resp] == ["10", "9", "8", "7", "6", "5"]

            resp = release_store.get_recent_deployments(environment="staging")
            assert [d["id"] for d in resp] == ["10", "8", "5", "3"]

            resp = release_store.get_recent_deployments(environment="staging", limit=4)
            assert [d["id"] for d in resp] == ["10", "8", "5", "3"]

            resp = release_store.get_recent_deployments(environment="prod", limit=1)
            assert [d["id"] for d in resp] == ["9"]

    def test_can_add_deployment(self, project_id):
        release = {
            "release_id": f"release-{secrets.token_hex()}",
            "project_id": project_id,
            "date_created": datetime.datetime.now().isoformat(),
            "last_date_deployed": datetime.datetime(2001, 1, 1).isoformat(),
            "deployments": []
        }

        with self.create_release_store(project_id) as release_store:
            release_store.initialise()
            release_store.put_release(release)

            deployment = {
                "id": "1",
                "environment": "prod",
                "date_created": datetime.datetime.now().isoformat()
            }

            release_store.add_deployment(
                release_id=release["release_id"],
                deployment=deployment
            )

            stored_release = release_store.get_release(release["release_id"])
            assert stored_release["deployments"] == [deployment]
            assert stored_release["last_date_deployed"] == deployment["date_created"]

    def test_adding_deployment_preserves_existing_deployments(self, project_id):
        release = {
            "release_id": f"release-{secrets.token_hex()}",
            "project_id": project_id,
            "date_created": datetime.datetime.now().isoformat(),
            "last_date_deployed": datetime.datetime(2001, 1, 1).isoformat(),
            "deployments": [
                {"id": "1", "environment": "prod"},
                {"id": "2", "environment": "staging"},
                {"id": "3", "environment": "prod"},
            ]
        }

        with self.create_release_store(project_id) as release_store:
            release_store.initialise()
            release_store.put_release(release)

            deployment = {
                "id": "4",
                "environment": "prod",
                "date_created": datetime.datetime.now().isoformat()
            }

            release_store.add_deployment(
                release_id=release["release_id"],
                deployment=deployment
            )

            stored_release = release_store.get_release(release["release_id"])
            assert len(stored_release["deployments"]) == 4
            assert stored_release["last_date_deployed"] == deployment["date_created"]


class TestMemoryReleaseStore(ReleaseStoreTestsMixin):
    @contextlib.contextmanager
    def create_release_store(self, project_id):
        yield MemoryReleaseStore()


class TestDynamoReleaseStore(ReleaseStoreTestsMixin):
    @contextlib.contextmanager
    def create_release_store(self, project_id):
        with moto.mock_dynamodb2(), moto.mock_sts(), moto.mock_iam():
            yield DynamoReleaseStore(
                project_id=project_id,
                region_name="eu-west-1",
                role_arn="arn:aws:iam::0123456789:role/example_role"
            )

    def test_unexpected_error_at_initialisation_is_raised(self, project_id):
        with self.create_release_store(project_id) as release_store:
            release_store.table = release_store.dynamodb.Table("")

            # DynamoDB tables should have non-empty length.  Trying to initialise
            # a table whose name is the empty string will fail.
            with pytest.raises(ParamValidationError):
                release_store.initialise()
