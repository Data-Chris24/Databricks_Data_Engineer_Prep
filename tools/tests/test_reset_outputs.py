"""Every assignment declares what it produces, so a reset can drop exactly that."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from objectives import load_all  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
SECTIONS = [s.id for exam in load_all() for s in exam.sections]
FQN = re.compile(r"^workspace\.[a-z_]+\.[a-z0-9_]+$")


@pytest.mark.parametrize("sid", SECTIONS)
def test_outputs_manifest_names_only_products_of_the_assignment(sid):
    path = REPO_ROOT / "grading" / sid / "outputs.json"
    assert path.exists(), f"{sid}: missing grading/{sid}/outputs.json"
    doc = json.loads(path.read_text())
    objects = doc.get("tables", []) + doc.get("views", []) + doc.get("shares", []) + doc.get("recipients", [])
    assert objects, f"{sid}: a reset would drop nothing"
    for t in doc.get("tables", []) + doc.get("views", []):
        assert FQN.match(t), f"{sid}: {t} is not a fully qualified workspace.<schema>.<name>"
        assert "_assess" not in t, f"{sid}: {t} is an assess input and must never be dropped"
        assert "teach" not in t, f"{sid}: {t} looks like a lesson table"


@pytest.mark.parametrize("sid", SECTIONS)
def test_outputs_manifest_matches_what_the_tests_grade(sid):
    doc = json.loads((REPO_ROOT / "grading" / sid / "outputs.json").read_text())
    tests = "\n".join(p.read_text() for p in (REPO_ROOT / "grading" / sid / "tests").glob("*.py"))
    for t in doc.get("tables", []):
        assert t.split(".")[-1] in tests, f"{sid}: {t} is not referenced by the graded tests"


def test_reset_job_exists_and_is_bound_to_the_app():
    job = yaml.safe_load((REPO_ROOT / "bundle" / "resources" / "de_prep_reset_assignment.job.yml").read_text())
    r = job["resources"]["jobs"]["reset_assignment"]
    assert r["parameters"][0]["name"] == "section"
    assert r["tasks"][0]["notebook_task"]["notebook_path"].endswith("grading/reset_assignment.py")
    app = yaml.safe_load((REPO_ROOT / "bundle" / "resources" / "de_prep_study_app.app.yml").read_text())["targets"]["free"]["resources"]["apps"]["study_app"]
    env = {e["name"]: e.get("value") for e in app["config"]["env"]}
    assert env["DATABRICKS_JOB_RESET_ASSIGNMENT"] == "${resources.jobs.reset_assignment.id}"
    assert any(x.get("name") == "job_reset_assignment" and x["job"]["permission"] == "CAN_MANAGE_RUN" for x in app["resources"])


def test_reset_notebook_refuses_assess_inputs():
    text = (REPO_ROOT / "grading" / "reset_assignment.py").read_text()
    assert "refusing to drop an assess input" in text
    assert "DROP TABLE IF EXISTS" in text


def test_reset_notebook_accepts_a_list_of_sections():
    text = (REPO_ROOT / "grading" / "reset_assignment.py").read_text()
    assert 'split(",")' in text, "start-over resets every section in one run"
    assert "for section in sections" in text
