#!/usr/bin/env python3
"""Generate docs/compliance-matrix.md and compliance/oscal/component-definition.json
from compliance/controls.yaml.

Both outputs are derived, not authored. Do not hand-edit them — edit
compliance/controls.yaml and rerun this script (`make compliance-gen`). CI's
`compliance` stage reruns this generator and fails the pipeline if either
output differs from what's committed.

Regeneration must be byte-for-byte deterministic given an unchanged
controls.yaml: every OSCAL UUID is a uuid5 derived from a fixed namespace
plus a stable string, and metadata.last-modified is the git commit
timestamp of controls.yaml itself rather than "now" — otherwise every CI
run would produce a spurious diff. See docs/adr/0006-oscal-compliance-generation.md.
"""

from __future__ import annotations

import datetime
import pathlib
import subprocess
import sys
import uuid

import trestle.oscal.common as common
import trestle.oscal.component as comp
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
CONTROLS_YAML = REPO_ROOT / "compliance" / "controls.yaml"
MATRIX_MD = REPO_ROOT / "docs" / "compliance-matrix.md"
OSCAL_JSON = REPO_ROOT / "compliance" / "oscal" / "component-definition.json"

# Fixed once, never regenerated — every uuid5() below is derived from this
# plus a stable string, so the same control always gets the same UUID.
UUID_NAMESPACE = uuid.UUID("a679c1c8-b4a3-4f5c-9f0a-9d6c7e8b1f2a")

NIST_800_53_R5_CATALOG = (
    "https://csrc.nist.gov/extensions/nvd/nist-sp-800-53r5-resolved-profile-catalog.json"
)

MATRIX_INTRO = """# NIST 800-53 rev5 Compliance Matrix

Maps controls actually implemented in this repo to the file, pipeline
stage, or evidence artifact that backs them. This is not a claim of
authorization — see [`Project.md`](../Project.md)'s non-goals — it is a
traceability matrix: every row below links to something real you can open
and check for yourself. No row here describes a control this repo doesn't
actually enforce.

This table and [`compliance/oscal/component-definition.json`](../compliance/oscal/component-definition.json)
are both generated from [`compliance/controls.yaml`](../compliance/controls.yaml)
by [`scripts/generate_compliance.py`](../scripts/generate_compliance.py) —
see [ADR 0006](adr/0006-oscal-compliance-generation.md).
"""

NOT_MAPPED = """## What's deliberately not mapped

A few controls a full ATO package would require aren't mapped here because
this repo doesn't actually implement them, and `Project.md`'s own
non-goals rule out padding this table with aspirational rows:

- **AC-2 (Account Management)** — the app has no user accounts or auth to manage.
- **CP-9 (System Backup)** — no persistent production data store exists to back up (SQLite in a container `emptyDir`, by design — see Phase 4's `k8s/base/deployment.yaml`).
- **IR-\\* (Incident Response)** — no incident response process exists for a portfolio project; would be theater if mapped here.
"""


def load_controls() -> list[dict]:
    controls = yaml.safe_load(CONTROLS_YAML.read_text())
    for control in controls:
        for evidence in control["evidence"]:
            file_part = evidence["path"].split("#", 1)[0]
            if not (REPO_ROOT / file_part).exists():
                raise SystemExit(
                    f"compliance/controls.yaml: {control['control_id']} evidence path "
                    f"does not exist: {file_part}"
                )
    return controls


def docs_relative(path: str) -> str:
    base, _, frag = path.partition("#")
    rel = base[len("docs/") :] if base.startswith("docs/") else f"../{base}"
    return f"{rel}#{frag}" if frag else rel


def csf_url(control_id: str) -> str:
    family = control_id.split("-")[0].lower()
    return f"https://csf.tools/reference/nist-sp-800-53/r5/{family}/{control_id.lower()}/"


def render_markdown(controls: list[dict]) -> str:
    header = (
        "<!-- DO NOT EDIT: generated from compliance/controls.yaml by "
        "scripts/generate_compliance.py. Run `make compliance-gen`. -->\n\n"
    )
    rows = ["| Control ID | Control Name | Implementation | Evidence |", "| --- | --- | --- | --- |"]
    for control in controls:
        evidence_md = ", ".join(
            f"[{e['label']}]({docs_relative(e['path'])})" for e in control["evidence"]
        )
        rows.append(
            f"| [{control['control_id']}]({csf_url(control['control_id'])}) "
            f"| {control['control_name']} | {control['implementation']} | {evidence_md} |"
        )
    return "\n".join(
        [header + MATRIX_INTRO, "\n".join(rows), "", NOT_MAPPED]
    ) + "\n"


def controls_yaml_last_modified() -> datetime.datetime:
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%cI", "--", str(CONTROLS_YAML)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        stamp = result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        stamp = ""
    if not stamp:
        # Fresh checkout with no git history for this path (e.g. before the
        # first commit). Fixed fallback keeps regeneration deterministic.
        return datetime.datetime(2025, 1, 1, tzinfo=datetime.timezone.utc)
    return datetime.datetime.fromisoformat(stamp)


def build_oscal(controls: list[dict]) -> comp.ComponentDefinition:
    implemented_requirements = []
    for control in controls:
        # Hrefs are repo-root-relative (not resolved relative to this JSON
        # file's own directory) — this is data for tooling to resolve
        # against a known repo root, not a browsable Markdown link.
        links = [
            common.Link(
                href=e["path"],
                rel="evidence",
                text=e["label"].strip("`"),
            )
            for e in control["evidence"]
        ]
        implemented_requirements.append(
            comp.ImplementedRequirement(
                uuid=str(uuid.uuid5(UUID_NAMESPACE, f"implemented-requirement:{control['control_id']}")),
                control_id=control["control_id"].lower(),
                description=control["implementation"],
                links=links,
            )
        )

    control_implementation = comp.ControlImplementation(
        uuid=str(uuid.uuid5(UUID_NAMESPACE, "control-implementation:ato-in-a-pipeline")),
        source=NIST_800_53_R5_CATALOG,
        description="NIST 800-53 rev5 controls implemented by the ato-in-a-pipeline CI/CD pipeline",
        implemented_requirements=implemented_requirements,
    )

    component = comp.DefinedComponent(
        uuid=str(uuid.uuid5(UUID_NAMESPACE, "component:ato-in-a-pipeline")),
        type="process-procedure",
        title="ato-in-a-pipeline CI/CD pipeline",
        description=(
            "The secure software delivery pipeline (SAST, secrets scanning, "
            "vulnerability scanning, SBOM, signing, Kyverno admission policy, "
            "and drift detection) defined in this repository."
        ),
        control_implementations=[control_implementation],
    )

    metadata = common.Metadata(
        title="ato-in-a-pipeline Component Definition",
        last_modified=controls_yaml_last_modified(),
        version="1.0.0",
        oscal_version=comp.OSCAL_VERSION,
    )

    return comp.ComponentDefinition(
        uuid=str(uuid.uuid5(UUID_NAMESPACE, "component-definition:ato-in-a-pipeline")),
        metadata=metadata,
        components=[component],
    )


def main() -> int:
    controls = load_controls()

    MATRIX_MD.write_text(render_markdown(controls))

    oscal_model = build_oscal(controls)
    OSCAL_JSON.write_bytes(oscal_model.oscal_serialize_json_bytes(pretty=True) + b"\n")

    print(f"Generated {MATRIX_MD.relative_to(REPO_ROOT)} and {OSCAL_JSON.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
