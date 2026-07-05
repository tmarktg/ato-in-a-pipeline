# Network primitives ---------------------------------------------------

resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name = "${var.project_name}-vpc"
  }
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "${var.project_name}-igw"
  }
}

resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = var.public_subnet_cidr
  map_public_ip_on_launch = true

  tags = {
    Name = "${var.project_name}-public-subnet"
  }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = {
    Name = "${var.project_name}-public-rt"
  }
}

resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}

resource "aws_security_group" "app" {
  name        = "${var.project_name}-app-sg"
  description = "Allow inbound app traffic within the VPC"
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "Readiness Board app port"
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-app-sg"
  }
}

# Registry-adjacent / remote-state-pattern resources ---------------------
#
# ECR is a LocalStack Pro (paid) feature, which conflicts with this
# project's no-cloud-spend constraint (see docs/adr/0004). The real image
# registry is GitHub Container Registry / GitLab's registry, already wired
# up in Phase 1's CI pipeline — Terraform has nothing to provision there.
#
# What we provision instead, for real, against LocalStack's free
# community edition: an S3 bucket for long-term SBOM/scan-report
# archival beyond CI's 30-day artifact retention, and a DynamoDB table
# demonstrating the state-lock pattern a real S3 remote-state backend
# would use. Both are genuinely functional against LocalStack, not stubs.

resource "aws_s3_bucket" "artifacts" {
  bucket = "${var.project_name}-artifacts"

  tags = {
    Name = "${var.project_name}-artifacts"
  }
}

resource "aws_dynamodb_table" "tf_lock" {
  name         = "${var.project_name}-tf-lock"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }

  tags = {
    Name = "${var.project_name}-tf-lock"
  }
}
