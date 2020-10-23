from deploy.git import log


def test_gets_commit_log():
    assert log("125d42f") == "Bump version to 5.4.3 and update changelog"


def test_returns_empty_string_for_missing_commit():
    assert log("doesnotexist", run_fetch=False) == ""
