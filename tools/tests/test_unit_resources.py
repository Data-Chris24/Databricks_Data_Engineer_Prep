"""Every unit declares what it creates, so clean-up can remove exactly that."""

from __future__ import annotations

import fnmatch
import json
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from objectives import load_all  # noqa: E402
from unit_resources import (  # noqa: E402
    GROUPS,
    KINDS,
    RAW,
    Created,
    code_of,
    covers,
    created_by_notebooks,
    declared,
    load,
    scan_text,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
UNITS = [(s.id, "associate" if exam.id.startswith("assoc") else "professional") for exam in load_all() for s in exam.sections]
SECTIONS = [u for u, _ in UNITS]
PREP_SCHEMAS = ("workspace.de_prep", "workspace.de_prep_staging")


def test_exam_dirs_resolve():
    assert ("ASSOC-S1", "associate") in UNITS and ("PRO-S10", "professional") in UNITS


@pytest.mark.parametrize("sid", SECTIONS)
def test_resource_list_is_well_formed(sid):
    doc = load(sid)
    assert set(doc) - {"_comment"} == set(GROUPS), f"{sid}: groups must be exactly {GROUPS}"
    unit_catalogs = {r["name"] for r in declared(sid) if r["kind"] == "catalog"}
    for r in declared(sid):
        assert set(r) <= {"kind", "name", "optional", "transient", "group"}, f"{sid}: unknown field in {r}"
        assert r["kind"] in KINDS, f"{sid}: unknown kind {r['kind']}"
        name = r["name"]
        if r["kind"] in ("table", "view", "materialized_view", "function", "volume"):
            parts = name.split(".")
            assert len(parts) == 3, f"{sid}: {name} must be catalog.schema.name"
            assert ".".join(parts[:2]) in PREP_SCHEMAS or parts[0] in unit_catalogs, f"{sid}: {name} is outside the prep schemas"
            assert "*" not in name or (r["kind"] == "table" and name.endswith("*")), f"{sid}: only a table name may end in *"
        if r["kind"] in ("folder", "file"):
            assert name.startswith(RAW + "/") and name != RAW, f"{sid}: {name} must be inside the raw volume"
        assert name not in ("workspace", "workspace.de_prep", "workspace.de_prep.raw"), f"{sid}: {name} is shared by every unit"


@pytest.mark.parametrize("sid", SECTIONS)
def test_set_up_creates_something_and_marks_none_optional(sid):
    setup = load(sid)["setup"]
    assert [r for r in setup if not r.get("transient")], f"{sid}: set-up must create something the page can wait for"
    assert not any(r.get("optional") for r in setup), f"{sid}: every set-up resource gates the lessons"


@pytest.mark.parametrize("sid", SECTIONS)
def test_assignment_group_covers_what_a_reset_drops(sid):
    """outputs.json (the reset's list) for the section and its extras must be in the unit's list."""
    decl = declared(sid)
    for out in [REPO_ROOT / "grading" / sid / "outputs.json", *sorted((REPO_ROOT / "grading").glob(f"{sid}-*/outputs.json"))]:
        doc = json.loads(out.read_text())
        for t in doc.get("tables", []) + doc.get("views", []):
            assert covers(decl, Created("table", t, str(out))), f"{sid}: {t} from {out.name} is not declared"
        for kind in ("shares", "recipients"):
            for n in doc.get(kind, []):
                assert covers(decl, Created(kind[:-1], n, str(out))), f"{sid}: {kind[:-1]} {n} is not declared"
        for p in doc.get("paths", []):
            assert covers(decl, Created("path", p, str(out))), f"{sid}: path {p} is not declared"


@pytest.mark.parametrize("sid,exam_dir", UNITS)
def test_every_object_a_notebook_creates_is_declared(sid, exam_dir):
    decl = declared(sid)
    created = created_by_notebooks(sid, exam_dir)
    assert created, f"{sid}: the scanner found nothing; is the layout what unit_resources.py expects?"
    missing = sorted({str(c) for c in created if not covers(decl, c)})
    assert not missing, f"{sid}: add these to grading/{sid}/resources.json, or clean-up will never remove them:\n  " + "\n  ".join(missing)


def test_no_two_units_claim_the_same_object():
    owner: dict[tuple[str, str], str] = {}
    for sid in SECTIONS:
        for r in declared(sid):
            key = ("table" if r["kind"] in ("table", "view", "materialized_view") else r["kind"], r["name"])
            assert key not in owner, f"{r['name']} is declared by both {owner[key]} and {sid}"
            owner[key] = sid
    patterns = [(n, s) for (k, n), s in owner.items() if k == "table" and "*" in n]
    for (k, n), s in owner.items():
        for pat, ps in patterns:
            if k == "table" and n != pat and ps != s:
                assert not fnmatch.fnmatchcase(n, pat), f"{n} ({s}) matches {pat} ({ps})"


def test_extras_belong_to_their_section():
    """ASSOC-S2-AUTO-LOADER is part of the ASSOC-S2 unit, so it has no list of its own."""
    for d in (REPO_ROOT / "grading").iterdir():
        if d.is_dir() and d.name.count("-") > 1:
            assert not (d / "resources.json").exists(), f"{d.name}: declare it in its section's resources.json"


# ---------------------------------------------------------------------------
# The scanner itself
# ---------------------------------------------------------------------------


def test_scanner_ignores_markdown_cells_and_strips_magic():
    text = "# Databricks notebook source\n# MAGIC %md\n# MAGIC CREATE TABLE shown_only\n\n# COMMAND ----------\n\n# MAGIC %sql\n# MAGIC CREATE TABLE real_one AS SELECT 1\n"
    assert "shown_only" not in code_of(text)
    assert [c.name for c in scan_text(text, "x")] == ["workspace.de_prep.real_one"]


def test_scanner_resolves_constants_and_turns_unknowns_into_patterns():
    text = (
        'CATALOG = "workspace"\nT = f"{CATALOG}.de_prep.orders"\nA, B = "cat_a", "cat_b"\n'
        'df.write.saveAsTable(T)\nspark.sql(f"CREATE CATALOG {A}")\n'
        'for n in names:\n    q.toTable(f"al_lesson_{n}")\n'
        'spark.sql("GRANT CREATE FOREIGN CATALOG ON CONNECTION c TO x")\n'
        'w.recipients.create(name="partner")\n'
        'path = f"/Volumes/{CATALOG}/de_prep/raw/s9_teach/x.csv"\n'
    )
    got = {(c.kind, c.name) for c in scan_text(text, "x")}
    assert ("table", "workspace.de_prep.orders") in got
    assert ("catalog", "cat_a") in got
    assert ("table", "workspace.de_prep.al_lesson_*") in got
    assert ("recipient", "partner") in got
    assert ("path", RAW + "/s9_teach/x.csv") in got
    assert not any(n == "ON" for _, n in got)


def test_covers_matches_patterns_both_ways_and_parent_folders():
    decl = [
        {"kind": "table", "name": "workspace.de_prep.al_lesson_*"},
        {"kind": "table", "name": "workspace.de_prep_staging.s5_channel_summary"},
        {"kind": "folder", "name": RAW + "/pro_s2/teach"},
        {"kind": "catalog", "name": "pro_s8_teach"},
    ]
    assert covers(decl, Created("table", "workspace.de_prep.al_lesson_orders", ""))
    assert covers(decl, Created("table", "*.*.s5_channel_summary", ""))
    assert covers(decl, Created("path", RAW + "/pro_s2", ""))
    assert covers(decl, Created("path", RAW + "/pro_s2/teach/a.json", ""))
    assert covers(decl, Created("table", "pro_s8_teach.ops.shipments", ""))
    assert not covers(decl, Created("table", "workspace.de_prep.other", ""))
    assert not covers(decl, Created("path", RAW + "/s2_teach", ""))


# ---------------------------------------------------------------------------
# The job, its grant, and what the learner is told
# ---------------------------------------------------------------------------


def test_cleanup_job_exists_and_the_app_may_run_it():
    job = yaml.safe_load((REPO_ROOT / "bundle" / "resources" / "de_prep_cleanup_unit.job.yml").read_text())
    j = job["resources"]["jobs"]["cleanup_unit"]
    assert j["name"].startswith("[DE prep] Clean up a unit")
    assert [p["name"] for p in j["parameters"]] == ["sections", "tables"]
    assert j["tasks"][0]["notebook_task"]["notebook_path"].endswith("ops/cleanup_unit.py")
    assert len(j["tasks"]) == 1, "Free Edition runs at most 5 tasks at once; one task per run"
    grants = yaml.safe_load((REPO_ROOT / "bundle" / "resources" / "de_prep_study_app_job_grants.yml").read_text())
    perms = grants["targets"]["free"]["resources"]["jobs"]["cleanup_unit"]["permissions"]
    assert [p["level"] for p in perms] == ["CAN_MANAGE_RUN"]


def test_cleanup_never_touches_notebooks_and_keeps_shared_objects():
    text = (REPO_ROOT / "ops" / "cleanup_unit.py").read_text()
    assert "import_(" not in text and "starters.json" not in text, "clean-up must leave notebooks alone"
    for keep in ('"workspace.de_prep"', '"workspace.de_prep.raw"', "RAW}"):
        assert keep in text
    assert "DROP SHARE" in text.split("DROP TABLE")[0], "shares go before tables (PRO-S4)"
    assert "ALTER SHARE" in text and "BY_SHARES" in text
    assert "is_declared(t)" in text, "a declared table is never removed as a stray"


def test_set_up_grants_browse_so_the_app_can_see_what_exists():
    text = (REPO_ROOT / "notebooks" / "datasets" / "generate.py").read_text()
    assert "GRANT BROWSE ON CATALOG" in text
    assert '"resources.json"' in text


@pytest.mark.parametrize("sid", SECTIONS)
def test_assignment_readme_says_what_clean_up_removes(sid):
    readme = REPO_ROOT / "notebooks" / "assignments" / sid / "README.md"
    assert "Clean-up removes only" in readme.read_text(), f"{sid}: README needs the clean-up note next to its outputs"
