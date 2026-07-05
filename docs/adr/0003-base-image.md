# 0003 — Base Image: Iron Bank Attempt, UBI9-Minimal, and STIG Remediation

## Status

Accepted

(Numbered 0003, not 0002 as `Project.md` originally names this file —
[0002-trivy-unfixed-cve-policy.md](0002-trivy-unfixed-cve-policy.md) had to claim 0002 in Phase 1 to keep the
Trivy gate meaningful before this phase existed.)

## Context

Phase 0/1 used `python:3.12-slim-bookworm` (Debian). Phase 2 asks first for
an Iron Bank base image, falling back to UBI9 + OpenSCAP DISA STIG
remediation if Iron Bank isn't reachable.

## Iron Bank attempt

```
$ docker pull registry1.dso.mil/ironbank/opensource/python/python39:v3.9
Error response from daemon: failed to resolve reference
"registry1.dso.mil/ironbank/opensource/python/python39:v3.9": pull access
denied, repository does not exist or may require authorization:
authorization failed: no basic auth credentials
```

Iron Bank (`registry1.dso.mil`) requires a Platform One SSO account, which
in turn is normally gated on organizational/CAC-based affiliation. There's
no anonymous or public-token pull path for a personal portfolio project —
this isn't a bug or misconfiguration, it's Iron Bank's actual access model
(hardened images for DoD program use, not public distribution). Falling
back to UBI9 per `Project.md` is the correct and expected outcome here, not
a workaround.

## UBI9 image selection

Two UBI9-family options were evaluated by actually building and measuring
each, not by assumption:

| Base | Non-root by default | Image size | CRITICAL CVEs (Trivy) |
| --- | --- | --- | --- |
| `ubi9/python-312` (s2i builder image) | yes (uid 1001, gid 0) | 1.6GB | not evaluated further — size alone ruled it out |
| `ubi9/ubi-minimal` + `microdnf install python3.12` | no (added `useradd`, same as Phase 0/1) | 279MB | 0 |
| (for comparison) Phase 1's `python:3.12-slim-bookworm` | no (added `useradd`) | 248MB | 0 CRITICAL blocking, 4 tracked unfixed ([0002-trivy-unfixed-cve-policy.md](0002-trivy-unfixed-cve-policy.md)) |

`ubi9/python-312` is Red Hat's s2i (source-to-image) builder image — it
ships a full dev toolchain (compilers, headers) intended for `s2i build`
workflows, not as a slim runtime base. It's genuinely non-root by
convention, which is a nice property, but 1.6GB blows Phase 0's <250MB
target by 6x for no runtime benefit in our multi-stage build (we already
discard the builder stage).

`ubi9-minimal` + a direct `microdnf install python3.12` mirrors exactly
what Phase 1 did with `python:3.12-slim-bookworm` (multi-stage venv build,
manual `useradd`), and lands at 279MB — 12% over the original <250MB
target, but this is the deliberate, accepted cost of moving from a general
-purpose Debian base to a base drawn from Red Hat's UBI program (a
concrete, recognizable step toward the Iron Bank/Platform One ecosystem
this project is aimed at, even though direct Iron Bank access wasn't
available). `--setopt=install_weak_deps=0 --nodocs` on every `microdnf
install` avoids pulling optional recommends (this alone was the difference
between an early 1.6GB miss and landing near budget).

**Decision: `registry.access.redhat.com/ubi9/ubi-minimal` as the runtime
base, built via microdnf, not the s2i `python-312` image.**

## OpenSCAP DISA STIG scan and remediation

