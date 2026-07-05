variable "aws_region" {
  description = "AWS region to provision against (LocalStack accepts any valid region name)"
  type        = string
  default     = "us-east-1"
}

variable "localstack_endpoint" {
  description = "LocalStack edge endpoint"
  type        = string
  default     = "http://localhost:4566"
}

variable "project_name" {
  description = "Name prefix applied to all provisioned resources"
  type        = string
  default     = "ato-in-a-pipeline"
}

variable "vpc_cidr" {
  description = "CIDR block for the demo VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "public_subnet_cidr" {
  description = "CIDR block for the public subnet"
  type        = string
  default     = "10.0.1.0/24"
}
