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


def test_show_deployments(project_id, release_store, wellcome_project_file):
    releases = [
        {
            "release_id": "release-1",
            "project_id": project_id,
            "date_created": datetime.datetime(2001, 1, 1).isoformat(),
            "last_date_deployed": datetime.datetime.now().isoformat(),
            "deployments": [
                {
                    "release_id": "release-1",
                    "environment": "prod",
                    "date_created": datetime.datetime(2001, 1, 1).isoformat(),
                    "requested_by": "role/prod-ops",
                    "description": "No description provided",
                },
                {
                    "release_id": "release-1",
                    "environment": "staging",
                    "date_created": datetime.datetime(2001, 1, 2).isoformat(),
                    "requested_by": "role/staging-peeps",
                    "description": "Deploy release 1 to staging",
                },
            ]
        },
        {
            "release_id": "release-2",
            "project_id": project_id,
            "date_created": datetime.datetime(2002, 2, 1).isoformat(),
            "last_date_deployed": datetime.datetime.now().isoformat(),
            "deployments": [
                {
                    "release_id": "release-2",
                    "environment": "prod",
                    "date_created": datetime.datetime(2002, 2, 1).isoformat(),
                    "requested_by": "role/prod-ops",
                    "description": "No description provided",
                },
                {
                    "release_id": "release-2",
                    "environment": "prod",
                    "date_created": datetime.datetime(2002, 2, 2).isoformat(),
                    "requested_by": "role/prod-ops",
                    "description": "Redeploy to prod",
                },
                {
                    "release_id": "release-2",
                    "environment": "prod",
                    "date_created": datetime.datetime(2002, 2, 3).isoformat(),
                    "requested_by": "role/staging-peeps",
                    "description": "No description provided",
                },
            ]
        },
    ]

    for r in releases:
        release_store.put_release(r)

    runner = CliRunner()

    # Check that we can see a list of deployments
    result = runner.invoke(
        cli,
        ["--project-file", wellcome_project_file, "show-deployments"]
    )

    assert result.exit_code == 0, result.output
    assert len(result.output.splitlines()) == 7  # 2 header + 5 deployments
    assert "No description provided" not in result.output

    # Check that we can see the deployments for a particular release
    result = runner.invoke(
        cli,
        ["--project-file", wellcome_project_file, "show-deployments", "release-1"]
    )

    assert result.exit_code == 0, result.output
    assert len(result.output.splitlines()) == 4  # 2 header + 2 deployments
    assert "release-2" not in result.output

    # Check that we can limit the number of deployments
    result = runner.invoke(
        cli,
        ["--project-file", wellcome_project_file, "show-deployments", "--limit=3"]
    )

    assert result.exit_code == 0, result.output
    assert len(result.output.splitlines()) == 5  # 2 header + 3 deployments

    # Check that we can filter by environment
    result = runner.invoke(
        cli,
        ["--project-file", wellcome_project_file, "show-deployments", "--environment-id=staging"]
    )

    assert result.exit_code == 0, result.output
    assert len(result.output.splitlines()) == 3  # 2 header + 1 deployment
