import datetime

import pytest

from deploy.exceptions import ConfigError
from deploy.models import Environment, ImageRepository, Service
from deploy.project import prepare_config, Projects, Project
from deploy.release_store import MemoryReleaseStore


def test_loading_non_existent_project_is_runtimeerror(tmpdir):
    project_filepath = str(tmpdir / ".wellcome_project")

    with open(project_filepath, "w") as outfile:
        outfile.write("test_project: true")

    project = Projects(project_filepath)

    with pytest.raises(ConfigError, match="No matching project doesnotexist"):
        project.load(project_id="doesnotexist")


class TestPrepareConfig:
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


class TestProject:
    def test_image_repositories(self, role_arn, project_id):
        config = {
            "image_repositories": [
                {
                    "id": "repo1",
                    "services": [{"id": "service1a"}, {"id": "service1b"}],
                    "region_name": "us-east-1",
                    "role_arn": "arn:aws:iam::1111111111:role/publisher-role"
                },
                {
                    "id": "repo2",
                    "services": [
                        {"id": "service2a"},
                        {"id": "service2b"},
                        {"id": "service2c"},
                    ]
                },
                {
                    "id": "repo3",
                    "services": [{"id": "service3a"}]
                }
            ],
            "role_arn": role_arn,
            "region_name": "eu-west-1",
            "name": "Example Project",
        }

        project = Project(
            project_id=project_id,
            config=config,
            release_store=MemoryReleaseStore()
        )

        assert project.image_repositories == {
            "repo1": ImageRepository(
                id="repo1",
                services=[
                    Service(id="service1a"),
                    Service(id="service1b"),
                ]
            ),
            "repo2": ImageRepository(
                id="repo2",
                services=[
                    Service(id="service2a"),
                    Service(id="service2b"),
                    Service(id="service2c"),
                ]
            ),
            "repo3": ImageRepository(
                id="repo3",
                services=[
                    Service(id="service3a")
                ]
            ),
        }

    def test_environment_names(self, role_arn, project_id):
        config = {
            "environments": [
                {"id": "stage", "name": "Staging"},
                {"id": "prod", "name": "Prod"},
            ],
            "role_arn": role_arn,
            "region_name": "eu-west-1",
            "name": "Example Project",
        }

        project = Project(
            project_id=project_id,
            config=config,
            release_store=MemoryReleaseStore()
        )

        assert project.environment_names == {
            "stage": Environment(id="stage", name="Staging"),
            "prod": Environment(id="prod", name="Prod"),
        }

    def test_prepare_no_release_available(self, role_arn, project_id):
        release_store = MemoryReleaseStore()

        config = {
            "image_repositories": [
                {
                    "id": "repo1",
                    "services": [{"id": "service1"}],
                    "region_name": "us-east-1",
                    "role_arn": "arn:aws:iam::1111111111:role/publisher-role"
                },
            ],
            "environments": [
                {"id": "stage", "name": "Staging"},
                {"id": "prod", "name": "Prod"},
            ],
            "role_arn": role_arn,
            "region_name": "eu-west-1",
            "name": "Example Project",
        }

        project = Project(
            project_id=project_id,
            config=config,
            release_store=release_store
        )

        get_images_return = {
            "foo": "abc"
        }

        def patch_get_images(label):
            return get_images_return

        # This is a poor way to test prepare as it relies on knowing the impl of get_images
        # The correct way to do this is to have a mocked `Ecr` and hand that in
        # TODO: Handle tests that interact with ECR by mocking it
        project.get_images = patch_get_images
        prepared_release = project.prepare("stage", "Some description")

        assert prepared_release["previous_release"] is None
        assert prepared_release["new_release"]["images"] == get_images_return
