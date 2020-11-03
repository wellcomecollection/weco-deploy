import pytest

from deploy.tags import (
    find_unique_resource_matching_tags,
    parse_aws_tags,
    MultipleMatchingResourcesError,
    NoMatchingResourceError,
)


@pytest.mark.parametrize(
    "aws_tags, expected_tags",
    [
        ([], {}),
        (
            [
                {"key": "deployment:env", "value": "prod"},
                {"key": "deployment:service", "value": "bag-unpacker"},
            ],
            {"deployment:env": "prod", "deployment:service": "bag-unpacker"},
        ),
    ],
)
def test_parse_aws_tags(aws_tags, expected_tags):
    assert parse_aws_tags(aws_tags) == expected_tags


class TestFindUniqueResourceMatchingTags:
    def test_finds_unique_matching_resource(self):
        """
        find_unique_resource_matching_tags finds a resource with a single matching tag.
        """
        resources = [
            {"name": "bag-unpacker", "tags": [{"key": "name", "value": "unpacker"}]},
            {"name": "bag-verifier", "tags": [{"key": "name", "value": "verifier"}]},
            {"name": "app-untagged"},
        ]

        match = find_unique_resource_matching_tags(
            resources, expected_tags={"name": "unpacker"}
        )

        assert match == resources[0]

    def test_matching_on_multiple_tags(self):
        """
        find_unique_resource_matching_tags can match on multiple tags, including
        a subset of the available tags.
        """
        resources = [
            {
                "name": "app-prod",
                "tags": [
                    {"key": "name", "value": "app"},
                    {"key": "env", "value": "prod"},
                    {"key": "ref", "value": "git.123"},
                ],
            },
            {
                "name": "app-stage",
                "tags": [
                    {"key": "name", "value": "app"},
                    {"key": "env", "value": "stage"},
                    {"key": "ref", "value": "git.123"},
                ],
            },
            {"name": "app-untagged"},
        ]

        match = find_unique_resource_matching_tags(
            resources, expected_tags={"name": "app", "env": "prod"}
        )

        assert match == resources[0]

    def test_empty_tags_is_error(self):
        """
        Trying to match on an empty set of tags is an error.
        """
        resources = [{"name": "app", "tags": [{"key": "env", "value": "prod"}]}]

        with pytest.raises(
            ValueError, match="Cannot match against an empty set of tags"
        ):
            find_unique_resource_matching_tags(resources, expected_tags={})

    def test_multiple_matching_resources_is_error(self):
        """
        If there are multiple resources with the expected tags, an error is thrown.
        """
        resources = [
            {
                "name": "app-prod",
                "tags": [
                    {"key": "name", "value": "app"},
                    {"key": "env", "value": "prod"},
                ],
            },
            {
                "name": "app-stage",
                "tags": [
                    {"key": "name", "value": "app"},
                    {"key": "env", "value": "stage"},
                ],
            },
        ]

        with pytest.raises(MultipleMatchingResourcesError):
            find_unique_resource_matching_tags(resources, expected_tags={"name": "app"})

    def test_no_matching_resources_is_error(self):
        """
        If there are no resources with the expected tags, an error is thrown.
        """
        resources = [
            {
                "name": "app-prod",
                "tags": [
                    {"key": "name", "value": "app"},
                    {"key": "env", "value": "prod"},
                ],
            },
            {
                "name": "app-stage",
                "tags": [
                    {"key": "name", "value": "app"},
                    {"key": "env", "value": "stage"},
                ],
            },
        ]

        with pytest.raises(NoMatchingResourceError):
            find_unique_resource_matching_tags(
                resources, expected_tags={"name": "worker"}
            )
