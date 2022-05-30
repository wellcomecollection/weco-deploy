locals {
  default_tags = {
    TerraformConfigurationURL = "https://github.com/wellcomecollection/weco-deploy/tree/main/terraform"
    Department                = "Digital Platform"
    Division                  = "Culture and Society"
    Use                       = "weco-deploy"
    Environment               = "Production"
  }
}

provider "aws" {
  region = "eu-west-1"

  assume_role {
    role_arn = "arn:aws:iam::760097843905:role/platform-developer"
  }

  default_tags {
    tags = local.default_tags
  }
}

provider "aws" {
  region = "us-east-1"
  alias  = "ecr_public"

  assume_role {
    role_arn = "arn:aws:iam::760097843905:role/platform-developer"
  }

  default_tags {
    tags = local.default_tags
  }
}
