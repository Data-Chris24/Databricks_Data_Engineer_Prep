"""Tests for the study app's content build (tools/build_app_content.py).

The app imports the JSON this script writes, so these guard the shape the app
relies on: every question has a family, notes carry a table of contents whose
anchors match what the client renders, sub-pages attach to their section, and
the committed files are current.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import build_app_content as bac  # noqa: E402
from objectives import load_all, objective_index  # noqa: E402


@pytest.fixture(scope="module")
def bundle():
    return bac.collect()


# --------------------------------------------------------------------------
# Slugs must match rehype-slug (github-slugger) in the client
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Joins — ASSOC-S3-O2", "joins--assoc-s3-o2"),
        ("Cleaning bronze into silver", "cleaning-bronze-into-silver"),
        ("1. DELTA_FAILED_TO_MERGE_FIELDS", "1-delta_failed_to_merge_fields"),
        ("COPY INTO (the simple case)", "copy-into-the-simple-case"),
        ("What's a checkpoint?", "whats-a-checkpoint"),
    ],
)
def test_slugify_matches_github_slugger(text, expected):
    assert bac.slugify(text) == expected


def test_slugger_dedupes_like_github_slugger():
    s = bac.Slugger()
    assert [s.slug("Joins"), s.slug("Joins"), s.slug("Joins")] == ["joins", "joins-1", "joins-2"]


def test_heading_text_strips_inline_markdown():
    assert bac.heading_text("Joins — `ASSOC-S3-O2`") == "Joins — ASSOC-S3-O2"
    assert bac.heading_text("**Bold** [link](x)") == "Bold link"


# --------------------------------------------------------------------------
# Questions
# --------------------------------------------------------------------------


def test_every_question_has_exam_section_and_family(bundle):
    known = objective_index()
    for q in bundle["questions.json"]:
        assert q["exam"] in ("associate", "professional")
        assert q["section"] == known[q["objectives"][0]].section_id
        assert q["family"], q["id"]


def test_families_never_exceed_questions_and_meta_agrees(bundle):
    qs = bundle["questions.json"]
    meta = bundle["meta.json"]
    for exam in ("associate", "professional"):
        fams = {q["family"] for q in qs if q["exam"] == exam}
        assert meta["families_per_exam"][exam] == len(fams)
        assert len(fams) <= sum(1 for q in qs if q["exam"] == exam)


def test_variant_family_resolves_to_the_root():
    """A variant's family is its source; a source's family is itself."""
    objectives = {"X-S1-O1": {"section": "X-S1", "exam": "associate"}}
    fake = {
        "questions": [
            {"id": "X-S1-Q001", "objective_ids": ["X-S1-O1"], "stem": "s", "options": {"A": "a"},
             "correct": "A", "explanation": "e", "provenance": "original"},
            {"id": "X-S1-Q002", "objective_ids": ["X-S1-O1"], "stem": "s", "options": {"A": "a"},
             "correct": "A", "explanation": "e", "provenance": "original",
             "variant_of": "X-S1-Q001"},
        ]
    }

    class FakePath:
        def read_text(self):
            return json.dumps(fake)

    original = bac.QUESTIONS_DIR
    try:
        bac.QUESTIONS_DIR = _SingleFileDir(FakePath())
        qs = bac.collect_questions(objectives)
    finally:
        bac.QUESTIONS_DIR = original
    assert {q["id"]: q["family"] for q in qs} == {"X-S1-Q001": "X-S1-Q001", "X-S1-Q002": "X-S1-Q001"}


class _SingleFileDir:
    def __init__(self, path):
        self._path = path

    def rglob(self, _pattern):
        return [self._path]


# --------------------------------------------------------------------------
# Notes
# --------------------------------------------------------------------------


def test_notes_carry_a_toc_with_resolvable_objectives(bundle):
    known = objective_index()
    notes = bundle["notes.json"]
    assert notes, "no section notes found"
    for sid, note in notes.items():
        assert note["markdown"], f"{sid} has no markdown"
        assert note["toc"], f"{sid} has no headings"
        for entry in note["toc"]:
            assert entry["anchor"] and entry["level"] in (2, 3)
            for oid in entry["objective_ids"]:
                assert oid in known, f"{sid}: unknown objective {oid} in heading"
                assert known[oid].section_id == sid, f"{sid}: heading references {oid}"


def test_s2_supplementary_note_is_a_subpage(bundle):
    """The bug this guards: build_study_app.py silently dropped nested notes."""
    s2 = bundle["notes.json"]["ASSOC-S2"]
    subs = {p["slug"]: p for p in s2["subpages"]}
    assert "errors-worth-meeting" in subs
    sub = subs["errors-worth-meeting"]
    assert sub["objective_ids"] == ["ASSOC-S2-O2", "ASSOC-S2-O3"]
    assert sub["toc"] and all(e["anchor"].startswith("errors-worth-meeting--") for e in sub["toc"])


def test_toc_anchors_are_unique_within_a_page(bundle):
    for sid, note in bundle["notes.json"].items():
        anchors = [e["anchor"] for e in note["toc"]]
        for sub in note["subpages"]:
            anchors += [e["anchor"] for e in sub["toc"]]
        assert len(anchors) == len(set(anchors)), f"{sid} has duplicate anchors"


def test_note_titles_drop_the_weight_suffix(bundle):
    for note in bundle["notes.json"].values():
        assert "%" not in note["title"]


# --------------------------------------------------------------------------
# Notebooks
# --------------------------------------------------------------------------


def test_every_section_lists_its_lesson_notebooks(bundle):
    nbs = bundle["notebooks.json"]
    for exam in load_all():
        for s in exam.sections:
            assert s.id in nbs
            assert nbs[s.id]["lessons"], f"{s.id} has no lesson notebooks"
            for nb in nbs[s.id]["lessons"]:
                assert not nb["path"].endswith(".py")
                assert (bac.REPO_ROOT / (nb["path"] + ".py")).exists()
                assert nb["title"] and "ASSOC-" not in nb["title"] and "PRO-" not in nb["title"]


def test_assignment_starter_and_grade_job_are_detected(bundle):
    nbs = bundle["notebooks.json"]
    assert nbs["ASSOC-S3"]["assignment"]["notebook"] == "notebooks/assignments/ASSOC-S3/assignment"
    assert nbs["ASSOC-S3"]["assignment"]["grade_job"] == "grade_assoc_s3"
    for sid, entry in nbs.items():
        starter = bac.REPO_ROOT / "notebooks" / "assignments" / sid / "assignment.py"
        assert (entry["assignment"]["notebook"] is not None) == starter.exists(), sid
        assert entry["assignment"]["grade_job"], f"{sid} has no grade job in the bundle"


# --------------------------------------------------------------------------
# Committed output
# --------------------------------------------------------------------------


def test_committed_app_content_is_current(bundle):
    stale = bac.check(bundle)
    assert not stale, f"{stale} are stale - run: python3 tools/build_app_content.py"


def test_check_reports_a_stale_file(tmp_path, bundle):
    bac.write(bundle, tmp_path)
    assert bac.check(bundle, tmp_path) == []
    (tmp_path / "meta.json").write_text("{}")
    assert bac.check(bundle, tmp_path) == ["meta.json"]


def test_content_version_is_stable_for_identical_input(bundle):
    assert bundle["meta.json"]["content_version"] == bac.collect()["meta.json"]["content_version"]
