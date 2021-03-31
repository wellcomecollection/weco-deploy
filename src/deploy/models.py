import typing

import attr
import cattr
import yaml


@attr.s
class Environment:
    id = attr.ib()
    name = attr.ib()


@attr.s
class Service:
    id = attr.ib()


@attr.s
class ImageRepository:
    id = attr.ib()
    services: typing.List[Service] = attr.ib(factory=list)


@attr.s
class Project:
    environments: typing.List[Environment] = attr.ib()
    image_repositories: typing.List[ImageRepository] = attr.ib()
    name = attr.ib()
    role_arn = attr.ib()

    account_id = attr.ib(default=None, type=str)
    aws_region_name = attr.ib(default="eu-west-1")


@attr.s
class ProjectList:
    projects: typing.Dict[str, Project] = attr.ib()

    @classmethod
    def from_text(cls, yaml_text):
        data = yaml.safe_load(yaml_text)
        return ProjectList(
            projects=cattr.structure(data, typing.Dict[str, Project])
        )

    @classmethod
    def from_path(cls, path):
        with open(path) as infile:
            yaml_text = infile.read()
        return ProjectList.from_text(yaml_text=yaml_text)