SCAP content (`ssg-rhel9-ds.xml`) was pulled from the upstream
[ComplianceAsCode/content](https://github.com/ComplianceAsCode/content)
v0.1.81 release — UBI9's own repos (BaseOS/AppStream/CodeReady Builder)
and even EPEL9 don't carry `scap-security-guide`, so the authoritative
upstream release is the correct source, not a packaging gap to work around.

`oscap xccdf eval --profile xccdf_org.ssgproject.content_profile_stig`
against the pre-hardening image:

- 415 `notapplicable` (systemd/audit-daemon/service-level rules that don't
  apply to a container with no init system — expected and correct, not a
  gap)
- 61 `pass`
- 7 `fail`
- 1 `notchecked` (a manual/procedural rule — "Ensure Software Patches
  Installed" — not something OVAL can automatically verify)

Full reports: [`docs/evidence/phase2-openscap-stig-before.html`](../evidence/phase2-openscap-stig-before.html)
and [`docs/evidence/phase2-openscap-stig-after.html`](../evidence/phase2-openscap-stig-after.html).

### The 7 failures, and what happened to each

Used the SSG project's own official remediation bash scripts
(`oscap xccdf eval --remediate`) to derive the exact fix for each rule,
then hand-translated the resulting file diffs into explicit `RUN`
instructions in the `Dockerfile`, so the fix is reproducible at build time
rather than a one-off manual patch:

| Rule | Outcome | Fix baked into Dockerfile |
| --- | --- | --- |
| `accounts_umask_etc_bashrc` | **fixed** | `umask 022` → `umask 077` in `/etc/bashrc` |
| `accounts_umask_etc_profile` | **fixed** | `umask 077` appended to `/etc/profile` |
| `file_permission_user_init_files_root` | **fixed** | `chmod 0640` on root's `.bashrc`/`.bash_profile`/`.bash_logout`/`.cshrc`/`.tcshrc` |
| `rootfiles_configured` | **fixed** | `/etc/tmpfiles.d/rootfiles.conf` added, overriding the base image's looser `/usr/lib/tmpfiles.d/rootfiles.conf` (644 → 600) |
| `use_pam_wheel_for_su` | **not applicable to the shipped image** | see below |
| `configure_crypto_policy` | **not fixable in a container** | see below |
| `network_configure_name_resolution` | **not applicable at build time** | see below |

### The 3 that stay documented, not "fixed"

A repo like this is more credible showing an honest 4/7 remediated with
three clearly explained exceptions than claiming 7/7 — the exceptions are
structural, not effort:

1. **`use_pam_wheel_for_su`** — this is a scanning-tooling artifact, not a
   property of the shipped image. `ubi9-minimal` ships **no PAM stack and
   no `su` binary at all** (`/etc/pam.d/su` doesn't exist). The rule only
   showed up as `fail` because installing `openscap-scanner` to run the
   scan pulls in a PAM stack as a transitive dependency, which then has no
   `pam_wheel` line — an artifact of the measurement method, since the
   scanner has to install itself into the thing it's scanning. The actual
   shipped image (without the scanner installed) has nothing for this rule
   to check.
2. **`configure_crypto_policy`** — this profile's check is actually an
   OVAL definition named `enable_fips_mode`, which depends on the *kernel*
   having been booted with `fips=1` at install time. That's a host/VM
   -level, install-time setting a container can never independently have,
   since containers share the host kernel. SSG's own content says as much
   elsewhere in the same profile ("If this rule fails on an installed
   system, then this is a permanent finding and cannot be fixed").
   `update-crypto-policies --set FIPS` was tested manually — it happily
   updates a symlink but doesn't change the underlying kernel FIPS state,
   so it wouldn't make the OVAL check pass regardless.
3. **`network_configure_name_resolution`** — wants 2-3 nameservers in
   `/etc/resolv.conf`. Docker overwrites `/etc/resolv.conf` at container
   start based on the host/daemon's DNS config; baking specific
   nameserver IPs into the image would be inert (overwritten on every
   `docker run`) and is the wrong layer to fix this at.

## Consequences

- Runtime image grew from 248MB (Debian) to 279MB (UBI9-minimal) — a 12%
  size cost, accepted deliberately for base-image provenance.
- Trivy CRITICAL count went from 0-blocking-but-4-tracked-unfixed (Debian,
  see [0002-trivy-unfixed-cve-policy.md](0002-trivy-unfixed-cve-policy.md)) to a clean 0 with nothing tracked
  (UBI9-minimal) — a real, measured improvement, not just a different
  vendor's CVE feed.
- The three unresolved STIG findings are structurally tied to "this is a
  container, not a booted host" — they'd recur on *any* container base
  image (Iron Bank included), not just this one. Re-attempting Iron Bank
  access later would not change this section.
