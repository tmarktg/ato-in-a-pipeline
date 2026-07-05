# 0007 — Ansible Configuration Management: Container Target, Scope, and Molecule

## Status

Accepted

## Context

Every prior phase manages configuration at **image-build time** only —
the Phase 2 Dockerfile's STIG remediation `RUN` block is baked into the
image once, at `docker build`, and never re-applied or re-verified against
a running system. `make demo` also silently assumes `kind`, `kubectl`,
`kustomize`, `helm`, and the Kyverno CLI are already installed. `Project.md`
asks Phase 8 to close both gaps with Ansible: re-express the STIG fixes as
idempotent, re-runnable tasks against a live container, and provision the
demo toolchain the same way real programs manage nodes rather than just
images.

## Build-time vs. running-system remediation

A Dockerfile `RUN` instruction proves a setting was correct *at the moment
the image was built*. It says nothing about whether that setting still
holds on a container that's been running for months, been patched
in-place, or drifted for any other reason — there's no mechanism to
re-check or re-apply it short of rebuilding and redeploying the whole
image. `ansible/roles/stig_hardening` re-expresses the same four STIG
fixes ADR 0003 already applies at build time as tasks that can be pointed
at *any* running UBI9 container and will both detect drift (report
`changed`) and correct it, without a rebuild. This is the difference
between "the image was compliant once" and "the running system is
compliant, checkably, right now" — the latter is what real configuration
management actually means, and what CM-2/CM-6 in `compliance/controls.yaml`
now cite this role for.

## Container target via `community.docker.docker`, not a VM

Two things ruled out a VM target: this project's own no-cloud-spend,
no-extra-services constraints (`Project.md` non-goals), and the fact that
Phase 2 already established which STIG findings are meaningful for a
container in the first place. Provisioning a VM just to re-run the same
container-scoped checks against it would test a different, less relevant
surface.

`community.docker.docker` — a connection plugin, not a management module —
lets Ansible treat a running container exactly like a normal managed host
(`docker exec` under the hood) using only the `docker` CLI already on the
controller. No SSH keys, no VM boot time, and it's exactly as CI-runnable
as every other phase in this repo (GitHub Actions' `ubuntu-latest` and
GitLab's shared runners both ship Docker). The target,
`registry.access.redhat.com/ubi9/ubi-minimal:latest`, is deliberately the
same **pre-hardening** base Phase 2 starts from — not this project's own
already-hardened production image, which would report `changed=0` on the
very first run and prove nothing about idempotency (see
`docs/evidence/phase8-harden-first-run.txt` vs.
`phase8-harden-idempotency.txt`).

One consequence carries over directly from ADR 0003: the three STIG
findings documented there as structurally inapplicable to *any* container
(the PAM/`su` scanning artifact, kernel FIPS mode, and `/etc/resolv.conf`
being Docker-managed) are exactly as inapplicable to an Ansible-managed
container as to a Dockerfile-built one. This phase doesn't re-litigate
that reasoning — the `stig_hardening` role only re-implements the four
findings ADR 0003 actually fixed.

## Molecule: considered, deferred

[Molecule](https://ansible.readthedocs.io/projects/molecule/) is the
standard tool for testing Ansible roles — spin up a target, converge,
verify, converge again to check idempotency, destroy. It was seriously
considered here since it's purpose-built for exactly the
apply-twice-and-check-idempotency story this phase needs.

Deferred for scope: Molecule would add its own test-scenario directory,
its own driver configuration (itself usually Docker-based, meaning
"testing infrastructure to test the thing that's already just Docker"),
and its own `verify.yml`/testinfra or Ansible-assertion layer — real
value, but weight this project's own idempotency evidence artifacts
already cover at this scope. `make ansible-harden` and
`make ansible-idempotency` apply the role twice against the same
container, and `phase8-stig-verify.txt` checks the resulting filesystem
state directly, independent of Ansible's own "changed" report — the same
apply-twice-and-verify shape Molecule would formalize, without a second
testing framework layered on top of a two-role playbook. If this
repository's Ansible surface grows past `stig_hardening` and `demo_env`,
Molecule is the obvious next tool to reach for.

## What isn't mapped to a control

`demo_env` (the toolchain-provisioning role) isn't cited in
`compliance/controls.yaml`. It's real engineering value — closing the gap
where `make demo` silently assumed a pre-installed toolchain — but it
provisions development tooling, not a system security control; mapping it
to CM-2 or CM-6 to inflate the control count would be exactly the
aspirational-row padding `Project.md`'s compliance instructions rule out.

## Consequences

- `compliance/controls.yaml`'s CM-2 and CM-6 entries now cite both the
  Phase 2 Dockerfile fix and the Phase 8 Ansible role for the same
  underlying settings — extended in place, not duplicated as separate
  rows, since they're two expressions of the same control, not two
  controls.
- `ansible-lint --profile production` and `ansible-playbook --syntax-check`
  gate both playbooks in CI, matching the "any finding = red pipeline"
  posture every other gate in this repo already has.
- `demo_env`'s toolchain-install path is Linux x86_64-only by design
  (`ansible.builtin.assert` fails fast with a clear message otherwise).
  The author's own development machine is `darwin/arm64`, so the install
  path itself can only be positive-path-verified in GitHub Actions'
  `ubuntu-latest` runner or a real Fedora box — locally, only the guard's
  refusal to proceed and the role's lint/syntax cleanliness were checked.
