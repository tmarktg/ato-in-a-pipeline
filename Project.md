# Secure Software Delivery Reference Pipeline (ATO-in-a-Pipeline)

A DoD-style DevSecOps software factory demonstrating how software moves from commit to a hardened Kubernetes cluster through automated security and compliance gates. The pipeline is the product; the app exists to be shipped by it.

**Target audience for this repo:** defense contractor hiring managers (Booz Allen, Leidos, GDIT, General Atomics) and technical interviewers familiar with Platform One, Iron Bank, and NIST RMF.

**Author context:** Junior DevOps engineer with active Secret clearance. Repo must read as professional and program-ready — boring name, clean docs, no memes.

---

## Goals

1. Demonstrate a CI pipeline where security gates are **hard-blocking**, not advisory.
2. Generate and retain supply-chain artifacts (SBOM, scan reports, signatures) on every build.
3. Enforce deploy-time policy in Kubernetes (no root, no unsigned images, approved registry only).
4. Map every control implemented to a NIST 800-53 rev5 control ID in a compliance matrix.
5. Provision all infra with Terraform; demonstrate continuous-monitoring via drift detection.

## Non-Goals

- No cloud spend. Everything runs locally (kind/k3s, LocalStack where AWS APIs are needed) or in free CI tiers.
- Not a real ATO. The compliance matrix maps controls; it does not claim authorization.
- The app is intentionally simple. Do not add app features beyond what Phase 0 specifies.

---

## Tech Stack

| Concern                   | Tool                                                                  | Notes                                                                                                                                       |
| ------------------------- | --------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| App                       | Python 3.12, FastAPI, uvicorn                                         | Minimal REST service                                                                                                                        |
| App DB                    | SQLite (dev) / Postgres container (deployed)                          | Keep swap trivial via env config                                                                                                            |
| Containers                | Docker, multi-stage builds                                            | Base: Iron Bank UBI9-python if pullable without auth; else `registry.access.redhat.com/ubi9/python-312` hardened with OpenSCAP STIG profile |
| CI                        | GitLab CI (`.gitlab-ci.yml`)                                          | Mirror repo to GitLab; GitHub is source of truth for portfolio visibility. Provide a GitHub Actions equivalent workflow as secondary.       |
| SAST                      | Semgrep (CI-friendly, fast)                                           | Fail on ERROR severity                                                                                                                      |
| Dependency/container scan | Trivy                                                                 | Fail on CRITICAL, warn on HIGH                                                                                                              |
| Secrets detection         | Gitleaks                                                              | Fail on any finding                                                                                                                         |
| SBOM                      | Syft (SPDX + CycloneDX output)                                        | Attach as CI artifact per build                                                                                                             |
| Image signing             | Cosign (keyless not required; use a repo key pair, document rotation) |                                                                                                                                             |
| Kubernetes                | kind (CI) / k3s (local demo)                                          |                                                                                                                                             |
| Policy engine             | Kyverno                                                               | Chosen over Gatekeeper for readable YAML policies; document the tradeoff in an ADR                                                          |
| IaC                       | Terraform + LocalStack                                                | Provisions "AWS" VPC/ECR-equivalent locally                                                                                                 |
| Drift detection           | Existing LangGraph drift-detection agent (separate repo)              | Integrate as Phase 5; link, don't vendor                                                                                                    |
| Compliance                | Markdown matrix + OSCAL JSON (stretch)                                | NIST 800-53 rev5                                                                                                                            |

---

## Phase 0 — The Simple App ("shipit-demo")

Build first so every later phase has something real to ship. Keep it under ~300 lines of app code.

**App: "Readiness Board"** — a tiny service that tracks deployable service statuses. Chosen because it's demo-relevant (a DevOps-flavored domain) without being complex.

Endpoints:

