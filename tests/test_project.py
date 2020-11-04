import secrets

import pytest

from deploy.exceptions import ConfigError
from deploy.project import prepare_config, Projects, Project


def test_loading_non_existent_project_is_runtimeerror(tmpdir):
    project_filepath = str(tmpdir / ".wellcome_project")

    with open(project_filepath, "w") as outfile:
        outfile.write("test_project: true")

    project = Projects(project_filepath)

    with pytest.raises(ConfigError, match="No matching project doesnotexist"):
        project.load(project_id="doesnotexist")


@pytest.fixture()
def role_arn():
    return f"arn:aws:iam::1234567890:role/role-{secrets.token_hex()}"


class TestPrepareConfig:
    def test_uses_config_namespace(self, role_arn):
        """
        ProjectConfig uses the namespace in the initial config.
        """
        config = {"namespace": "edu.self", "role_arn": role_arn}
        prepare_config(config)
        assert config["namespace"] == "edu.self"

    def test_allows_overriding_namespace(self, role_arn):
        """
        If there is no namespace in the initial config, but an override namespace
        is supplied, that namespace is added to the config.
        """
        config = {"role_arn": role_arn}
        prepare_config(config, namespace="edu.self")
        assert config["namespace"] == "edu.self"

    def test_uses_default_namespace(self, role_arn):
        """
        If there is no namespace in the initial config, and no override is supplied,
        then the default namespace is added to the config.
        """
        config = {"role_arn": role_arn}
        prepare_config(config)
        assert config["namespace"] == "uk.ac.wellcome"

    def test_warns_if_namespace_conflict(self, role_arn):
        """
        If there is a namespace in the initial config, and a different override
        is supplied, then a warning is shown.
        """
        config = {"namespace": "edu.self", "role_arn": role_arn}
        with pytest.warns(UserWarning, match="Preferring override"):
            prepare_config(config, namespace="uk.ac.wellcome")

        assert config["namespace"] == "uk.ac.wellcome"

    def test_does_not_warn_if_namespace_match(self, role_arn):
        """
        If there is a namespace in the initial config, and it matches the override,
        then no warning is shown.
        """
        config = {"namespace": "edu.self", "role_arn": role_arn}

        with pytest.warns(None) as record:
            prepare_config(config, namespace="edu.self")

        assert len(record) == 0

    def test_allows_overriding_role_arn(self, role_arn):
        """
        If there is no role_arn in the initial config, but an override role_arn
        is supplied, that role_arn is added to the config.
        """
        config = {}
        prepare_config(config, role_arn=role_arn)
        assert config["role_arn"] == role_arn

    def test_warns_if_role_arn_conflict(self, role_arn):
        """
        If there is a role_arn in the initial config, and a differnet override
        is supplied, then a warning is shown.
        """
        config = {"role_arn": role_arn}

        with pytest.warns(UserWarning, match="Preferring override role_arn"):
            prepare_config(config, role_arn=role_arn + "_alt")

        assert config["role_arn"] == role_arn + "_alt"

    def test_does_not_warn_if_role_arn_match(self, role_arn):
        """
        If there is a role_arn in the initial config, and it matches the override,
        then no warning is shown.
        """
        config = {"role_arn": role_arn}

        with pytest.warns(None) as record:
            prepare_config(config, role_arn=role_arn)

        assert len(record) == 0

    def test_errors_if_no_role_arn(self, role_arn):
        """
        If there is no role_arn in the initial config or override, then an
        error is thrown.
        """
        with pytest.raises(ConfigError, match="role_arn is not set"):
            prepare_config(config={})

    def test_uses_config_region_name(self, role_arn):
        """
        ProjectConfig uses the region_name in the initial config.
        """
        config = {"region_name": "us-east-2", "role_arn": role_arn}
        prepare_config(config)
        assert config["region_name"] == "us-east-2"

    def test_allows_overriding_region_name(self, role_arn):
        """
        If there is no region_name in the initial config, but an override region_name
        is supplied, that region_name is added to the config.
        """
        config = {"role_arn": role_arn}
        prepare_config(config, region_name="eu-north-1")
        assert config["region_name"] == "eu-north-1"

    def test_uses_default_region_name(self, role_arn):
        """
        If there is no region_name in the initial config, and no override is supplied,
        then the default region_name is added to the config.
        """
        config = {"role_arn": role_arn}
        prepare_config(config)
        assert config["region_name"] == "eu-west-1"

    def test_warns_if_region_name_conflict(self, role_arn):
        """
        If there is a region_name in the initial config, and a different override
        is supplied, then a warning is shown.
        """
        config = {"region_name": "eu-west-1", "role_arn": role_arn}
        with pytest.warns(UserWarning, match="Preferring override"):
            prepare_config(config, region_name="us-east-1")

        assert config["region_name"] == "us-east-1"

    def test_does_not_warn_if_region_name_match(self, role_arn):
        """
        If there is a region_name in the initial config, and it matches the override,
        then no warning is shown.
        """
        config = {"region_name": "eu-west-1", "role_arn": role_arn}

        with pytest.warns(None) as record:
            prepare_config(config, region_name="eu-west-1")

        assert len(record) == 0

    def test_duplicate_image_repository_is_error(self, role_arn):
        """
        If the same ID appears twice in the list of image repositories, raise
        a ConfigError.
        """
        config = {
            "role_arn": role_arn,
            "image_repositories": [
                {"id": "worker1", "services": []},
                {"id": "worker1", "services": []},
                {"id": "worker2", "services": []},
            ]
        }

        with pytest.raises(
            ConfigError, match="Duplicate repo in image_repositories: worker1"
        ):
            prepare_config(config)

    def test_duplicate_image_repositories_are_error(self, role_arn):
        """
        If the same ID appears twice in the list of image repositories, raise
        a ConfigError.
        """
        config = {
            "role_arn": role_arn,
            "image_repositories": [
                {"id": "worker1", "services": []},
                {"id": "worker1", "services": []},
                {"id": "worker2", "services": []},
                {"id": "worker2", "services": []},
                {"id": "worker3", "services": []},
            ]
        }

        with pytest.raises(
            ConfigError, match="Duplicate repos in image_repositories: worker1, worker2"
        ):
            prepare_config(config)

    def test_does_not_warn_on_unique_image_repositories(self, role_arn):
        """
        If all the image repositories have unique IDs, no error is raised.
        """
        config = {
            "role_arn": role_arn,
            "image_repositories": [
                {"id": "worker1", "services": []},
                {"id": "worker2", "services": []},
                {"id": "worker3", "services": []},
            ]
        }

        prepare_config(config)
