from deploy.models import Environment, ImageRepository, ProjectList, Project, Service

example_wellcome_project = """
calm_adapter:
  environments:
    - id: prod
      name: Production
  image_repositories:
    - id: calm_adapter
      services:
        - id: calm-adapter
    - id: calm_deletion_checker
  name: Calm Adapter
  role_arn: arn:aws:iam::123456789012:role/platform-ci
  account_id: 123456789012
  aws_region_name: us-east-1

sierra_adapter:
  environments:
    - id: prod
      name: Production
    - id: staging
      name: Staging
  image_repositories:
    - id: sierra_merger
      services:
        - id: bibs-merger
        - id: items-merger
        - id: holdings-merger
  name: Sierra Adapter
  role_arn: arn:aws:iam::760097843905:role/platform-ci
"""


def test_from_path(tmpdir):
    calm_adapter = Project(
        environments=[
            Environment(id="prod", name="Production"),
        ],
        image_repositories=[
            ImageRepository(
                id="calm_adapter",
                services=[Service(id="calm-adapter")]
            ),
            ImageRepository(
                id="calm_deletion_checker",
                services=[]
            )
        ],
        name="Calm Adapter",
        role_arn="arn:aws:iam::123456789012:role/platform-ci",
        account_id="123456789012",
        aws_region_name="us-east-1"
    )

    sierra_adapter = Project(
        environments=[
            Environment(id="prod", name="Production"),
            Environment(id="staging", name="Staging"),
        ],
        image_repositories=[
            ImageRepository(
                id="sierra_merger",
                services=[
                    Service(id="bibs-merger"),
                    Service(id="items-merger"),
                    Service(id="holdings-merger"),
                ]
            )
        ],
        name="Sierra Adapter",
        role_arn="arn:aws:iam::760097843905:role/platform-ci",
        # These are the default values
        account_id=None,
        aws_region_name="eu-west-1"
    )

    yaml_path = tmpdir / ".wellcome_project"
    yaml_path.write(example_wellcome_project)

    project_list = ProjectList.from_path(yaml_path)

    assert project_list == ProjectList(
        projects={
            "calm_adapter": calm_adapter,
            "sierra_adapter": sierra_adapter,
        }
    )
