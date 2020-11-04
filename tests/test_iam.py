import pytest

from deploy.iam import get_account_id


def test_gets_get_account_id():
    assert get_account_id("arn:aws:iam::1234567890:role/worker_role") == "1234567890"


@pytest.mark.parametrize("role_arn", [
    "not-an-arn",
    "not-arn:aws:iam::1234567890:role/worker_role"
])
def test_spots_invalid_arn(role_arn):
    with pytest.raises(ValueError) as err:
        get_account_id(role_arn)

    assert err.value.args[0] == f"Is this a valid AWS ARN? {role_arn}"


@pytest.mark.parametrize("role_arn", [
    "arn:aws:iam:eu-west-1:1234567890:role/worker_role",
    "arn:aws:sqs:eu-west-1:1234567890:queue/example_queue",
    "arn:aws:sqs:eu-west-1:wellcome:queue/example_queue",
])
def test_spots_non_iam_arn(role_arn):
    with pytest.raises(ValueError) as err:
        get_account_id(role_arn)

    assert err.value.args[0] == f"Is this an IAM role ARN? {role_arn}"
