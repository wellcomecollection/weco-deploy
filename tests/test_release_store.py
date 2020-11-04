import abc
import secrets

import moto

from deploy.release_store import DynamoReleaseStore, MemoryReleaseStore


class ReleaseStoreTestsMixin:
    @abc.abstractmethod
    def create_release_store(self):
        pass

    def test_description(self):
        release_store = self.create_release_store()
        description = release_store.describe_initialisation()
        assert isinstance(description, str)
        assert len(description) > 0


class TestMemoryReleaseStore(ReleaseStoreTestsMixin):
    def create_release_store(self):
        return MemoryReleaseStore()


class TestDynamoReleaseStore(ReleaseStoreTestsMixin):
    @moto.mock_iam()
    @moto.mock_sts()
    @moto.mock_dynamodb()
    def create_release_store(self):
        return DynamoReleaseStore(
            project_id=f"test_project-{secrets.token_hex()}",
            region_name="eu-west-1",
            role_arn="arn:aws:iam::0123456789:role/example_role"
        )
