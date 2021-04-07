import pytest

from deploy.exceptions import ConfigError
from deploy.models import Environment, ImageRepository, Service
from deploy.project import Projects, Project
from deploy.release_store import MemoryReleaseStore


def test_loading_non_existent_project_is_runtimeerror(tmpdir):
    project_filepath = str(tmpdir / ".wellcome_project")

    with open(project_filepath, "w") as outfile:
        outfile.write("test_project: true")

    project = Projects(project_filepath)

    with pytest.raises(ConfigError, match="No matching project doesnotexist"):
        project.load(project_id="doesnotexist")


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
