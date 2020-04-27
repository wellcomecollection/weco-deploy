data "aws_caller_identity" "current" {}

data "aws_iam_policy_document" "read_secrets" {
  statement {
    actions = [
      "ssm:GetParameters",
    ]

    resources = local.ssm_resources
  }

  statement {
    actions = [
      "secretsmanager:GetSecretValue",
    ]

    resources = local.secrets_resources
  }
}