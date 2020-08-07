from .iam import Iam


class SecretsManager:
    def __init__(self, account_id, region_name, role_arn):
        self.account_id = account_id
        self.region_name = region_name
        self.session = Iam.get_session(
            session_name="ReleaseToolSecretsManager",
            role_arn=role_arn,
            region_name=region_name
        )
        self.secretsmanager = self.session.client('secretsmanager')

    def get_secret_value(self, secret_id):
        response = self.secretsmanager.get_secret_value(
            SecretId=secret_id,
        )

        return response
