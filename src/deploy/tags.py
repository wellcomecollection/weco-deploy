def parse_aws_tags(tags):
    """
    When you get the tags on an AWS resource from the API, they are in the form

        [{"key": "KEY1", "value": "VALUE1"},
         {"key": "KEY2", "value": "VALUE2"},
         ...]

    This function converts them into a Python-style dict().

    """
    result = {}

    for aws_tag in tags:
        assert isinstance(aws_tag, dict)
        assert aws_tag.keys() == {"key", "value"}

        assert aws_tag["key"] not in result, f"Duplicate key in tags: {aws_tag['key']}"

        result[aws_tag["key"]] = aws_tag["value"]

    return result
