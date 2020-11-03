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


class MultipleMatchingResourcesError(ValueError):
    """
    Raised if there are multiple resources matching a given set of tags.
    """


class NoMatchingResourceError(ValueError):
    """
    Raised if there is no resource matching a given set of tags.
    """
    pass


def find_unique_resource_matching_tags(resources, *, expected_tags):
    """
    Given a list of AWS resources, find the unique resource matching a given
    set of tags.

    The tags should be a Python dictionary, e.g. {"key1": "value1", "key2": "value2"}
    """
    if not expected_tags:
        raise ValueError("Cannot match against an empty set of tags")

    def _is_match(resource):
        resource_tags = parse_aws_tags(resource.get("tags", []))
        return all(
            k in resource_tags and resource_tags[k] == v
            for k, v in expected_tags.items()
        )

    matching_resources = [r for r in resources if _is_match(r)]

    if len(matching_resources) == 1:
        return matching_resources[0]
    elif not matching_resources:
        raise NoMatchingResourceError(f"Could not find any resources with tags {expected_tags}")
    else:
        raise MultipleMatchingResourcesError(
            f"Found multiple resources with tags {expected_tags}, expected one: {matching_resources}"
        )
