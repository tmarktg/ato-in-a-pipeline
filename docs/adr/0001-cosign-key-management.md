# 0001 — Cosign Key Management

## Status

Accepted

## Context

Phase 1 needs to sign every built image so Phase 4's Kyverno policy can verify
the signature before admitting a pod. Cosign supports two signing modes:

1. **Keyless (Fulcio/Rekor, OIDC-based)** — no long-lived key to manage, but
   requires trusting Sigstore's public-good instance and a network round
   trip to Fulcio/Rekor at sign and verify time.
2. **Repo key pair** — a static private/public key pair; the private key
   signs in CI, the public key is committed and used everywhere else to
   verify.

## Decision

Use a repo key pair, per the tech stack table in `Project.md` ("keyless not
required; use a repo key pair, document rotation").

- `cosign.pub` is committed at the repo root — it's the verification
  material Kyverno's `verifyImages` policy (Phase 4) and any reviewer need.
- `cosign.key` (the encrypted private key) is **never committed** — it's
  git-ignored and lives only as a CI secret file/variable
  (`COSIGN_KEY`), decrypted at sign time with a second CI secret
  (`COSIGN_PASSWORD`).
- The key was generated with `cosign generate-key-pair` under a randomly
  generated passphrase (not empty), so a leaked `cosign.key` file alone is
  not sufficient to sign images.

## Rotation

- Rotate on: suspected private-key compromise, a team member with CI
  secret access leaving, or annually as a baseline hygiene interval.
- Rotation procedure:
  1. Generate a new pair: `cosign generate-key-pair` (produces a new
     `cosign.key` / `cosign.pub`).
  2. Update the CI secrets `COSIGN_KEY` / `COSIGN_PASSWORD` in both GitLab
     and GitHub project settings.
  3. Commit the new `cosign.pub`, and update the public key embedded in the
     Kyverno `verify-image-signature` policy (Phase 4) in the same commit so
     policy and signing key never drift apart.
  4. Old images signed with the retired key remain verifiable only if the
     old public key is kept around for a documented grace window; for this
     project (not a real ATO, no production traffic) we do not keep grace
     windows — rotation is a hard cutover, and previously built images are
     rebuilt/re-signed if they need to be redeployed after a rotation.

## Consequences

- Signing has zero dependency on an external transparency-log service being
  reachable from CI, which matters for a project designed to run without
  cloud spend or external accounts.
- The tradeoff is that this project owns key custody: if `COSIGN_KEY` and
  `COSIGN_PASSWORD` are both exfiltrated from CI secrets, an attacker can
  forge signatures until rotation happens. This is an accepted tradeoff for
  a demonstration pipeline; a real ATO'd system would weigh keyless/KMS-backed
  signing against this operational simplicity.
