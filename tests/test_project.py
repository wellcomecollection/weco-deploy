import pytest

from deploy.project import Projects


def test_loading_non_existent_project_is_runtimeerror(tmpdir):
    project_filepath = str(tmpdir / ".wellcome_project")

    with open(project_filepath, "w") as outfile:
        outfile.write("test_project: true")

    project = Projects(project_filepath)

    with pytest.raises(RuntimeError, match="No matching project doesnotexist"):
        project.load(project_id="doesnotexist")