- `GET /healthz` — liveness (returns 200, no dependencies)
- `GET /readyz` — readiness (checks DB connectivity)
- `GET /services` — list tracked services and status
- `POST /services` — add a service `{name, version, status}` (basic pydantic validation)
- `PUT /services/{id}/status` — update status (enum: `green|yellow|red`)
- `GET /metrics` — Prometheus format via `prometheus-fastapi-instrumentator`

Requirements:

- 12-factor config: all settings via env vars (`DATABASE_URL`, `LOG_LEVEL`, `PORT`). No config files.
- Structured JSON logging to stdout.
- Pytest suite: unit tests for handlers + one integration test with a temp DB. Target ≥80% coverage; coverage gate enforced in CI later.
- Run as non-root in the container (UID 1001), read-only root filesystem compatible, no capabilities required. Design the app so Phase 4 policies pass without rework.
- Multi-stage Dockerfile: builder stage installs deps, final stage copies venv only. Final image target < 250MB.
- `Makefile` with: `make run`, `make test`, `make lint`, `make image`, `make scan` (local Trivy).

Acceptance criteria:

- [ ] `make test` green, coverage ≥80%
- [ ] Container runs as non-root and passes `docker run --read-only`
- [ ] `/healthz`, `/readyz`, `/metrics` all respond correctly in container

## Phase 1 — CI Pipeline with Hard Security Gates

`.gitlab-ci.yml` stages: `lint → test → sast → secrets → build → scan → sbom → sign → publish`

- Semgrep: fail pipeline on ERROR-severity findings. Config in `.semgrep.yml`.
- Gitleaks: fail on any secret. Include a `.gitleaks.toml` with documented false-positive allowlist (empty to start).
- Trivy: scan the built image. `--exit-code 1 --severity CRITICAL`. HIGH findings produce a report artifact and a warning.
- Syft: emit `sbom.spdx.json` and `sbom.cdx.json` as pipeline artifacts, retained 30 days.
- Cosign: sign the image digest; push signature alongside image.
- Deliberately commit a known-vulnerable dependency on a branch and capture a screenshot/CI link of the pipeline failing. Put it in `docs/evidence/`. **This "the gate actually blocks" proof is a core interview artifact.**
- Provide `.github/workflows/pipeline.yml` mirroring the same stages for GitHub visibility.

Acceptance criteria:

- [ ] Clean main branch: full pipeline green, SBOM + signed image produced
- [ ] Vulnerable branch: pipeline fails at scan stage, evidence captured

## Phase 2 — Hardened Container Baseline

- Attempt Iron Bank base image (document registry1.dso.mil access experience either way).
- Fallback path: UBI9 base + OpenSCAP scan with DISA STIG profile. Save before/after scan HTML reports to `docs/evidence/`.
- Write `docs/adr/0002-base-image.md` explaining the choice.

Acceptance criteria:

- [ ] OpenSCAP before/after reports committed, with remediation summary in README

## Phase 3 — Terraform Infra

- Terraform provisions (against LocalStack): container registry, network primitives, and outputs consumed by deploy scripts.
- Remote state simulated locally; document how it would map to S3 + DynamoDB locking in real AWS.
- `terraform plan` runs in CI on merge requests; plan output posted as artifact.

Acceptance criteria:

- [ ] `terraform apply` idempotent against LocalStack
- [ ] CI runs `fmt`, `validate`, `plan` on every MR

## Phase 4 — Kubernetes Deploy with Policy Enforcement

- kind cluster in CI, k3s for local demo. Deploy via Kustomize (base + overlays for `dev`/`prod`).
- Kyverno policies (each in its own file under `policy/`):
  1. Disallow root containers (`runAsNonRoot: true` required)
  2. Require image signature verification (Cosign public key)
  3. Restrict images to the approved registry
  4. Require resource limits
  5. Disallow `latest` tag
- Include a `policy-tests/` directory using Kyverno CLI `apply --resource` tests: one passing manifest, one violating manifest per policy, run in CI.
- Evidence: capture the admission-denied output when deploying an unsigned image.

Acceptance criteria:

