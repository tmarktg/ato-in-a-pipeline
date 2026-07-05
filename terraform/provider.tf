# Points the AWS provider at LocalStack instead of real AWS. Credentials
# are dummy values — LocalStack doesn't validate them, but the provider
# requires something non-empty to be present.
provider "aws" {
  region                      = var.aws_region
  access_key                  = "test"
  secret_key                  = "test"
  s3_use_path_style           = true
  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true

  endpoints {
    ec2      = var.localstack_endpoint
    iam      = var.localstack_endpoint
    sts      = var.localstack_endpoint
    s3       = var.localstack_endpoint
    dynamodb = var.localstack_endpoint
  }
}
