"""The layout that keeps answers away from the learner path (docs/authoring-guide.md).

Learners deploy their own fork as workspace admins, so these invariants are the
only thing standing between the assignment notebook and the reference solution:
graders live under grading/, solutions never enter a learner target, and the
assignment folder holds nothing but the task and the starter.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from objectives import load_all  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
SECTIONS = [s.id for exam in load_all() for s in exam.sections]
RESOURCES = REPO_ROOT / "bundle" / "resources"


@pytest.mark.parametrize("sid", SECTIONS)
def test_every_section_has_a_grader_with_tests_and_fixtures(sid):
    g = REPO_ROOT / "grading" / sid
    assert (g / "grade.py").exists(), f"{sid}: missing grading/{sid}/grade.py"
    assert list((g / "tests").glob("test_*.py")), f"{sid}: no tests under grading/{sid}/tests"
    assert (g / "expected.json").exists(), f"{sid}: missing grading/{sid}/expected.json"


@pytest.mark.parametrize("sid", SECTIONS)
def test_assignment_folder_holds_only_the_task_and_starter(sid):
    allowed = {"README.md", "assignment.py", "publish_summary.py"}
    present = {p.name for p in (REPO_ROOT / "notebooks" / "assignments" / sid).iterdir()}
    stray = present - allowed
    assert not stray, f"{sid}: {sorted(stray)} do not belong next to the assignment notebook"


@pytest.mark.parametrize("sid", SECTIONS)
def test_solutions_hold_no_fixtures(sid):
    assert not (REPO_ROOT / "solutions" / sid / "expected.json").exists()


def test_graders_read_fixtures_and_tests_from_their_own_folder():
    for grade in (REPO_ROOT / "grading").glob("*/grade.py"):
        text = grade.read_text()
        assert '"solutions"' not in text, f"{grade}: still reaches into solutions/"
        assert 'os.path.join(grading_dir, "expected.json")' in text, f"{grade}: fixture path"


def test_no_learner_target_job_references_solutions():
    for path in RESOURCES.glob("*.yml"):
        assert "solutions/" not in path.read_text(), (
            f"{path.name} references solutions/ - move it under bundle/resources/verify/"
        )


def test_verify_files_define_resources_only_under_the_verify_target():
    files = list((RESOURCES / "verify").glob("*.yml"))
    assert files, "no verify-target resource files"
    for path in files:
        doc = yaml.safe_load(path.read_text())
        assert set(doc) == {"targets"} and set(doc["targets"]) == {"verify"}, path.name
        jobs = doc["targets"]["verify"]["resources"]["jobs"]
        assert jobs, path.name


def test_learner_targets_exclude_solutions_from_sync():
    doc = yaml.safe_load((REPO_ROOT / "bundle" / "databricks.yml").read_text())
    for target in ("free", "staging"):
        excludes = ((doc["targets"][target].get("sync") or {}).get("exclude")) or []
        assert "../solutions/**" in excludes, f"target {target} would deploy solutions/"
    assert "verify" in doc["targets"]
    assert not (doc["targets"]["verify"].get("sync") or {}).get("exclude")


@pytest.mark.parametrize("sid", SECTIONS)
def test_each_section_has_a_grade_job_and_a_transplant_check(sid):
    key = sid.lower().replace("-", "_")
    free = "\n".join(p.read_text() for p in RESOURCES.glob("*.yml"))
    verify = "\n".join(p.read_text() for p in (RESOURCES / "verify").glob("*.yml"))
    assert f"grading/{sid}/grade.py" in free, f"{sid}: no grade job in a learner target"
    assert f"transplant_check_{key}:" in verify, f"{sid}: no transplant check in the verify target"
    assert f"transplant_check_{key}:" not in free


def test_graders_return_a_structured_result_to_the_app():
    for grade in (REPO_ROOT / "grading").glob("*/grade.py"):
        text = grade.read_text()
        sid = grade.parent.name
        assert "dbutils.notebook.exit(json.dumps(result))" in text, f"{grade}: no exit value"
        assert f'"section": "{sid}"' in text, f"{grade}: result names the wrong section"
        assert "/Volumes/" not in text, f"{grade}: still writes to a volume"


def test_app_binds_every_grading_job():
    doc = yaml.safe_load((RESOURCES / "de_prep_study_app.app.yml").read_text())
    app = doc["resources"]["apps"]["study_app"]
    env = {e["name"]: e.get("value") for e in app["config"]["env"]}
    jobs = {r["name"]: r["job"] for r in app["resources"] if "job" in r}
    for sid in SECTIONS:
        key = f"grade_{sid.lower().replace('-', '_')}"
        assert env.get(f"DATABRICKS_JOB_{key.upper()}") == f"${{resources.jobs.{key}.id}}", sid
        assert jobs.get(f"job_{key}", {}).get("permission") == "CAN_MANAGE_RUN", sid