- [ ] All 5 policies enforced in cluster; violation attempts denied with captured evidence
- [ ] Kyverno CLI policy tests run in CI and pass

## Phase 5 — Continuous Monitoring (Drift Detection Integration)

- Integrate the existing LangGraph Terraform drift-detection agent as the CA-7 continuous-monitoring story.
- Scheduled CI job (or cron in cluster) runs drift check against LocalStack state; drift produces a report artifact and a non-zero exit.
- Document the integration in `docs/continuous-monitoring.md`; link the agent repo rather than vendoring it.

Acceptance criteria:

- [ ] Manually induced drift (out-of-band resource change) is detected and reported by the scheduled job

## Phase 6 — Compliance Matrix (The Differentiator)

- `docs/compliance-matrix.md`: table with columns `Control ID | Control Name | Implementation | Evidence Link`.
- Minimum mappings:
  - RA-5 (Vulnerability Scanning) → Trivy stage
  - SI-7 (Software Integrity) → Cosign signing + Kyverno verification
  - CM-7 (Least Functionality) → Kyverno restriction policies, non-root, read-only fs
  - CM-2 / CM-3 (Baseline Config / Change Control) → Terraform + MR pipeline
  - SA-11 (Developer Testing) → pytest + Semgrep stages
  - AU-\* (Audit) → CI artifact retention, structured logs
  - CA-7 (Continuous Monitoring) → drift detection job
  - IA-5 (Authenticator Mgmt) → Gitleaks secrets gate
- Every row must link to a real file, pipeline config line, or evidence artifact in the repo. No aspirational rows.
- Stretch: emit the matrix as an OSCAL component-definition JSON under `compliance/oscal/`.

Acceptance criteria:

- [ ] ≥8 controls mapped with working evidence links
- [ ] Matrix referenced prominently from the top-level README

---

## Repo Structure

```
secure-delivery-pipeline/
├── README.md                  # Architecture diagram, quickstart, link to compliance matrix
├── PROJECT.md                 # This file
├── Makefile
├── app/                       # Phase 0 FastAPI app
│   ├── main.py
│   ├── models.py
│   ├── config.py
│   └── tests/
├── Dockerfile
├── .gitlab-ci.yml
├── .github/workflows/pipeline.yml
├── .semgrep.yml
├── .gitleaks.toml
├── terraform/
├── k8s/
│   ├── base/
│   └── overlays/{dev,prod}/
├── policy/                    # Kyverno policies
├── policy-tests/
├── compliance/
│   └── oscal/                 # stretch
└── docs/
    ├── adr/                   # Architecture decision records
    ├── evidence/              # Screenshots, scan reports, denied-admission logs
    ├── compliance-matrix.md
    └── continuous-monitoring.md
```

---

## Working Instructions for Claude Code

- Work phase by phase, in order. Do not start a phase until the prior phase's acceptance criteria are met. Each phase should end in a commit-ready, demoable state.
- Prefer boring, widely-used configurations over clever ones. This repo optimizes for legibility to defense-industry reviewers.
- Every non-obvious tool choice gets a short ADR in `docs/adr/` (Kyverno vs Gatekeeper, base image, kind vs k3s, etc.).
- Keep the app frozen after Phase 0. Pipeline changes only.
- All scripts must be runnable on Fedora Linux. No macOS-only tooling.
- README top section must include: one-paragraph pitch, architecture diagram (Mermaid is fine), quickstart (`make demo` that spins up k3s/kind and deploys end-to-end), and a link to the compliance matrix.
- Evidence discipline: whenever a gate blocks something or a policy denies an admission, capture the output into `docs/evidence/` immediately. These artifacts are the interview material.

## Definition of Done (whole project)

- [ ] `make demo` performs an end-to-end local deploy through all gates
- [ ] A deliberately bad commit is demonstrably blocked at three different layers (CI scan, secrets gate, K8s admission)
- [ ] Compliance matrix complete with evidence links
- [ ] README presentable to a hiring manager in under 2 minutes of reading
