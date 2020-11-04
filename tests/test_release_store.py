import abc
import contextlib
import datetime
import secrets
import uuid

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

            assert release_store.get_recent_releases(count=3) == [
                releases[-1], releases[-2], releases[-3]
            ]

            assert release_store.get_recent_releases(count=5) == [
                releases[-1], releases[-2], releases[-3], releases[-4], releases[-5]
            ]

            assert release_store.get_most_recent_release() == releases[-1]

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
                        {"id": "1", "environment": "prod",    "date_created": datetime.datetime(2001, 1, 1).isoformat()},
                        {"id": "2", "environment": "prod",    "date_created": datetime.datetime(2001, 1, 2).isoformat()},
                        {"id": "3", "environment": "staging", "date_created": datetime.datetime(2001, 1, 3).isoformat()},
                        {"id": "4", "environment": "prod",    "date_created": datetime.datetime(2001, 1, 4).isoformat()},
                        {"id": "5", "environment": "staging", "date_created": datetime.datetime(2001, 1, 5).isoformat()},
                    ]
                },
                {
                    "release_id": f"release-{secrets.token_hex()}",
                    "project_id": project_id,
                    "date_created": datetime.datetime.now().isoformat(),
                    "last_date_deployed": datetime.datetime.now().isoformat(),
                    "deployments": [
                        {"id": "6", "environment": "prod",     "date_created": datetime.datetime(2001, 1, 6).isoformat()},
                        {"id": "7", "environment": "prod",     "date_created": datetime.datetime(2001, 1, 7).isoformat()},
                        {"id": "8", "environment": "staging",  "date_created": datetime.datetime(2001, 1, 8).isoformat()},
                        {"id": "9", "environment": "prod",     "date_created": datetime.datetime(2001, 1, 9).isoformat()},
                        {"id": "10", "environment": "staging", "date_created": datetime.datetime(2001, 1, 10).isoformat()},
                    ]
                },
            ]

            for r in releases:
                release_store.put_release(r)

            resp = release_store.get_recent_deployments(count=0)
            assert resp == []

            resp = release_store.get_recent_deployments(count=4)
            assert [d["id"] for d in resp] == ["10", "9", "8", "7"]

            resp = release_store.get_recent_deployments(count=6)
            assert [d["id"] for d in resp] == ["10", "9", "8", "7", "6", "5"]

            resp = release_store.get_recent_deployments(environment="staging")
            assert [d["id"] for d in resp] == ["10", "8", "5", "3"]

            resp = release_store.get_recent_deployments(environment="staging", count=4)
            assert [d["id"] for d in resp] == ["10", "8", "5", "3"]

            resp = release_store.get_recent_deployments(count=1, environment="prod")
            assert [d["id"] for d in resp] == ["9"]


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
