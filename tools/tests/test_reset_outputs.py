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
    objects = doc.get("tables", []) + doc.get("views", []) + doc.get("functions", []) + doc.get("shares", []) + doc.get("recipients", [])
    assert objects, f"{sid}: a reset would drop nothing"
    for t in doc.get("tables", []) + doc.get("views", []) + doc.get("functions", []):
        assert FQN.match(t), f"{sid}: {t} is not a fully qualified workspace.<schema>.<name>"
        assert "_assess" not in t, f"{sid}: {t} is an assess input and must never be dropped"
        assert "teach" not in t, f"{sid}: {t} looks like a lesson table"


@pytest.mark.parametrize("sid", SECTIONS)
def test_outputs_manifest_matches_what_the_tests_grade(sid):
    doc = json.loads((REPO_ROOT / "grading" / sid / "outputs.json").read_text())
    tests = "\n".join(p.read_text() for p in (REPO_ROOT / "grading" / sid / "tests").glob("*.py"))
    for t in doc.get("tables", []):
        assert t.split(".")[-1] in tests, f"{sid}: {t} is not referenced by the graded tests"


def test_reset_job_exists_and_the_app_may_run_it():
    job = yaml.safe_load((REPO_ROOT / "bundle" / "resources" / "de_prep_reset_assignment.job.yml").read_text())
    r = job["resources"]["jobs"]["reset_assignment"]
    assert r["parameters"][0]["name"] == "section"
    assert r["tasks"][0]["notebook_task"]["notebook_path"].endswith("grading/reset_assignment.py")
    grants = yaml.safe_load((REPO_ROOT / "bundle" / "resources" / "de_prep_study_app_job_grants.yml").read_text())
    perms = grants["targets"]["free"]["resources"]["jobs"]["reset_assignment"]["permissions"]
    assert [p["level"] for p in perms] == ["CAN_MANAGE_RUN"]


def test_reset_notebook_refuses_assess_inputs():
    text = (REPO_ROOT / "grading" / "reset_assignment.py").read_text()
    assert "refusing to drop an assess input" in text
    assert "DROP TABLE IF EXISTS" in text


def test_reset_drops_functions_after_the_tables_that_use_them():
    text = (REPO_ROOT / "grading" / "reset_assignment.py").read_text()
    assert "DROP FUNCTION IF EXISTS" in text
    assert text.index('outputs.get("tables"') < text.index('outputs.get("functions"')


@pytest.mark.parametrize("sid", SECTIONS)
def test_every_function_the_solution_creates_is_reset(sid):
    """A mask or filter the solution defines must be in outputs.json, or a reset leaves it behind."""
    import re
    sol = REPO_ROOT / "solutions" / sid / "solution.py"
    if not sol.exists():
        return
    made = set(re.findall(r"CREATE\s+(?:OR\s+REPLACE\s+)?FUNCTION\s+(?:workspace\.de_prep\.)?(\w+)", sol.read_text(), re.I))
    doc = json.loads((REPO_ROOT / "grading" / sid / "outputs.json").read_text())
    listed = {f.split(".")[-1] for f in doc.get("functions", [])}
    assert made <= listed, f"{sid}: reset would leave {sorted(made - listed)}"


def test_reset_notebook_accepts_a_list_of_sections():
    text = (REPO_ROOT / "grading" / "reset_assignment.py").read_text()
    assert 'split(",")' in text, "start-over resets every section in one run"
    assert "for section in sections" in text


def test_reset_notebook_restores_deployed_starters_from_the_build():
    text = (REPO_ROOT / "grading" / "reset_assignment.py").read_text()
    assert 'os.path.join(files_root, "app", "shared", "content", "starters.json")' in text
    assert "w.workspace.import_(" in text and "overwrite=True" in text


def test_nothing_in_the_repo_names_the_maintainer():
    """A fork must work for a stranger; no mechanism may key on one person."""
    import subprocess
    out = subprocess.run(
        ["git", "grep", "-l", "-i", "data" + "chris24", "--", ":!docs/local", ":!README.md", ":!docs/ci-cd.md", ":!tools/tests/test_reset_outputs.py"],
        cwd=REPO_ROOT, capture_output=True, text=True,
    ).stdout.split()
    assert out == [], f"maintainer identity appears in {out}"
