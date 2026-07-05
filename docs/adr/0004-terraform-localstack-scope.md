# 0004 — Terraform/LocalStack Scope and State Backend Mapping

## Status

Accepted

## Context

`Project.md` asks Terraform to provision, against LocalStack: "container
registry, network primitives, and outputs consumed by deploy scripts," and
to document how local state would map to an S3 + DynamoDB backend in real
AWS.

## ECR is not free

LocalStack's community (free) edition does not include ECR at all — it
isn't listed as a service, enabled or disabled, in
`/_localstack/health`:

```
$ curl -s http://localhost:4566/_localstack/health | python3 -m json.tool
{
  "services": {
    "ec2": "available",
    "iam": "available",
    "s3": "available",
    "dynamodb": "available",
    "sts": "available",
    ...
    # no "ecr" key at all
  },
  "edition": "community"
}
```

ECR emulation is a LocalStack Pro (paid) feature. Provisioning it would
require a paid LocalStack license, which directly violates this project's
own non-goal: "No cloud spend. Everything runs locally ... or in free CI
tiers." Paying for LocalStack Pro to simulate a registry, when this
project already has a real, free container registry (GHCR / GitLab
Container Registry, wired up in Phase 1), would be spending money to fake
something we already have for real.

**Decision: don't provision ECR.** Terraform's scope for the registry
side of Phase 3 is instead:

- `aws_s3_bucket.artifacts` — a genuinely functional (against LocalStack
  community) bucket for long-term SBOM/scan-report archival beyond CI's
  30-day artifact retention. Not a registry, but a real, working piece of
  supply-chain evidence storage that Terraform actually provisions.
- Real container images continue to live in GHCR/GitLab's registry, signed
  and scanned by the Phase 1 pipeline — Terraform has nothing useful to do
  there, since those registries aren't ours to provision.

Network primitives (VPC, subnet, internet gateway, route table, security
group) are all free/community LocalStack services and are provisioned for
real in `terraform/main.tf`.

## Remote state: local now, S3+DynamoDB mapping

State is currently local (`terraform/terraform.tfstate`, gitignored) —
appropriate for a single-operator demo project with no team to coordinate
locking against. `Project.md` asks this to be documented rather than
implemented, since a real S3 backend needs a real AWS account (cloud
spend) to test.

The mapping is direct, and — importantly — **this phase already
provisions the exact resources that migration would point at**, proving
the pattern isn't just theoretical:

```hcl
terraform {
  backend "s3" {
    bucket         = "ato-in-a-pipeline-artifacts"   # aws_s3_bucket.artifacts, this phase
    key            = "terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "ato-in-a-pipeline-tf-lock"     # aws_dynamodb_table.tf_lock, this phase
    encrypt        = true
  }
}
```

To actually cut over: add the `backend "s3"` block above to
`terraform/versions.tf`, point `bucket`/`dynamodb_table` at real AWS
resources (the same names this phase already uses against LocalStack),
run `terraform init -migrate-state`, and remove `terraform/terraform.tfstate`
from local disk. No resource definitions change — only the backend block.

## Consequences

- `terraform apply` against LocalStack provisions VPC/network primitives +
  S3 + DynamoDB, all free/community-tier — verified idempotent (`0 added,
  0 changed, 0 destroyed` on a second apply).
- No registry resource exists in this Terraform config; readers looking
  for "where does Terraform create the ECR repo" should look here instead
  of assuming it was missed.
- The S3 bucket and DynamoDB table this phase provisions aren't
  demo-only stand-ins — they're literally the resources a real S3 backend
  migration would reuse, so the "how this maps to real AWS" story is
  backed by working infrastructure, not just a paragraph.
