import datetime
import json
import textwrap

from click.testing import CliRunner
import moto
import pytest

from deploy.deploy import cli
from deploy.release_store import DynamoReleaseStore


@pytest.fixture
def wellcome_project_file(tmpdir, project_id, role_arn):
    with open(tmpdir / ".wellcome_project", "w") as outfile:
        outfile.write(textwrap.dedent(f"""\
            {project_id}:
              environments:
                - id: stage
                  name: Staging
                - id: prod
                  name: Prod
              image_repositories:
                - id: repo1
                  services:
                  - service1a
                  - service1b
                - id: repo2
                  services:
                  - service2a
              name: My project
              role_arn: {role_arn}
            """))

    return str(tmpdir / ".wellcome_project")


@moto.mock_dynamodb2()
@moto.mock_sts()
@moto.mock_iam()
@pytest.fixture
def release_store(project_id, region_name, role_arn):
    with moto.mock_dynamodb2(), moto.mock_sts(), moto.mock_iam():
        store = DynamoReleaseStore(
            project_id=project_id,
            region_name=region_name,
            role_arn=role_arn
        )
        store.initialise()
        yield store


def test_show_release(project_id, release_store, wellcome_project_file):
    releases = [
        {
            "release_id": f"release-{i}",
            "project_id": project_id,
            "date_created": datetime.datetime(2001, 1, i).isoformat(),
            "last_date_deployed": datetime.datetime.now().isoformat()
        }
        for i in range(1, 4)
    ]

    for r in releases:
        release_store.put_release(r)

    runner = CliRunner()

    # Check that if we don't supply an argument, we get the latest release.
    result = runner.invoke(
        cli,
        ["--project-file", wellcome_project_file, "show-release"]
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == releases[-1]

    # Now check that if we supply an argument, we get that release.
    result = runner.invoke(
        cli,
        ["--project-file", wellcome_project_file, "show-release", "release-1"]
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == releases[0]
