import pytest

from deploy.exceptions import ConfigError
from deploy.project import Projects, Project


def test_loading_non_existent_project_is_runtimeerror(tmpdir):
    project_filepath = str(tmpdir / ".wellcome_project")

    with open(project_filepath, "w") as outfile:
        outfile.write("test_project: true")

    project = Projects(project_filepath)

    with pytest.raises(ConfigError, match="No matching project doesnotexist"):
        project.load(project_id="doesnotexist")


def test_no_role_arn_is_error():
    with pytest.raises(ConfigError, match="role_arn is not set!"):
        Project(
            project_id="my_project",
            config={}
        )
