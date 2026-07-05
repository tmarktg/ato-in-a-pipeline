output "vpc_id" {
  description = "ID of the demo VPC — consumed by deploy scripts to place cluster/networking resources"
  value       = aws_vpc.main.id
}

output "public_subnet_id" {
  description = "ID of the public subnet"
  value       = aws_subnet.public.id
}

output "app_security_group_id" {
  description = "Security group ID for app-tier resources"
  value       = aws_security_group.app.id
}

output "artifacts_bucket" {
  description = "S3 bucket for long-term SBOM/scan-report archival"
  value       = aws_s3_bucket.artifacts.bucket
}

output "tf_lock_table" {
  description = "DynamoDB table name demonstrating the remote-state lock pattern"
  value       = aws_dynamodb_table.tf_lock.name
}
