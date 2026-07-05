# 0005 — Kubernetes Cluster (kind vs. k3s) and Policy Engine (Kyverno vs. Gatekeeper)

## Status

Accepted

## Context

`Project.md` calls for two Kubernetes tool choices in Phase 4: a local
cluster to run and demo against, and an admission-policy engine to enforce
the five deploy-time gates (non-root, signed images, approved registry,
resource limits, no `:latest`). Both choices needed a documented rationale
per the working instructions ("every non-obvious tool choice gets a short
ADR ... kind vs k3s").

## Cluster: kind in CI, k3s for local demo

`Project.md` specifies this split explicitly, and it maps directly onto
what each tool is actually good at:

- **kind** (Kubernetes-in-Docker) starts from a plain `docker.io/kindest/node`
  image, needs no host-level init system, and tears down with
  `kind delete cluster` — a clean fit for a GitHub Actions/GitLab CI runner
  that already has a Docker daemon and nothing else. This is also what this
  project actually used to build and verify every manifest and policy in
  this phase (see `docs/evidence/phase4-*`).
- **k3s** installs as a systemd-managed binary with its own embedded
  containerd, and is meant to run persistently on a real (or long-lived VM)
  host — a better fit for someone cloning this repo to run a standing local
  demo (`make demo`) than a throwaway CI job.

Running kind in CI and documenting k3s as the local-demo path (rather than
forcing one tool into both roles) avoids two bad options: k3s's systemd
dependency doesn't play well with ephemeral CI containers, and kind's
Docker-in-Docker model is more setup than a local demo needs when the host
already has a real Docker install to hand a plain kind cluster to anyway —
kind works equally well for the local demo, so `make demo` uses it too
unless k3s is already installed, to avoid requiring two different tools for
what is otherwise the identical `kubectl apply` + Kyverno flow.

## Policy engine: Kyverno over OPA/Gatekeeper

Both are CNCF admission-control projects capable of enforcing all five
Phase 4 policies. The deciding factor is authoring format, since this
project's audience is defense-industry reviewers who need to read and
audit policy intent quickly, not debug Rego:

- **Kyverno** policies are plain Kubernetes YAML (`ClusterPolicy` with
  `match`/`validate` blocks) — no new language to learn, and the policy
  reads close to the English description of the control it enforces. It
  also has first-class, declarative image-verification
  (`verifyImages`/`attestors.keys.publicKeys`) that maps directly onto this
  project's existing Cosign key-pair from
  [ADR 0001](0001-cosign-key-management.md), with no extra webhook or
  sidecar to write.
- **Gatekeeper** requires policies written in Rego (via OPA `ConstraintTemplate`
  + `Constraint` CRDs), which is more expressive but is its own language
  with its own debugging story — a real cost for a project whose stated
  goal is legibility, not maximum policy flexibility. Gatekeeper has no
  native Cosign image-verification story either; that would need a
  separate admission controller (e.g. Connaisseur or Sigstore's policy
  controller) layered in just for that one rule.

Since none of Phase 4's five policies need Rego's extra expressiveness,
Kyverno's YAML-native policies and built-in image verification are a
strictly better fit here.

## Consequences

- `policy/*.yaml` are plain `ClusterPolicy` resources, readable without any
  Rego knowledge — see `policy/require-non-root.yaml`,
  `policy/restrict-registry.yaml`, `policy/require-resource-limits.yaml`,
  `policy/disallow-latest-tag.yaml`, and `policy/require-signed-images.yaml`.
- `policy/require-signed-images.yaml` verifies against `cosign.pub`
  directly, reusing Phase 1's signing key with no additional components.
- CI (`kind`) and the documented local demo path (`k3s` or `kind`, per
  `make demo`) exercise the identical Kustomize manifests and Kyverno
  policies — there is no CI-only or demo-only policy variant to keep in
  sync.
