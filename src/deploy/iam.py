import boto3


class Iam:
    def __init__(self, role_arn=None):
        self.session = Iam.get_session("ReleaseToolIamUserDetails", role_arn)
        self.iam = self.session.resource('iam')

    @staticmethod
    def get_session(session_name, role_arn=None):
        if role_arn:
            client = boto3.client('sts')
            response = client.assume_role(
                RoleArn=role_arn,
                RoleSessionName=session_name
            )

            return boto3.session.Session(
                aws_access_key_id=response['Credentials']['AccessKeyId'],
                aws_secret_access_key=response['Credentials']['SecretAccessKey'],
                aws_session_token=response['Credentials']['SessionToken']
            )
        else:
            return boto3.session.Session()

    def caller_identity(self, underlying=False):
        if underlying:
            client = boto3.client('sts')
        else:
            client = self.session.client('sts')

        caller_identity = client.get_caller_identity()

        return {
            "arn": caller_identity['Arn'],
            "user_id": caller_identity['UserId'],
            "account_id": caller_identity['Account']
        }
