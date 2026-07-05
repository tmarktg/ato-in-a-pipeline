# NIST 800-53 rev5 Compliance Matrix

Maps controls actually implemented in this repo to the file, pipeline
stage, or evidence artifact that backs them. This is not a claim of
authorization — see [`Project.md`](../Project.md)'s non-goals — it is a
traceability matrix: every row below links to something real you can open
and check for yourself. No row here describes a control this repo doesn't
actually enforce.

| Control ID | Control Name | Implementation | Evidence |
| --- | --- | --- | --- |
| [CM-2](https://csf.tools/reference/nist-sp-800-53/r5/cm/cm-2/) | Baseline Configuration | The LocalStack infra baseline (VPC, subnet, internet gateway, route table, security group, S3 bucket, DynamoDB lock table) is codified in Terraform, not manually configured | [`terraform/main.tf`](../terraform/main.tf) |
| [CM-3](https://csf.tools/reference/nist-sp-800-53/r5/cm/cm-3/) | Configuration Change Control | Every infra change runs `terraform fmt`/`validate`/`plan` in CI before it can merge; plan output is posted as a reviewable artifact | [`.github/workflows/pipeline.yml#L88-L102`](../.github/workflows/pipeline.yml#L88-L102), [ADR 0004](adr/0004-terraform-localstack-scope.md) |
| [CM-6](https://csf.tools/reference/nist-sp-800-53/r5/cm/cm-6/) | Configuration Settings | The UBI9 base image is remediated against the RHEL9 DISA STIG profile (umask policy, root shell-init file permissions, tmpfiles override) | [`Dockerfile#L28-L42`](../Dockerfile#L28-L42), [before](evidence/phase2-openscap-stig-before.html)/[after](evidence/phase2-openscap-stig-after.html) OpenSCAP reports, [ADR 0003](adr/0003-base-image.md) |
| [CM-7](https://csf.tools/reference/nist-sp-800-53/r5/cm/cm-7/) | Least Functionality | Kyverno denies admission to images from unapproved registries and any `:latest`-tagged image | [`policy/restrict-registry.yaml`](../policy/restrict-registry.yaml), [`policy/disallow-latest-tag.yaml`](../policy/disallow-latest-tag.yaml), [`phase4-admission-denied-other-policies.txt`](evidence/phase4-admission-denied-other-policies.txt) |
| [CM-8](https://csf.tools/reference/nist-sp-800-53/r5/cm/cm-8/) | System Component Inventory | Syft generates an SPDX and a CycloneDX SBOM for every built image, retained 30 days | [`.github/workflows/pipeline.yml#L162-L182`](../.github/workflows/pipeline.yml#L162-L182) |
| [AC-6](https://csf.tools/reference/nist-sp-800-53/r5/ac/ac-6/) | Least Privilege | Container runs as non-root (UID 1001) with a read-only root filesystem and all Linux capabilities dropped; re-enforced at admission | [`Dockerfile#L54`](../Dockerfile#L54), [`k8s/base/deployment.yaml#L36-L39`](../k8s/base/deployment.yaml#L36-L39), [`policy/require-non-root.yaml`](../policy/require-non-root.yaml), [`phase4-admission-denied-other-policies.txt`](evidence/phase4-admission-denied-other-policies.txt) |
| [SI-2](https://csf.tools/reference/nist-sp-800-53/r5/si/si-2/) | Flaw Remediation | Trivy HIGH findings produce a non-blocking triage report; unfixed CRITICALs with no vendor patch are tracked rather than perpetually blocking the pipeline | [`.github/workflows/pipeline.yml#L143-L156`](../.github/workflows/pipeline.yml#L143-L156), [ADR 0002](adr/0002-trivy-unfixed-cve-policy.md) |
| [SI-7](https://csf.tools/reference/nist-sp-800-53/r5/si/si-7/) | Software, Firmware, and Information Integrity | Cosign signs every image digest in CI; Kyverno verifies that signature against the same public key before the pod is admitted | [`.github/workflows/pipeline.yml#L196-L203`](../.github/workflows/pipeline.yml#L196-L203), [`policy/require-signed-images.yaml`](../policy/require-signed-images.yaml), [`phase4-admission-denied-unsigned-image.txt`](evidence/phase4-admission-denied-unsigned-image.txt), [ADR 0001](adr/0001-cosign-key-management.md) |
| [RA-5](https://csf.tools/reference/nist-sp-800-53/r5/ra/ra-5/) | Vulnerability Monitoring and Scanning | Trivy scans every built image and fails the pipeline on any CRITICAL finding | [`.github/workflows/pipeline.yml#L136-L142`](../.github/workflows/pipeline.yml#L136-L142), [`phase1-scan-gate-blocks-vulnerable-dependency.txt`](evidence/phase1-scan-gate-blocks-vulnerable-dependency.txt) |
| [SA-11](https://csf.tools/reference/nist-sp-800-53/r5/sa/sa-11/) | Developer Testing and Evaluation | pytest gates merges at ≥80% coverage; Semgrep SAST fails the pipeline on ERROR-severity findings | [`pyproject.toml#L1-L2`](../pyproject.toml#L1-L2), [`app/tests/`](../app/tests), [`.semgrep.yml`](../.semgrep.yml), [`.github/workflows/pipeline.yml#L20-L46`](../.github/workflows/pipeline.yml#L20-L46) |
| [IA-5](https://csf.tools/reference/nist-sp-800-53/r5/ia/ia-5/) | Authenticator Management | Gitleaks fails the pipeline on any secret detected in source; the Cosign private key is never committed and lives only as a CI secret, with rotation documented | [`.gitleaks.toml`](../.gitleaks.toml), [`.github/workflows/pipeline.yml#L59-L69`](../.github/workflows/pipeline.yml#L59-L69), [ADR 0001](adr/0001-cosign-key-management.md) |
| [AU-2](https://csf.tools/reference/nist-sp-800-53/r5/au/au-2/) | Event Logging | The app emits structured JSON logs (timestamp, level, logger, message) to stdout for every request | [`app/main.py#L22-L30`](../app/main.py#L22-L30) |
| [AU-11](https://csf.tools/reference/nist-sp-800-53/r5/au/au-11/) | Audit Record Retention | Every gate's report (Semgrep, Gitleaks, Trivy, SBOM, Terraform plan, drift-check plan) is retained as a CI artifact for 30 days | `retention-days: 30` / `expire_in: 30 days` across [`pipeline.yml`](../.github/workflows/pipeline.yml), [`.gitlab-ci.yml`](../.gitlab-ci.yml), [`drift-check.yml`](../.github/workflows/drift-check.yml) |
| [CA-7](https://csf.tools/reference/nist-sp-800-53/r5/ca/ca-7/) | Continuous Monitoring | A scheduled job runs `terraform plan -detailed-exitcode` against LocalStack daily (non-zero exit on drift); the deeper classify/remediate story is linked, not vendored | [`.github/workflows/drift-check.yml`](../.github/workflows/drift-check.yml), [`continuous-monitoring.md`](continuous-monitoring.md), [`phase5-drift-detected.txt`](evidence/phase5-drift-detected.txt) |
| [SC-7](https://csf.tools/reference/nist-sp-800-53/r5/sc/sc-7/) | Boundary Protection | Terraform provisions a dedicated VPC, public subnet, internet gateway, route table, and a security group scoping ingress to the app port only | [`terraform/main.tf#L3-L72`](../terraform/main.tf#L3-L72) |

## What's deliberately not mapped

A few controls a full ATO package would require aren't mapped here because
this repo doesn't actually implement them, and `Project.md`'s own
non-goals rule out padding this table with aspirational rows:

- **AC-2 (Account Management)** — the app has no user accounts or auth to manage.
- **CP-9 (System Backup)** — no persistent production data store exists to back up (SQLite in a container `emptyDir`, by design — see Phase 4's `k8s/base/deployment.yaml`).
- **IR-\* (Incident Response)** — no incident response process exists for a portfolio project; would be theater if mapped here.

## Stretch: OSCAL

`Project.md` lists an OSCAL component-definition JSON under
`compliance/oscal/` as a stretch goal. Not attempted — the markdown matrix
above already satisfies the acceptance criteria (≥8 controls, working
evidence links), and hand-authoring OSCAL JSON that just re-encodes this
same table without a consuming tool to validate it against would be
exactly the kind of unverified, aspirational artifact this matrix is
trying to avoid.
