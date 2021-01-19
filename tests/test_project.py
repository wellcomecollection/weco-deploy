import datetime

import pytest

from deploy.exceptions import ConfigError
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

    def test_duplicate_environment_is_error(self, role_arn):
        """
        If the same ID appears twice in the list of environments, raise a ConfigError.
        """
        config = {
            "role_arn": role_arn,
            "environments": [
                {"id": "stage", "name": "Staging"},
                {"id": "stage", "name": "Staging"},
                {"id": "prod", "name": "Prod"},
            ]
        }

        with pytest.raises(ConfigError, match="Duplicate environment in config: stage"):
            prepare_config(config)

    def test_duplicate_environments_are_error(self, role_arn):
        """
        If the same ID appears twice in the list of environments, raise a ConfigError.
        """
        config = {
            "role_arn": role_arn,
            "environments": [
                {"id": "stage", "name": "Staging"},
                {"id": "stage", "name": "Staging"},
                {"id": "prod", "name": "Prod"},
                {"id": "prod", "name": "Prod"},
                {"id": "dev", "name": "Dev"},
            ]
        }

        with pytest.raises(
            ConfigError, match="Duplicate environments in config: prod, stage"
        ):
            prepare_config(config)

    def test_does_not_warn_on_unique_environments(self, role_arn):
        """
        If all the environments have unique IDs, no error is raised.
        """
        config = {
            "role_arn": role_arn,
            "environments": [
                {"id": "stage", "name": "Staging"},
                {"id": "prod", "name": "Prod"},
                {"id": "dev", "name": "Dev"},
            ]
        }

        prepare_config(config)

    def test_uses_config_account_id(self):
        config = {
            "role_arn": "arn:aws:iam::1234567890:role/example-role",
            "account_id": "1234567890"
        }

        prepare_config(config)
        assert config["account_id"] == "1234567890"

    def test_allows_overriding_account_id(self):
        """
        If there is no account_id in the initial config, but an override account_id
        is supplied, that account_id is added to the config.
        """
        config = {"role_arn": "arn:aws:iam::1234567890:role/example-role"}
        prepare_config(config, account_id="1234567890")
        assert config["account_id"] == "1234567890"

    def test_warns_if_account_id_conflict(self):
        """
        If there is an account_id in the initial config, and a different override
        is supplied, then a warning is shown.
        """
        config = {
            "role_arn": "arn:aws:iam::1234567890:role/example-role",
            "account_id": "1111111111"
        }
        with pytest.warns(UserWarning, match="Preferring override account_id"):
            prepare_config(config, account_id="1234567890")

        assert config["account_id"] == "1234567890"

    def test_does_not_warn_if_account_id_match(self):
        """
        If there is an account_id in the initial config, and it matches the override,
        then no warning is shown.
        """
        config = {
            "role_arn": "arn:aws:iam::1234567890:role/example-role",
            "account_id": "1234567890"
        }

        with pytest.warns(None) as record:
            prepare_config(config, account_id="1234567890")

        assert len(record) == 0

    def test_warns_if_account_if_does_not_match_role_arn(self):
        """
        If the account_id does not match the role ARN, then a warning is shown.
        """
        config = {
            "role_arn": "arn:aws:iam::1234567890:role/example-role",
            "account_id": "1111111111"
        }
        with pytest.warns(
            UserWarning,
            match="Account ID 1111111111 does not match the role"
        ):
            prepare_config(config)

    def test_uses_account_id_from_role_if_none_specified(self):
        """
        If the account_id is not explicitly specified, the one in the role ARN is used.
        """
        config = {
            "role_arn": "arn:aws:iam::1234567890:role/example-role",
        }
        prepare_config(config)

        assert config["account_id"] == "1234567890"


class TestProject:
    def test_image_repositories(self, role_arn, project_id):
        config = {
            "image_repositories": [
                {
                    "id": "repo1",
                    "services": ["service1a", "service1b"],
                    "account_id": "1111111111",
                    "region_name": "us-east-1",
                    "namespace": "org.wellcome",
                    "role_arn": "arn:aws:iam::1111111111:role/publisher-role"
                },
                {
                    "id": "repo2",
                    "services": ["service2a", "service2b", "service2c"]
                },
                {
                    "id": "repo3",
                    "services": ["service3a"]
                }
            ],
            "role_arn": role_arn,
            "account_id": "1234567890",
            "namespace": "edu.self",
            "region_name": "eu-west-1",
        }

        project = Project(
            project_id=project_id,
            config=config,
            release_store=MemoryReleaseStore()
        )

        assert project.image_repositories == {
            "repo1": {
                "namespace": "org.wellcome",
                "services": ["service1a", "service1b"],
                "account_id": "1111111111",
                "region_name": "us-east-1",
                "role_arn": "arn:aws:iam::1111111111:role/publisher-role",
            },
            "repo2": {
                "namespace": "edu.self",
                "services": ["service2a", "service2b", "service2c"],
                "account_id": "1234567890",
                "region_name": "eu-west-1",
                "role_arn": role_arn,
            },
            "repo3": {
                "namespace": "edu.self",
                "services": ["service3a"],
                "account_id": "1234567890",
                "region_name": "eu-west-1",
                "role_arn": role_arn,
            },
        }

    def test_environment_names(self, role_arn, project_id):
        config = {
            "environments": [
                {"id": "stage", "name": "Staging"},
                {"id": "prod", "name": "Prod"},
            ],
            "role_arn": role_arn,
            "account_id": "1234567890",
            "namespace": "edu.self",
            "region_name": "eu-west-1",
        }

        project = Project(
            project_id=project_id,
            config=config,
            release_store=MemoryReleaseStore()
        )

        assert project.environment_names == {"stage": "Staging", "prod": "Prod"}

    def test_get_release(self, role_arn, project_id):
        releases = [
            {
                "release_id": f"release-{i}",
                "project_id": project_id,
                "date_created": datetime.datetime(2001, 1, i).isoformat(),
                "last_date_deployed": datetime.datetime.now().isoformat()
            }
            for i in range(1, 10)
        ]

        release_store = MemoryReleaseStore()

        for r in releases:
            release_store.put_release(r)

        project = Project(
            project_id=project_id,
            config={"role_arn": role_arn},
            release_store=release_store
        )

        assert project.get_release("latest") == releases[-1]

        for r in releases:
            assert project.get_release(release_id=r["release_id"]) == r

    def test_prepare_no_release_available(self, role_arn, project_id):
        release_store = MemoryReleaseStore()

        config = {
            "image_repositories": [
                {
                    "id": "repo1",
                    "services": ["service1"],
                    "account_id": "1111111111",
                    "region_name": "us-east-1",
                    "namespace": "org.wellcome",
                    "role_arn": "arn:aws:iam::1111111111:role/publisher-role"
                },
            ],
            "environments": [
                {"id": "stage", "name": "Staging"},
                {"id": "prod", "name": "Prod"},
            ],
            "role_arn": role_arn,
            "account_id": "1234567890",
            "namespace": "edu.self",
            "region_name": "eu-west-1",
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

        assert prepared_release["previous_release"] == None
        assert prepared_release["new_release"]["images"] == get_images_return
