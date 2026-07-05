# ato-in-a-pipeline

A DoD-style DevSecOps software factory: a small FastAPI service ("Readiness
Board") whose CI pipeline enforces **hard-blocking** security gates (SAST,
secrets, vulnerability scanning), produces signed images with attached
SBOMs, and deploys through Kyverno-enforced Kubernetes policy. The pipeline
is the product; the app exists to be shipped by it.
Everything runs locally or in free CI tiers — no cloud spend, and this is
not a real ATO (see [`Project.md`](Project.md) for the full spec and
non-goals). Every control below is mapped to real, working evidence in the
[**NIST 800-53 compliance matrix**](docs/compliance-matrix.md).

## Status

- [x] **Phase 0** — Readiness Board app (FastAPI, 100% test coverage, non-root/read-only-fs container)
- [x] **Phase 1** — CI with hard-blocking gates (Semgrep, Gitleaks, Trivy, Syft, Cosign)
- [x] **Phase 2** — Hardened base image (UBI9) + OpenSCAP DISA STIG remediation
- [x] **Phase 3** — Terraform/LocalStack infra (VPC/network, S3, DynamoDB)
- [x] **Phase 4** — Kubernetes deploy with Kyverno policy enforcement
- [x] **Phase 5** — Continuous monitoring (drift detection)
- [x] **Phase 6** — NIST 800-53 compliance matrix
- [x] **Phase 7** — OSCAL compliance-as-code (generated matrix + machine-readable component-definition)
- [x] **Phase 8** — Configuration management with Ansible (idempotent STIG hardening + demo-env provisioning)

## Architecture

![Architecture diagram: commit flows through GitLab CI security gates (SAST + ansible-lint, Secrets, CVE Scan, SBOM + Sign) to a registry, then through Kyverno admission control into Kubernetes; Terraform/LocalStack and a drift-detection agent feed continuous monitoring, Ansible provides idempotent STIG hardening and demo-env provisioning; every stage maps into the NIST 800-53 compliance matrix.](docs/architecture.svg)

## Quickstart

```bash
make venv    # create .venv, install dev dependencies
make test    # pytest, 100% coverage gate
make lint    # ruff
make image   # build the hardened UBI9-based container image
make run     # run the app locally against a SQLite DB

make localstack-up    # start LocalStack (community edition)
make tf-plan          # terraform init + plan against LocalStack
make tf-apply         # terraform init + apply against LocalStack
make localstack-down  # tear down LocalStack

make demo       # kind up + Kyverno install + policy tests + deploy the real signed image
make kind-down  # tear the demo cluster down

make drift-check  # terraform plan -detailed-exitcode against LocalStack (exit 2 = drift)

make compliance-gen    # regenerate docs/compliance-matrix.md + OSCAL component-definition.json
make compliance-check  # regenerate, fail on drift, then validate the OSCAL JSON

make ansible-deps        # install pinned Ansible collections (community.docker, ansible.posix)
make ansible-harden      # recreate a fresh ubi9_target container, apply the STIG hardening role
make ansible-idempotency # rerun the same role against that container, fail unless changed=0
make ansible-provision   # install kind/kubectl/kustomize/helm/kyverno-cli (Linux x86_64 only)
```

