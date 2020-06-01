module "task_role" {
  source = "./iam_role"

  task_name = var.task_name
}

resource "aws_ecs_task_definition" "task" {
  family                = var.task_name
  container_definitions = jsonencode(var.container_definitions)

  task_role_arn      = module.task_role.task_role_arn
  execution_role_arn = module.task_role.task_execution_role_arn

  network_mode = var.network_mode

  requires_compatibilities = var.launch_types

  cpu    = var.cpu
  memory = var.memory

  # Unused here, but must be set to prevent churn
  tags = {}

  # This is a slightly obtuse way to make these two blocks conditional.
  # They should only be created if this task definition is using EBS volume
  # mounts; otherwise they should be ignored.
  #
  # This is a kludge around Terraform's "dynamic blocks".
  # See https://www.terraform.io/docs/configuration/expressions.html#dynamic-blocks
  #
  # There's an open feature request on the Terraform repo to add syntactic
  # sugar for this sort of conditional block.  If that ever arises, we should
  # use that instead.  See https://github.com/hashicorp/terraform/issues/21512
  dynamic "volume" {
    for_each = var.ebs_volume_name == "" ? [] : [{}]

    content {
      name      = var.ebs_volume_name
      host_path = var.ebs_host_path
    }
  }

  dynamic "placement_constraints" {
    for_each = var.ebs_volume_name == "" ? [] : [{}]

    content {
      type       = "memberOf"
      expression = "attribute:ebs.volume exists"
    }
  }

  # We do the same as above for the EFS volume.
  dynamic "volume" {
    for_each = var.efs_volume_name == "" ? [] : [{}]

    content {
      name      = var.efs_volume_name
      host_path = var.efs_host_path
    }
  }

  dynamic "placement_constraints" {
    for_each = var.efs_volume_name == "" ? [] : [{}]

    content {
      type       = "memberOf"
      expression = "attribute:efs.volume exists"
    }
  }

  dynamic "volume" {
    for_each = var.extra_volumes

    content {
      name      = volume.value["name"]
      host_path = volume.value["host_path"]
    }
  }
}
