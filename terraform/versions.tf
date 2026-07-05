terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Local backend for this demo (LocalStack, no real AWS account). See
  # docs/adr/0004-terraform-state-backend.md for the S3 + DynamoDB backend
  # this would use against real AWS, and why the resources this config
  # provisions are the same ones that migration would depend on.
}
