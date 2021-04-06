import collections
import typing

import attr
import cattr
import yaml

from .exceptions import ConfigError


def _convert_identified_list_to_dict(values):
    """
    Given a list of objects with a .id parameter, convert them to a dict
    keyed with the .id.
    """
    id_counts = collections.Counter(v.id for v in values)
    duplicate_ids = {id for id, count in id_counts.items() if count > 1}
    if duplicate_ids:
        raise ConfigError("Duplicate IDs: %s" % ", ".join(duplicate_ids))

    return {v.id: v for v in values}


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
        factory=list, converter=_convert_identified_list_to_dict
    )


@attr.s
class Project:
    environments: typing.List[Environment] = attr.ib(
        converter=_convert_identified_list_to_dict
    )
    image_repositories: typing.List[ImageRepository] = attr.ib(
        converter=_convert_identified_list_to_dict
    )
    name = attr.ib()
    role_arn = attr.ib()

    account_id = attr.ib(default=None, type=str)
    aws_region_name = attr.ib(default="eu-west-1")


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
