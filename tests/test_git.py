import pytest

from deploy.git import log


@pytest.mark.skip(
    'Something about Git in the tox container is broken in CI; '
    'skipping this test until we can debug properly.'
)
def test_gets_commit_log():
    assert log("125d42f") == "Bump version to 5.4.3 and update changelog"


@pytest.mark.skip(
    'Something about Git in the tox container is broken in CI; '
    'skipping this test until we can debug properly.'
)
def test_returns_empty_string_for_missing_commit():
    assert log("doesnotexist", run_fetch=False) == ""
