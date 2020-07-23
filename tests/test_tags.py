import pytest

from deploy.tags import parse_aws_tags


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
