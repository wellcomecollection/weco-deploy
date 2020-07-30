resource "aws_autoscaling_group" "asg" {
  name                = "${var.name}_asg"
  max_size            = var.max_instances
  vpc_zone_identifier = var.subnets

  min_size                  = 0
  default_cooldown          = 60
  desired_capacity          = 0
  health_check_type         = "EC2"
  health_check_grace_period = 180

  launch_template {
    id      = aws_launch_template.launch_template.id
    version = aws_launch_template.launch_template.latest_version
  }

  enabled_metrics = [
    "GroupMinSize",
    "GroupMaxSize",
    "GroupDesiredCapacity",
    "GroupInServiceInstances",
    "GroupPendingInstances",
    "GroupStandbyInstances",
    "GroupTerminatingInstances",
    "GroupTotalInstances"
  ]

  tag {
    key                 = "Name"
    value               = "${var.name}_instance"
    propagate_at_launch = true
  }
}

resource "aws_launch_template" "launch_template" {
  name                   = "${var.name}_launch_template"
  instance_type          = var.instance_type
  image_id               = var.ami_id == null ? data.aws_ami.ecs_optimized.id : var.ami_id
  vpc_security_group_ids = var.security_group_ids
  update_default_version = true

  ebs_optimized = var.ebs_size_gb > 0

  dynamic "block_device_mappings" {
    for_each = var.ebs_size_gb > 0 ? [{}] : []

    content {
      // The instance volume used by Docker
      device_name = "/dev/xvdcz"

      ebs {
        volume_size           = var.ebs_size_gb
        volume_type           = var.ebs_volume_type
        delete_on_termination = true
      }
    }
  }

  dynamic "instance_market_options" {
    for_each = var.use_spot_purchasing ? [{}] : []

    content {
      market_type = "spot"
    }
  }
}

data "aws_ami" "ecs_optimized" {
  owners      = ["amazon"]
  most_recent = true

  filter {
    name   = "name"
    values = ["amzn-ami-*-amazon-ecs-optimized"]
  }
}
