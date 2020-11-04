import boto3


def get_account_id(role_arn):
    """
    Returns the account ID for a given role ARN.
    """
    # The format of an IAM role ARN is
    #
    #     arn:partition:service:region:account:resource
    #
    # Where:
    #
    # - 'arn' is a literal string
    # - 'service' is always 'iam' for IAM resources
    # - 'region' is always blank for IAM resources
    # - 'account' is the AWS account ID with no hyphens
    #
    # See https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_identifiers.html#identifiers-arns
    try:
        arn, _, service, region, account, _ = role_arn.split(":")
    except ValueError:
        raise ValueError(f"Is this a valid AWS ARN? {role_arn}")

    if arn != "arn":
        raise ValueError(f"Is this a valid AWS ARN? {role_arn}")

    if service != "iam" or region != "" or not account.isnumeric():
        raise ValueError(f"Is this an IAM role ARN? {role_arn}")

    return account


def get_underlying_role_arn():
    """
    Returns the original role ARN.

    e.g. at Wellcome we have a base role, but then we assume roles into different
    accounts.  This returns the ARN of the base role.
    """
    client = boto3.client('sts')
    return client.get_caller_identity()["Arn"]


def get_session(session_name, role_arn, region_name):
    client = boto3.client('sts')
    response = client.assume_role(
        RoleArn=role_arn,
        RoleSessionName=session_name
    )

    return boto3.session.Session(
        aws_access_key_id=response['Credentials']['AccessKeyId'],
        aws_secret_access_key=response['Credentials']['SecretAccessKey'],
        aws_session_token=response['Credentials']['SessionToken'],
        region_name=region_name
    )
