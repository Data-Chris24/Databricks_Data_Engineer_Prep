#!/usr/bin/env python3
"""Validate the bundle without contacting a workspace.

`databricks bundle validate` cannot be used on pull requests: it always resolves
the current user via SCIM, so it needs working credentials. On a public repo,
pull requests from forks get no secrets, which would make that check fail for
every outside contributor - and handing credentials to a PR-triggered workflow on
a public repo is not something we want to do anyway.

So this does the part that can be done offline:

  * validates databricks.yml against the schema the CLI itself emits
    (`databricks bundle schema`, which needs no credentials)
  * checks the invariants this repo cares about

The authoritative `databricks bundle validate` still runs in deploy.yml,
with real credentials, before anything is deployed. This is the early warning; that
is the gate.

    python3 tools/validate_bundle.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
BUNDLE_DIR = REPO_ROOT / "bundle"
BUNDLE_FILE = BUNDLE_DIR / "databricks.yml"

EXPECTED_TARGETS = {"free", "classic"}

errors: list[str] = []
warnings: list[str] = []


def load_schema() -> dict | None:
    """Ask the CLI for the bundle schema. Explicitly runs with no credentials."""
    try:
        proc = subprocess.run(
            ["databricks", "bundle", "schema"],
            capture_output=True, text=True, cwd=BUNDLE_DIR,
        )
    except FileNotFoundError:
        warnings.append("databricks CLI not found - skipping schema validation")
        return None
    if proc.returncode != 0:
        warnings.append(f"could not obtain bundle schema: {proc.stderr.strip()[:200]}")
        return None
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        warnings.append(f"bundle schema was not valid JSON: {e}")
        return None


def main() -> int:
    if not BUNDLE_FILE.exists():
        print(f"missing {BUNDLE_FILE.relative_to(REPO_ROOT)}", file=sys.stderr)
        return 1

    raw = BUNDLE_FILE.read_text()

    try:
        doc = yaml.safe_load(raw)
    except yaml.YAMLError as e:
        print(f"databricks.yml is not valid YAML:\n{e}", file=sys.stderr)
        return 1

    # --- schema ---------------------------------------------------------
    schema = load_schema()
    if schema is not None:
        try:
            import jsonschema
        except ImportError:
            warnings.append("jsonschema not installed - skipping schema validation")
        else:
            validator = jsonschema.Draft202012Validator(schema)
            for err in sorted(validator.iter_errors(doc), key=lambda e: list(e.path)):
                loc = ".".join(str(p) for p in err.path) or "(root)"
                errors.append(f"schema: {loc}: {err.message}")

    # --- repo invariants ------------------------------------------------
    targets = doc.get("targets") or {}

    missing = EXPECTED_TARGETS - set(targets)
    if missing:
        errors.append(f"targets missing from databricks.yml: {sorted(missing)}")

    # A workspace URL must never be committed to this public repo, and
    # workspace.host cannot be parameterised (it resolves before variable
    # interpolation), so the only correct answer is to omit it entirely.
    for name, target in targets.items():
        host = ((target or {}).get("workspace") or {}).get("host")
        if host:
            errors.append(
                f"target '{name}' hardcodes workspace.host ({host!r}). "
                "Omit it - the host comes from the CLI profile or DATABRICKS_HOST."
            )

    defaults = [n for n, t in targets.items() if (t or {}).get("default")]
    if len(defaults) > 1:
        errors.append(f"more than one default target: {sorted(defaults)}")
    elif not defaults:
        warnings.append("no default target set")

    # Free Edition is serverless-only; a job cluster here would fail at deploy.
    if "job_clusters" in raw or "new_cluster" in raw:
        warnings.append(
            "found a cluster definition - Free Edition is serverless-only, so the "
            "'free' target must not define job clusters"
        )

    for pattern in doc.get("include") or []:
        if not list(BUNDLE_DIR.glob(pattern)):
            warnings.append(f"include pattern matches nothing yet: {pattern!r}")

    # --- report ---------------------------------------------------------
    for w in warnings:
        print(f"  WARN  {w}")
    for e in errors:
        print(f"  FAIL  {e}", file=sys.stderr)

    if errors:
        print(f"\n{len(errors)} problem(s) in the bundle.", file=sys.stderr)
        return 1

    n = sum(len(t or {}) for t in targets.values())
    print(f"\nBundle is structurally valid: {len(targets)} targets ({', '.join(sorted(targets))}).")
    print("Authoritative `bundle validate` runs in deploy.yml with real credentials.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