`make demo` requires `kind`, `kubectl`, `kustomize`, `helm`, and the
Kyverno CLI on `PATH`. It deploys the real, signed
`ghcr.io/tmarktg/ato-in-a-pipeline:stable` image through all 5 Kyverno
policies against a throwaway local kind cluster — see
[Kubernetes deploy (Phase 4)](#kubernetes-deploy--policy-enforcement-phase-4)
below.

## CI pipeline (Phase 1)

`.gitlab-ci.yml` and `.github/workflows/pipeline.yml` both run the same
twelve stages: `lint → test → sast → secrets → compliance → ansible-lint →
terraform → build → scan → sbom → sign → publish`.

- **SAST** — Semgrep (`.semgrep.yml`), fails on ERROR severity.
- **Secrets** — Gitleaks (`.gitleaks.toml`), fails on any finding.
- **Compliance** — regenerates `docs/compliance-matrix.md` and the OSCAL
  `component-definition.json` from `compliance/controls.yaml`, fails on any
  drift from what's committed, then schema-validates the OSCAL JSON — see
  [Machine-readable compliance (OSCAL, Phase 7)](#machine-readable-compliance-oscal-phase-7)
  below.
- **Ansible-lint** — `ansible-lint --profile production` plus
  `ansible-playbook --syntax-check` on both playbooks; any finding is red,
  same as every other gate — see
  [Configuration management (Phase 8)](#configuration-management-with-ansible-phase-8)
  below.
- **Scan** — Trivy, fails on CRITICAL (unfixed CVEs with no vendor patch are
  tracked, not blocking — [ADR 0002](docs/adr/0002-trivy-unfixed-cve-policy.md)).
- **SBOM** — Syft emits SPDX + CycloneDX, retained 30 days.
- **Sign** — Cosign signs the image digest with a repo key pair
  ([ADR 0001](docs/adr/0001-cosign-key-management.md)); `cosign.pub` is
  committed, the private key lives only as a CI secret.

Evidence that the gates actually block, not just advise:
[`docs/evidence/phase1-scan-gate-blocks-vulnerable-dependency.txt`](docs/evidence/phase1-scan-gate-blocks-vulnerable-dependency.txt)
— a deliberately vulnerable dependency (`pyyaml==5.3.1`, CVE-2020-14343,
CRITICAL) fails the scan stage with exit code 1 — and
[`docs/evidence/phase1-secrets-gate-blocks-committed-credential.txt`](docs/evidence/phase1-secrets-gate-blocks-committed-credential.txt)
— a deliberately committed fake AWS credential fails the secrets stage the
same way, on a demo branch never merged to main. Combined with the K8s
admission-denial evidence in [Phase 4](#kubernetes-deploy--policy-enforcement-phase-4),
a bad commit is demonstrably blocked at all three layers `Project.md` asks
for.

## Hardened base image (Phase 2)

Attempted Iron Bank (`registry1.dso.mil`) first; access requires a
Platform One SSO account with no public/anonymous pull path, so the
project falls back to `registry.access.redhat.com/ubi9/ubi-minimal` per
`Project.md`'s own fallback plan. Full writeup, including why the s2i
`python-312` image was rejected (1.6GB vs. 279MB) and the Trivy before/after
numbers: [ADR 0003](docs/adr/0003-base-image.md).

**OpenSCAP DISA STIG remediation summary** (RHEL9 STIG profile, full
reports: [before](docs/evidence/phase2-openscap-stig-before.html) /
[after](docs/evidence/phase2-openscap-stig-after.html)):

| | Before | After |
| --- | --- | --- |
| Pass | 61 | 65 |
| Fail | 7 | 3 |
| Not applicable | 415 | 415 |
| Not checked (manual/procedural) | 1 | 1 |

Four rules were remediated directly in the `Dockerfile` (umask policy in
`/etc/bashrc` and `/etc/profile`, root shell-init file permissions tightened
to 0640, `/etc/tmpfiles.d/rootfiles.conf` override). The remaining three
are documented in [ADR 0003](docs/adr/0003-base-image.md) as structurally
out of scope for a container image — one requires a kernel booted with
`fips=1` (impossible for any container sharing a host kernel), one is an
artifact of the scanner's own install pulling in a PAM stack the shipped
image doesn't otherwise have, and one (DNS servers in `/etc/resolv.conf`)
is overwritten by Docker at container start regardless of what ships in
the image.

## Infrastructure (Phase 3)

`terraform/` provisions against [LocalStack](https://www.localstack.cloud/)
(community/free edition): a VPC with a public subnet, internet gateway,
route table, and security group (real network primitives, not stubs), plus
an S3 bucket for long-term SBOM/scan-report archival and a DynamoDB table
demonstrating the remote-state lock pattern. `terraform apply` is verified
idempotent (`0 added, 0 changed, 0 destroyed` on a second apply). CI runs
`fmt`, `validate`, and `plan` (with plan output posted as a build artifact)
against a LocalStack service container on every push.

There's deliberately no Terraform-provisioned container registry — ECR is
a LocalStack **Pro** (paid) feature, which would violate this project's own
no-cloud-spend constraint. The real registry is GHCR/GitLab's registry,
already wired up in Phase 1. Full reasoning, plus exactly how the local
state backend maps to a real S3 + DynamoDB backend in real AWS:
[ADR 0004](docs/adr/0004-terraform-localstack-scope.md).

## Kubernetes deploy & policy enforcement (Phase 4)

`k8s/base` (Deployment + Service) and `k8s/overlays/{dev,prod}` (Kustomize
overlays — replica counts, resource limits, namespaces) deploy the
Readiness Board app. Admission into the cluster is gated by five Kyverno
`ClusterPolicy` resources in `policy/`, each in its own file:

| Policy | Enforces |
| --- | --- |
| [`require-non-root.yaml`](policy/require-non-root.yaml) | `runAsNonRoot: true`, no `runAsUser: 0` |
| [`require-signed-images.yaml`](policy/require-signed-images.yaml) | Cosign signature verification against `cosign.pub` ([ADR 0001](docs/adr/0001-cosign-key-management.md)) |
| [`restrict-registry.yaml`](policy/restrict-registry.yaml) | Images must come from `ghcr.io/tmarktg/*` |
| [`require-resource-limits.yaml`](policy/require-resource-limits.yaml) | Every container sets `resources.limits.cpu` and `.memory` |
| [`disallow-latest-tag.yaml`](policy/disallow-latest-tag.yaml) | No bare/`:latest` image references |

Why Kyverno over Gatekeeper, and kind (CI) over k3s (local demo):
[ADR 0005](docs/adr/0005-kind-and-kyverno.md).

**Policy tests** (`policy-tests/`) — one passing and one violating fixture
per policy, run via `kyverno apply <policy> --resource <fixture>` and
checked by `policy-tests/run.sh` (`make policy-test`, and the first step of
`make demo`). All 5 pass/fail both directions today.

**Evidence** — a live kind cluster, all 5 policies enforced, admitting the
real signed image and denying violations of every policy, one at a time:

- [`phase4-policies-admit-signed-image.txt`](docs/evidence/phase4-policies-admit-signed-image.txt) — the real, signed `ghcr.io/tmarktg/ato-in-a-pipeline:stable` image running in-cluster.
- [`phase4-admission-denied-unsigned-image.txt`](docs/evidence/phase4-admission-denied-unsigned-image.txt) — an unverifiable image denied by `require-signed-images`.
- [`phase4-admission-denied-other-policies.txt`](docs/evidence/phase4-admission-denied-other-policies.txt) — root containers, an unapproved registry, missing resource limits, and a `:latest` tag, each denied by its respective policy.

Both CI pipelines run the same flow on every push: `kyverno apply` fixture
tests, a throwaway kind cluster, Kyverno install, policy apply, then a
deploy of that run's own signed image digest into the `dev` overlay
(GitLab's mirror deploys the published GHCR `:stable` image instead, since
that pipeline's own build lands in GitLab's registry, not GHCR — see the
`k8s-policy` job comments in `.gitlab-ci.yml`).

## Continuous monitoring (Phase 5)

A scheduled CI job (`drift-check` — cron in GitHub Actions, a GitLab
Pipeline Schedule) runs `terraform plan -detailed-exitcode` against this
repo's own Phase 3 LocalStack infra daily: exit `0` = clean, exit `2` =
drift, plan output uploaded as an artifact either way. Free, no LLM calls,
no extra services.

The deeper detect→classify→remediate story is
[**agentic-ai-devops**](https://github.com/tmarktg/agentic-ai-devops) — an
existing LangGraph ReAct agent (Claude + pgvector RAG + Postgres
checkpointer), linked here rather than vendored per `Project.md`. It can be
pointed at this repo's own `terraform/` directory to classify drift
severity and gate remediation behind human approval for anything
high-severity or incident-correlated. Full writeup, including why it isn't
wired into the scheduled CI job (real API cost, Postgres+pgvector
dependency): [`docs/continuous-monitoring.md`](docs/continuous-monitoring.md).

**Evidence** — a manually induced out-of-band change (opening SSH ingress
directly against LocalStack, bypassing Terraform) caught by the same
`terraform plan -detailed-exitcode` the scheduled job runs:
[`phase5-drift-detected.txt`](docs/evidence/phase5-drift-detected.txt)
(exit code 2).

## Compliance matrix (Phase 6)

[`docs/compliance-matrix.md`](docs/compliance-matrix.md) maps 15 NIST
800-53 rev5 controls across the AC, AU, CA, CM, IA, RA, SA, SC, and SI
families to the file, pipeline stage, or evidence artifact that actually
backs each one — no aspirational rows. It also lists what's deliberately
*not* mapped (account management, backups, incident response) because this
repo genuinely doesn't implement them, rather than padding the table.

## Machine-readable compliance (OSCAL, Phase 7)

The matrix above and [`compliance/oscal/component-definition.json`](compliance/oscal/component-definition.json)
are both generated from a single source of truth,
[`compliance/controls.yaml`](compliance/controls.yaml), by
[`scripts/generate_compliance.py`](scripts/generate_compliance.py); CI
regenerates both on every push and fails if either differs from what's
committed, then validates the OSCAL JSON against the official schema. See
[ADR 0006](docs/adr/0006-oscal-compliance-generation.md) for why
`component-definition` and not a full SSP, and how this pattern maps to
eMASS/Xacta ingestion in a real cATO pipeline.

## Configuration management with Ansible (Phase 8)

Phase 2's STIG remediation only ever proved a setting was correct *at
image-build time*. `ansible/roles/stig_hardening` re-expresses the same
four fixes (default umask in `/etc/bashrc`/`/etc/profile`, root
shell-init file permissions, the `/etc/tmpfiles.d` override) as idempotent
tasks against a running, pre-hardening UBI9 container reached via the
`community.docker.docker` connection plugin — no SSH, no VM, no cloud
spend. `ansible/roles/demo_env` closes a separate gap: `make demo` used to
silently assume `kind`/`kubectl`/`kustomize`/`helm`/the Kyverno CLI were
already installed; it now provisions that exact pinned toolchain (Linux
x86_64 only — it fails fast with a clear message elsewhere).

**Evidence** — first run against a fresh container changes 6 tasks
([`phase8-harden-first-run.txt`](docs/evidence/phase8-harden-first-run.txt));
rerunning the same role against that same container reports `changed=0`
([`phase8-harden-idempotency.txt`](docs/evidence/phase8-harden-idempotency.txt));
the resulting filesystem state is verified directly inside the container,
independent of Ansible's own report
([`phase8-stig-verify.txt`](docs/evidence/phase8-stig-verify.txt)); and a
deliberate violation (a bare `shell` task, no `changed_when`) on a
throwaway branch is caught by the `ansible-lint` gate with a non-zero exit
([`phase8-ansible-lint-fail.txt`](docs/evidence/phase8-ansible-lint-fail.txt)).

Why a container target instead of a VM, why `community.docker.docker`,
and why Molecule was considered and deferred:
[ADR 0007](docs/adr/0007-ansible-configuration-management.md).
