resource "aws_ecr_repository" "weco-deploy" {
  name                 = "wellcome/weco-deploy"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecrpublic_repository" "weco-deploy" {
  provider = aws.ecr_public

  repository_name = "weco-deploy"

  catalog_data {
    about_text  = "A tool for deploying Docker-based ECS services at Wellcome Collection"
    description = "See https://github.com/wellcomecollection/weco-deploy"
  }
}