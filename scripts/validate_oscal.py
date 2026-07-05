#!/usr/bin/env python3
"""Validate compliance/oscal/component-definition.json against the official
OSCAL schema.

`trestle validate -f` requires a full trestle workspace layout, which is
disproportionate machinery for validating one generated artifact — see
docs/adr/0006-oscal-compliance-generation.md. Instead this parses the file
back through compliance-trestle's ComponentDefinition model, which is
generated directly from NIST's published OSCAL JSON Schema: parsing success
means the document is schema-valid, and a missing/malformed field raises a
pydantic validation error naming the exact path.
"""

from __future__ import annotations

import pathlib
import sys

import trestle.oscal.component as comp

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
OSCAL_JSON = REPO_ROOT / "compliance" / "oscal" / "component-definition.json"


def main() -> int:
    rel = OSCAL_JSON.relative_to(REPO_ROOT)
    try:
        comp.ComponentDefinition.oscal_read(OSCAL_JSON)
    except Exception as exc:
        print(f"OSCAL validation failed for {rel}:\n{exc}", file=sys.stderr)
        return 1
    print(f"{rel} is a valid OSCAL component-definition")
    return 0


if __name__ == "__main__":
    sys.exit(main())
