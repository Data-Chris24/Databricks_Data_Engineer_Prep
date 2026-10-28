"""Tests for versioned objective maps (tools/objectives.py) and guide fences.

Each exam guide Databricks publishes is a version of the map. These guard the
Type 2 rules: a version shows exactly the rows live in it, merged guide
sections keep their stable units, and history problems are reported rather
than silently loaded.
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import build_app_content as bac  # noqa: E402
import objectives  # noqa: E402
from objectives import check_history, load_all, load_exam  # noqa: E402

# Two guides: the second merges S2 into S1's section, rewords one objective,
# drops one and adds one.
TWO_GUIDES = """
exam:
  id: demo
  name: Demo exam
  time_limit_minutes: 60
guide_versions:
  - version: "2026-01-01"
    retrieved: "2026-01-02"
    scored_items: 10
    weighting_source: guide
    sections:
      - {number: 1, title: First, weighting_pct: 60, units: [D-S1]}
      - {number: 2, title: Second, weighting_pct: 40, units: [D-S2]}
  - version: "2026-06-01"
    retrieved: "2026-06-02"
    scored_items: 12
    weighting_source: guide
    sections:
      - {number: 1, title: Merged, weighting_pct: 100, units: [D-S1, D-S2]}
sections:
  - id: D-S1
    title: First unit
    objectives:
      - id: D-S1-O1
        text: An objective that never changes its wording.
      - id: D-S1-O2
        versions:
          - {from: "2026-01-01", to: "2026-06-01", text: The original wording of this one.}
          - {from: "2026-06-01", text: The reworded version of this one.}
      - id: D-S1-O3
        to: "2026-06-01"
        text: An objective the second guide dropped.
  - id: D-S2
    title: Second unit
    objectives:
      - id: D-S2-O1
        text: An objective present in both guides.
      - id: D-S2-O2
        from: "2026-06-01"
        text: An objective only the second guide has.
"""


@pytest.fixture
def demo(tmp_path, monkeypatch):
    def write(body: str) -> None:
        (tmp_path / "demo.yaml").write_text(textwrap.dedent(body))

    monkeypatch.setattr(objectives, "OBJECTIVES_DIR", tmp_path)
    write(TWO_GUIDES)
    return write


def ids(exam):
    return {s.id: [o.id for o in s.objectives] for s in exam.sections}


def test_default_is_the_latest_guide(demo):
    assert load_exam("demo").guide_version == "2026-06-01"


def test_each_version_shows_only_its_live_rows(demo):
    old = load_exam("demo", "2026-01-01")
    new = load_exam("demo", "2026-06-01")
    assert ids(old) == {"D-S1": ["D-S1-O1", "D-S1-O2", "D-S1-O3"], "D-S2": ["D-S2-O1"]}
    assert ids(new) == {"D-S1": ["D-S1-O1", "D-S1-O2"], "D-S2": ["D-S2-O1", "D-S2-O2"]}
    assert old.scored_items == 10 and new.scored_items == 12


def test_reworded_objective_keeps_its_id_and_shows_each_wording(demo):
    text = lambda e: next(o.text for o in e.objectives if o.id == "D-S1-O2")  # noqa: E731
    assert text(load_exam("demo", "2026-01-01")) == "The original wording of this one."
    assert text(load_exam("demo", "2026-06-01")) == "The reworded version of this one."


def test_guide_numbering_and_titles_come_from_the_version(demo):
    old = load_exam("demo", "2026-01-01")
    new = load_exam("demo", "2026-06-01")
    assert [(s.id, s.number, s.title) for s in old.sections] == [
        ("D-S1", 1, "First"),
        ("D-S2", 2, "Second"),
    ]
    # Merged: both units sit under section 1 and keep their own titles.
    assert [(s.id, s.number, s.title) for s in new.sections] == [
        ("D-S1", 1, "First unit"),
        ("D-S2", 1, "Second unit"),
    ]
    assert old.total_weighting == new.total_weighting == 100


def test_unknown_version_is_refused(demo):
    with pytest.raises(ValueError, match="no guide version"):
        load_exam("demo", "2025-01-01")


def test_retired_objectives_stay_in_the_units(demo):
    exam = load_exam("demo")
    assert "D-S1-O3" in [o.id for o in exam.units["D-S1"].objectives]
    assert check_history(exam) == []


@pytest.mark.parametrize(
    "change, message",
    [
        (("units: [D-S1, D-S2]", "units: [D-S1, D-S9]"), "unknown unit D-S9"),
        (("weighting_pct: 100", "weighting_pct: 90"), "total 90%"),
        (
            ('{from: "2026-06-01", text: The reworded', '{from: "2026-01-01", text: The reworded'),
            "rows overlap",
        ),
        (('to: "2026-06-01"\n        text: An objective the', 'to: "2026-03-01"\n        text: An objective the'), "not a guide version"),
    ],
)
def test_history_problems_are_reported(demo, change, message):
    old, new = change
    assert old in TWO_GUIDES
    demo(TWO_GUIDES.replace(old, new, 1))
    problems = check_history(load_exam("demo"))
    assert any(message in p for p in problems), problems


def test_objective_live_where_its_unit_is_not(demo):
    # D-S2 is only in the second guide, but this row claims the first too.
    body = TWO_GUIDES.replace(
        "      - {number: 2, title: Second, weighting_pct: 40, units: [D-S2]}\n",
        "",
    ).replace("weighting_pct: 60", "weighting_pct: 100")
    demo(body)
    problems = check_history(load_exam("demo"))
    assert any("does not include D-S2" in p for p in problems), problems


def test_real_maps_have_a_clean_history():
    for exam in load_all():
        assert check_history(exam) == [], exam.id


# --------------------------------------------------------------------------
# Guide fences in notes
# --------------------------------------------------------------------------

VERSIONS = ["2026-07-03", "2026-10-09"]


@pytest.mark.parametrize(
    "markdown",
    [
        "no fences at all",
        "a\n<!-- guide: to=2026-10-09 -->\nold\n<!-- /guide -->\nb",
        "<!-- guide: from=2026-10-09 -->new<!-- /guide -->",
        "<!-- guide: from=2026-07-03 to=2026-10-09 -->x<!-- /guide -->",
    ],
)
def test_valid_fences(markdown):
    bac.check_fences(markdown, "note.md", VERSIONS)


@pytest.mark.parametrize(
    "markdown, message",
    [
        ("<!-- guide: to=2026-10-09 -->never closed", "never closed"),
        ("stray <!-- /guide -->", "without an opening"),
        ("<!-- guide: to=2026-10-09 --><!-- guide: to=2026-10-09 -->", "inside the one"),
        ("<!-- guide: to=2025-01-01 -->x<!-- /guide -->", "not a guide version"),
        ("<!-- guide: until=2026-10-09 -->x<!-- /guide -->", "write <!-- guide:"),
        ("<!-- guide: from=2026-10-09 to=2026-07-03 -->x<!-- /guide -->", "ends before"),
    ],
)
def test_invalid_fences(markdown, message):
    with pytest.raises(SystemExit, match=message):
        bac.check_fences(markdown, "note.md", VERSIONS)


# --------------------------------------------------------------------------
# exams.json carries one snapshot per guide
# --------------------------------------------------------------------------


def test_latest_snapshot_matches_the_top_level():
    exams, _ = bac.collect_exams()
    for e in exams:
        assert [v["guide"] for v in e["versions"]] == sorted(v["guide"] for v in e["versions"])
        latest = e["versions"][-1]
        assert latest["guide"] == e["guide"]
        assert latest["items"] == e["items"]
        assert latest["sections"] == e["sections"]
