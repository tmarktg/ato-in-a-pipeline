# 0006 — OSCAL Compliance Generation: Model, Determinism, and Validation

## Status

Accepted

## Context

Phase 6 shipped a hand-written `docs/compliance-matrix.md` and explicitly
declined to attempt the OSCAL stretch goal, reasoning that hand-authoring a
second, JSON-shaped copy of the same table without a consuming tool to
validate it against would itself be an aspirational artifact — exactly what
the matrix is trying to avoid.

Phase 7 changes what's possible: `Project.md` now asks for
`compliance/controls.yaml` as the single source of truth, with both
`docs/compliance-matrix.md` and an OSCAL `component-definition.json`
*generated* from it, and a CI stage that fails if either generated file
drifts from what's committed. That closes the original objection — the
JSON is no longer hand-authored, and CI proves it stays honest. Three tool
choices in that pipeline are non-obvious enough to warrant this ADR.

## Model: component-definition, not system-security-plan

OSCAL has several top-level models. The two candidates here are
`component-definition` (what a component implements, control-by-control)
and `system-security-plan` (the full authorization package for a system,
including inherited controls, roles, boundaries, and POA&Ms).

This repo's own non-goals rule out the second: `Project.md` states plainly
"Not a real ATO. The compliance matrix maps controls; it does not claim
authorization." An SSP *is* the authorization artifact — generating one
would misrepresent what this project is. A component-definition makes a
narrower, true claim: "this component (the pipeline defined in this repo)
implements these controls, here's the evidence" — precisely the traceability
matrix's own claim, just machine-readable.

## Determinism: uuid5 + git-derived timestamp, not uuid4 + now()

The CI drift check (`generate → diff --exit-code`) only works if generating
from an unchanged `controls.yaml` produces byte-identical output every
time, on every machine. Two OSCAL fields are naturally non-deterministic by
default and had to be pinned:

- **UUIDs.** Every OSCAL object (`component-definition`, the one
  `component`, its `control-implementation`, each
  `implemented-requirement`) requires a UUID. `scripts/generate_compliance.py`
  uses `uuid.uuid5(NAMESPACE, stable_string)` — e.g. the control ID — instead
  of `uuid.uuid4()`. Same input, same UUID, forever; a real random UUID
  would make every regeneration look like drift even when nothing changed.
- **`metadata.last-modified`.** Using `datetime.now()` at generation time
  would fail the drift check on literally every CI run, since two runs a
  minute apart would disagree. Instead this is
  `git log -1 --format=%cI -- compliance/controls.yaml` — the commit
  timestamp of the source-of-truth file itself. This is deterministic for a
  given checked-out commit *and* semantically honest ("last modified" really
  does mean "when the source of truth last changed"). One caveat: on a
  shallow clone (GitHub Actions' default `fetch-depth: 1`), git can only see
  the tip commit, so this resolves to the tip commit's date rather than the
  actual last commit that touched the file if it's older — still
  deterministic per-commit, just less precise than GitLab CI's `GIT_DEPTH: 50`
  checkout. Acceptable for a portfolio project's audit trail; would need a
  deeper (or full) clone in CI to fix properly in a program that cared about
  the distinction.

## Library: compliance-trestle, not hand-built JSON

`compliance-trestle` ships Pydantic models generated directly from NIST's
published OSCAL JSON Schema (`trestle.oscal.component.ComponentDefinition`
and friends). Building the document by instantiating these models — rather
than assembling dicts and hoping the shape matches the schema — means the
output is schema-shaped by construction: a required field that's missing or
a value in the wrong place fails at generation time, not silently in CI two
steps later.

## Validation: trestle model round-trip, not `trestle validate` or `oscal-cli`

`Project.md` names two options: NIST's Java-based `oscal-cli`, or
`trestle validate`. Tried both against a real generated file before
picking:

- `trestle validate -f <file>` requires a full **trestle workspace**
  (a `.trestle/` root with the project laid out the way `trestle init`
  expects) — confirmed by running it directly against the generated JSON
  outside such a workspace: `ERROR: Given directory ... is not in a valid
  trestle root directory`. Restructuring this repo around trestle's
  workspace layout to validate one generated file is disproportionate.
- `oscal-cli` validates a standalone file directly, which is the right
  shape, but it's a Java tool — adding a JRE to an otherwise pure-Python
  generation/validation step for one CI stage didn't seem worth it.

Instead, `scripts/validate_oscal.py` parses the generated file back through
`ComponentDefinition.oscal_read(path)`. Since that model *is* the schema
(generated from the same JSON Schema `oscal-cli` validates against),
successful parsing is real schema validation, not a rubber stamp — confirmed
by deliberately deleting a required field (`control-id`) from a test file
and watching it fail with a precise Pydantic error pointing at the exact
missing path. This keeps the whole compliance stage dependency-light and
Python-only, consistent with the rest of this repo's tooling.

## How this maps to cATO / eMASS / Xacta in a real program

eMASS and Xacta both support importing OSCAL, and DoD's continuous-ATO
(cATO) push is explicitly about replacing point-in-time, hand-assembled
authorization packages with machine-readable artifacts that get
regenerated and re-validated on every change — the same shape as this
phase, just at program scale. In a real program, this generator's role
would be played by whatever the system-of-record is (a GRC tool, a
control-tracking spreadsheet with an export step, or a hand-maintained
YAML file like this one for a smaller program) feeding an OSCAL
`component-definition` per system component; eMASS/Xacta would ingest
those component-definitions and roll them up into the system's SSP. The
part of this phase that's a genuine miniature of that story, not just an
analogy, is the CI drift check: a control mapping that's out of sync with
its generated artifact is a build failure, not something a reviewer has to
notice by eye months later.

## Consequences

- `compliance/controls.yaml` is now the only file a human edits; both
  `docs/compliance-matrix.md` and `compliance/oscal/component-definition.json`
  are regenerated by `make compliance-gen` / `scripts/generate_compliance.py`
  and checked for drift in CI (`make compliance-check` runs the same check
  locally).
- Running the generator twice with no source changes produces byte-identical
  output (verified locally) — the determinism design holds in practice, not
  just in theory.
- If a future program wanted to swap in real `oscal-cli` validation (e.g. to
  match an eMASS/Xacta ingestion pipeline's own validation step exactly),
  only `scripts/validate_oscal.py` and the CI stage's last step would need
  to change — the generation logic and its determinism guarantees are
  unaffected.
