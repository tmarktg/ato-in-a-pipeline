# Continuous Monitoring (CA-7)

Phase 5 has two layers: a small, free, mechanical drift *check* that runs on
a schedule inside this repo's own CI, and a separate, more capable
detect→classify→remediate *agent* that this repo links to rather than
vendors, per `Project.md`.

## Layer 1 — scheduled `terraform plan` gate (this repo, CI)

`.github/workflows/drift-check.yml` and the `drift-check` job in
`.gitlab-ci.yml` run on a daily cron schedule (and can be triggered
manually). Each run:

1. Starts a LocalStack service container.
2. `terraform -chdir=terraform apply -auto-approve` — establishes the
   known-good baseline (Phase 3's VPC/network primitives, the S3 artifact
   bucket, and the DynamoDB lock table).
3. `terraform -chdir=terraform plan -detailed-exitcode` — Terraform's own
   drift-detection exit code convention: `0` = no changes, `1` = error,
   `2` = changes present (drift).
4. Uploads the plan output as a build artifact and fails the job (non-zero
   exit) if exit code `2` was returned.

This is deliberately minimal — no LLM calls, no extra services beyond
LocalStack, no API key. It exists so "did anything change out-of-band"
has a free, always-on, mechanical answer, matching Phase 5's acceptance
criterion literally: a manually induced drift is detected and reported by
the scheduled job (see [Proving it](#proving-it-manually-induced-drift)
below).

GitHub Actions runs `schedule:`-triggered workflows automatically once
they exist on the default branch — no extra setup. GitLab has no YAML-only
equivalent; a **Pipeline Schedule** must be created once in the project's
CI/CD settings (pointing at this same `.gitlab-ci.yml`) before the
`drift-check` job ever fires there. Every other job is scoped with
`except: [schedules]` (and `publish` with an equivalent `rules:` guard) so
a GitLab schedule tick runs only `drift-check`, not the full pipeline.

## Layer 2 — the agent: detect, classify, remediate

The deeper CA-7 story — telling *what kind* of drift happened and whether
it's safe to auto-fix — is
[**agentic-ai-devops**](https://github.com/tmarktg/agentic-ai-devops), an
existing, independently-authored project. It's linked here, not vendored,
per `Project.md`'s explicit instruction.

**What it is:** a single LangGraph ReAct agent (Claude Sonnet for the main
loop, Claude Haiku for cheap classification sub-calls) that runs
`terraform plan`, classifies each finding's severity via an LLM call plus a
pgvector-backed runbook search, and either auto-remediates (low/medium
severity) or pauses for human approval via a graph `interrupt()`
(high-severity or incident-correlated findings — never auto-applied). Every
step is persisted to a Postgres checkpointer as a tamper-evident audit
trail. Full architecture, safety guarantees, and a demo walkthrough are in
that repo's README.

**Why it isn't wired into this repo's scheduled CI job:** it needs a real
`ANTHROPIC_API_KEY` (real cost per invocation) and a Postgres+pgvector
service, and its `runbooks/` corpus (RAG passages for tag drift, open
security groups, S3 versioning) is tuned to its own demo infrastructure,
not this repo's specific resource shapes. Adding that secret and those
services to an unattended job that fires on a timer regardless of whether
anyone's watching didn't seem like the right trade for what Phase 5 asks
for. Layer 1 covers the "detect and report" requirement for free; the agent
is the tool a human reaches for when Layer 1 reports drift and someone
needs to know *what changed and whether it's safe to fix*.

**How it points at this repo's infra** — its Terraform tool takes a
`working-dir` argument, so it isn't hardcoded to its own demo
infrastructure:

```bash
# from a clone of agentic-ai-devops, with its own docker-compose services up
python -m app.run \
  --working-dir /path/to/ato-in-a-pipeline/terraform \
  --aws-endpoint localhost:4566 \
  --objective "detect and remediate all infrastructure drift"
```

The `terraform_plan`/`classify_findings` read-only path generalizes fine to
this repo's VPC/S3/DynamoDB resources. Runbook-backed remediation
suggestions will be weaker here than against the agent's own demo
infrastructure until runbooks are added for this repo's specific resource
types — the classify+report loop is proven to generalize; the remediation
corpus is not yet tuned to this repo.

## Proving it: manually induced drift

1. `make tf-apply` — establish the baseline against LocalStack.
2. Mutate a provisioned resource out-of-band, bypassing Terraform (e.g.
   `awslocal ec2 authorize-security-group-ingress ...` against the security
   group `terraform/main.tf` provisions, or delete a DynamoDB table tag).
3. Run the same check the scheduled job runs:
   `terraform -chdir=terraform plan -detailed-exitcode`.
4. Exit code `2`, plan output shows the reverted-looking diff — the drift
   is caught.

Evidence from exactly this sequence, run against a real LocalStack
instance: [`docs/evidence/phase5-drift-detected.txt`](evidence/phase5-drift-detected.txt).
