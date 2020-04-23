variable "task_name" {
  type = string
}

variable "container_definitions" {}

variable "launch_types" {
  type = list(string)
}

variable "network_mode" {
  default = "awsvpc"
  type    = string
}

variable "cpu" {
  type    = number
  default = null
}

variable "memory" {
  type    = number
  default = null
}

variable "ebs_volume_name" {
  type    = string
  default = ""
}

variable "ebs_host_path" {
  type    = string
  default = ""
}

variable "efs_volume_name" {
  type    = string
  default = ""
}

variable "efs_host_path" {
  type    = string
  default = ""
}