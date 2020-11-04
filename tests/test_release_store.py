import abc
import contextlib
import secrets

from botocore.exceptions import ParamValidationError
import moto
import pytest

from deploy.release_store import DynamoReleaseStore, MemoryReleaseStore


class ReleaseStoreTestsMixin:
    @abc.abstractmethod
    @contextlib.contextmanager
    def create_release_store(self):
        pass

    def test_description(self):
        with self.create_release_store() as release_store:
            description = release_store.describe_initialisation()
            assert isinstance(description, str)
            assert len(description) > 0

    def test_can_initialise(self):
        with self.create_release_store() as release_store:
            release_store.initialise()

            # Calling initialise() a second time should have no effect
            release_store.initialise()


class TestMemoryReleaseStore(ReleaseStoreTestsMixin):
    @contextlib.contextmanager
    def create_release_store(self):
        yield MemoryReleaseStore()


class TestDynamoReleaseStore(ReleaseStoreTestsMixin):
    @contextlib.contextmanager
    def create_release_store(self):
        with moto.mock_dynamodb2(), moto.mock_sts(), moto.mock_iam():
            yield DynamoReleaseStore(
                project_id=f"test_project-{secrets.token_hex()}",
                region_name="eu-west-1",
                role_arn="arn:aws:iam::0123456789:role/example_role"
            )

    def test_unexpected_error_at_initialisation_is_raised(self):
        with self.create_release_store() as release_store:
            release_store.table = release_store.dynamodb.Table("")

            # DynamoDB tables should have non-empty length.  Trying to initialise
            # a table whose name is the empty string will fail.
            with pytest.raises(ParamValidationError):
                release_store.initialise()
