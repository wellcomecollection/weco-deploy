import typing

import attr
import cattr
import yaml

from .iterators import convert_identified_list_to_dict


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
    services: typing.List[Service] = attr.ib(
        factory=list, converter=convert_identified_list_to_dict
    )


@attr.s
class Project:
    name = attr.ib()
    role_arn = attr.ib()

    environments: typing.List[Environment] = attr.ib(
        factory=list, converter=convert_identified_list_to_dict
    )
    image_repositories: typing.List[ImageRepository] = attr.ib(
        factory=list, converter=convert_identified_list_to_dict
    )

    aws_region_name = attr.ib(default="eu-west-1")

    @property
    def region_name(self):
        return self.aws_region_name


class ProjectList:
    @classmethod
    def from_text(cls, yaml_text):
        data = yaml.safe_load(yaml_text)
        return cattr.structure(data, typing.Dict[str, Project])

    @classmethod
    def from_path(cls, path):
        with open(path) as infile:
            yaml_text = infile.read()
        return ProjectList.from_text(yaml_text=yaml_text)
