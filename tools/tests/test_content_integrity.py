"""Tests for the content model itself.

These guard the invariants everything else assumes: objective IDs are stable and
unique, weightings add up, and questions resolve to real objectives with a sane
answer key. They run offline - no workspace, no credentials.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from objectives import (  # noqa: E402
    VALID_LAB_FEASIBILITY,
    load_all,
    objective_index,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
QUESTIONS_DIR = REPO_ROOT / "content" / "questions"

QUESTION_ID_RE = re.compile(r"^(?P<exam>[A-Z]+)-(?P<section>S\d+)-Q\d{3}$")


def all_questions():
    """Every question in the bank, paired with the file it came from."""
    for path in sorted(QUESTIONS_DIR.rglob("*.yaml")):
        doc = yaml.safe_load(path.read_text())
        for q in doc["questions"]:
            yield path, q


# --------------------------------------------------------------------------
# Objectives
# --------------------------------------------------------------------------


@pytest.mark.parametrize("exam", load_all(), ids=lambda e: e.id)
def test_weightings_total_100(exam):
    assert exam.total_weighting == 100


@pytest.mark.parametrize("exam", load_all(), ids=lambda e: e.id)
def test_sections_are_ordered_and_populated(exam):
    assert [s.number for s in exam.sections] == sorted(s.number for s in exam.sections)
    for section in exam.sections:
        assert section.objectives, f"{section.id} has no objectives"


def test_objective_ids_are_globally_unique():
    ids = [o.id for exam in load_all() for o in exam.objectives]
    duplicates = {i for i in ids if ids.count(i) > 1}
    assert not duplicates, f"duplicate objective IDs: {sorted(duplicates)}"


def test_objective_ids_match_their_section():
    for exam in load_all():
        for section in exam.sections:
            for obj in section.objectives:
                assert obj.id.startswith(f"{section.id}-O"), (
                    f"{obj.id} is filed under {section.id} but its ID disagrees"
                )


def test_lab_feasibility_values_are_valid():
    for obj in objective_index().values():
        assert obj.lab_feasibility in VALID_LAB_FEASIBILITY, (
            f"{obj.id} has unknown free_edition_lab={obj.lab_feasibility!r}"
        )


def test_theory_only_objectives_are_explained():
    """A theory-only objective must offer a way out, or say why there isn't one.

    Otherwise it's just a silent hole in the coverage.
    """
    for obj in objective_index().values():
        if obj.lab_feasibility == "theory_only":
            assert obj.optional_classic_lab or obj.note, (
                f"{obj.id} is theory_only with no optional lab and no explanation"
            )


# --------------------------------------------------------------------------
# Questions
# --------------------------------------------------------------------------


def test_question_bank_is_not_empty():
    assert list(all_questions()), "no questions found"


def test_question_ids_are_unique():
    seen: dict[str, Path] = {}
    for path, q in all_questions():
        assert q["id"] not in seen, (
            f"duplicate question ID {q['id']} in {path} and {seen[q['id']]}"
        )
        seen[q["id"]] = path


def test_correct_answer_exists_among_options():
    for path, q in all_questions():
        assert q["correct"] in q["options"], (
            f"{q['id']} marks {q['correct']!r} correct, but options are "
            f"{sorted(q['options'])}"
        )


def test_questions_reference_real_objectives():
    known = objective_index()
    for path, q in all_questions():
        unknown = [o for o in q["objective_ids"] if o not in known]
        assert not unknown, f"{q['id']} references unknown objectives {unknown}"


def test_question_id_section_matches_primary_objective():
    known = objective_index()
    for path, q in all_questions():
        m = QUESTION_ID_RE.match(q["id"])
        assert m, f"{q['id']} does not match the required ID format"
        primary = q["objective_ids"][0]
        expected = known[primary].section_id
        actual = f"{m.group('exam')}-{m.group('section')}"
        assert actual == expected, (
            f"{q['id']} is filed under {actual} but its primary objective "
            f"{primary} belongs to {expected}"
        )


def test_distractor_rationale_never_explains_the_correct_answer():
    for path, q in all_questions():
        for key in q.get("distractor_rationale", {}):
            assert key in q["options"], f"{q['id']} explains non-existent option {key}"
            assert key != q["correct"], (
                f"{q['id']} lists its correct answer {key} as a distractor"
            )


def _by_id():
    return {q["id"]: q for _, q in all_questions()}


def test_variant_targets_exist():
    by_id = _by_id()
    for path, q in all_questions():
        if q.get("variant_of"):
            assert q["variant_of"] in by_id, f"{q['id']} is a variant of unknown {q['variant_of']}"
            assert q["variant_of"] != q["id"], f"{q['id']} is a variant of itself"


def test_variant_shares_primary_objective():
    by_id = _by_id()
    for path, q in all_questions():
        target = q.get("variant_of")
        if target and target in by_id:
            assert by_id[target]["objective_ids"][0] == q["objective_ids"][0], (
                f"{q['id']} and its source {target} test different primary objectives"
            )


def test_variant_target_is_an_original():
    """No chains: a variant points at the original, so a family is one hop deep."""
    by_id = _by_id()
    for path, q in all_questions():
        target = q.get("variant_of")
        if target and target in by_id:
            assert not by_id[target].get("variant_of"), (
                f"{q['id']} is a variant of {target}, which is itself a variant"
            )


def test_attributed_questions_name_their_source():
    """official-sample and concept-inspired questions must carry a source_note.

    This is the copyright guardrail - see docs/authoring-guide.md.
    """
    for path, q in all_questions():
        if q["provenance"] in ("official-sample", "concept-inspired"):
            assert q.get("source_note"), (
                f"{q['id']} has provenance={q['provenance']} but no source_note"
            )


def test_questions_match_the_json_schema():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads((QUESTIONS_DIR / "schema.json").read_text())
    validator = jsonschema.Draft202012Validator(schema)

    for path in sorted(QUESTIONS_DIR.rglob("*.yaml")):
        doc = yaml.safe_load(path.read_text())
        errors = sorted(validator.iter_errors(doc), key=lambda e: e.path)
        assert not errors, (
            f"{path.name}: " + "; ".join(f"{list(e.path)}: {e.message}" for e in errors)
        )


# --------------------------------------------------------------------------
# Generated docs
# --------------------------------------------------------------------------


def test_rendered_objective_docs_are_current():
    """The markdown maps are generated - fail if someone edited them by hand."""
    from render_objectives import OUT_DIR, render

    for exam in load_all():
        target = OUT_DIR / f"{exam.id}-objectives.md"
        assert target.exists(), f"{target.name} has not been generated"
        assert target.read_text() == render(exam), (
            f"{target.name} is stale - run: python3 tools/render_objectives.py"
        )


def test_notebook_cell_magic_check_catches_a_missing_header(tmp_path, monkeypatch):
    """The check must fail a cell whose `# MAGIC %md` header is missing.

    This is the bug it exists for: prose without the magic deploys as a code cell,
    and only fails later, on whichever character Python cannot parse.
    """
    import validate_content as vc

    nb = tmp_path / "notebooks" / "lessons"
    nb.mkdir(parents=True)
    (nb / "broken.py").write_text(
        "# Databricks notebook source\n"
        "# MAGIC %md\n"
        "# MAGIC # fine\n\n"
        "# COMMAND ----------\n\n"
        "# MAGIC ## no magic declared — an em dash Python cannot parse\n"
    )
    (tmp_path / "solutions").mkdir()

    monkeypatch.setattr(vc, "REPO_ROOT", tmp_path)
    vc.errors.clear()
    vc.check_notebook_cells()
    assert any("no magic declaration" in e for e in vc.errors), vc.errors
    vc.errors.clear()


def test_notebook_cell_magic_check_passes_a_correct_notebook(tmp_path, monkeypatch):
    import validate_content as vc

    nb = tmp_path / "notebooks"
    nb.mkdir(parents=True)
    (nb / "ok.py").write_text(
        "# Databricks notebook source\n"
        "# MAGIC %md\n"
        "# MAGIC # heading\n\n"
        "# COMMAND ----------\n\n"
        "print('code')\n\n"
        "# COMMAND ----------\n\n"
        "# MAGIC %sql\n"
        "# MAGIC SELECT 1\n"
    )
    (tmp_path / "solutions").mkdir()

    monkeypatch.setattr(vc, "REPO_ROOT", tmp_path)
    vc.errors.clear()
    vc.check_notebook_cells()
    assert vc.errors == []


def _lesson_tree(tmp_path, last_cell: str, with_starter: bool = True):
    lesson = tmp_path / "notebooks" / "lessons" / "associate" / "S3"
    lesson.mkdir(parents=True)
    (lesson / "01_lesson.py").write_text(
        "# Databricks notebook source\n"
        "# MAGIC %md\n# MAGIC # A lesson\n\n"
        "# COMMAND ----------\n\n"
        "print('code')\n\n"
        "# COMMAND ----------\n\n"
        f"{last_cell}\n"
    )
    assignment = tmp_path / "notebooks" / "assignments" / "ASSOC-S3"
    assignment.mkdir(parents=True)
    if with_starter:
        (assignment / "assignment.py").write_text("# Databricks notebook source\n")


def test_lesson_notebook_link_check_fails_without_a_link(tmp_path, monkeypatch):
    import validate_content as vc

    _lesson_tree(tmp_path, "# MAGIC %md\n# MAGIC Done.")
    monkeypatch.setattr(vc, "REPO_ROOT", tmp_path)
    vc.errors.clear()
    vc.check_lesson_notebooks_link_to_assignment()
    assert any("does not link to assignments/ASSOC-S3/assignment" in e for e in vc.errors), vc.errors
    vc.errors.clear()


def test_lesson_notebook_link_check_passes_with_a_link(tmp_path, monkeypatch):
    import validate_content as vc

    _lesson_tree(
        tmp_path,
        "# MAGIC %md\n# MAGIC [Open the assignment](../../../assignments/ASSOC-S3/assignment)",
    )
    monkeypatch.setattr(vc, "REPO_ROOT", tmp_path)
    vc.errors.clear()
    vc.check_lesson_notebooks_link_to_assignment()
    assert vc.errors == []


def test_lesson_notebook_link_check_warns_when_no_starter_exists(tmp_path, monkeypatch):
    import validate_content as vc

    _lesson_tree(tmp_path, "# MAGIC %md\n# MAGIC Done.", with_starter=False)
    monkeypatch.setattr(vc, "REPO_ROOT", tmp_path)
    vc.errors.clear()
    vc.warnings.clear()
    vc.check_lesson_notebooks_link_to_assignment()
    assert vc.errors == []
    assert any("no assignment.py starter" in w for w in vc.warnings)
    vc.warnings.clear()
