"""The per-step contract excerpts tools/sync_assignment_tasks.py writes into starters.

A learner on the last step of an assignment should not have to scroll back to the
README cell for the schema. Each step's markdown cell names what it must satisfy
in a contract marker, and the sync copies that part of the README under it. These
tests pin the marker format, that a marker the README cannot satisfy is an error,
and that every starter in the repo is marked up and in sync.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sync_assignment_tasks as sync  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
SECTIONS = sorted(p for p in (REPO_ROOT / "notebooks" / "assignments").iterdir() if p.is_dir())

README = """\
# Assignment

## The output contract

Create **`workspace.de_prep.orders_clean`** with exactly this schema:

| Column | Type | Meaning |
|---|---|---|
| `order_id` | `STRING` | Unique |
| `amount` | `DOUBLE` | Currency units |
| `ordered_on` | `DATE` | |

**`workspace.de_prep.orders_clean_rejects`** — every row that could not be published.

| Column | Type |
|---|---|
| `order_id` | `STRING` |

### What `metric` must hold

| `finding` | `metric` |
|---|---|
| `dupes` | how many rows repeat |
| `skew` | the largest group's share |

**`flagged`** — a definition, not a column:

> true when the order was refunded.

### Requirements

1. **One row per order.**
2. **Retention differs by type:**

   | Type | Days |
   |---|---|
   | `a` | 30 |

3. Column order matters.

## Grading

Run the tests.
"""


def test_a_column_subset_keeps_readme_order_and_does_not_claim_to_be_the_schema():
    out = sync.excerpt(README, "orders_clean: ordered_on, order_id")
    assert out[0] == "From **`workspace.de_prep.orders_clean`** (the full table is at the top):"
    rows = [l for l in out if l.startswith("| `")]
    assert rows == ["| `order_id` | `STRING` | Unique |", "| `ordered_on` | `DATE` | |"]


def test_a_whole_table_keeps_its_readme_label():
    out = sync.excerpt(README, "orders_clean")
    assert out[0] == "Create **`workspace.de_prep.orders_clean`** with exactly this schema:"
    assert sum(l.startswith("| `") for l in out) == 3


def test_a_bare_name_does_not_match_a_longer_name_it_prefixes():
    out = sync.excerpt(README, "orders_clean_rejects")
    assert out[0].startswith("**`workspace.de_prep.orders_clean_rejects`**")
    assert sum(l.startswith("| `") for l in out) == 1


def test_a_table_under_a_heading_is_found_by_the_heading_and_rows_by_first_cell():
    out = sync.excerpt(README, "metric: skew")
    assert out[0] == "**What `metric` must hold**"
    assert out[-3:] == ["| `finding` | `metric` |", "|---|---|", "| `skew` | the largest group's share |"]


def test_a_phrase_key_matches_the_label_text():
    assert sync.excerpt(README, "exactly this schema: amount")[-1].startswith("| `amount`")


def test_requirements_keep_their_number_and_their_nested_table():
    out = sync.excerpt(README, "requirements: 2, 3")
    assert out[0] == "**Requirement 2.** **Retention differs by type:**"
    assert "| `a` | 30 |" in out, "a table nested in the item must be dedented, not dropped"
    assert out[-1] == "**Requirement 3.** Column order matters."


def test_text_brings_its_blockquote():
    out = sync.excerpt(README, "text: flagged")
    assert out == ["**`flagged`** — a definition, not a column:", "", "> true when the order was refunded."]


def test_text_on_a_heading_brings_the_subsection():
    out = sync.excerpt(README, "text: metric")
    assert out[0] == "**What `metric` must hold**"
    assert "| `dupes` | how many rows repeat |" in out
    assert not any("One row per order" in l for l in out), "it must stop at the next heading"


@pytest.mark.parametrize("spec", [
    "no_such_table",
    "orders_clean: no_such_column",
    "requirements: 9",
    "requirements: two",
    "text: nowhere in the readme",
])
def test_a_marker_the_readme_cannot_satisfy_is_an_error(spec):
    with pytest.raises(sync.ContractError):
        sync.excerpt(README, spec)


STARTER = """\
# Databricks notebook source
# MAGIC %md
# MAGIC # Header

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1 - write it
# MAGIC
# MAGIC <!-- contract: orders_clean: amount; requirements: 1 -->

# COMMAND ----------

# your code
"""


def test_the_excerpt_lands_under_the_marker_and_a_rerun_changes_nothing():
    once = sync.synced(STARTER, README)
    assert once.count(sync.EXCERPT_BEGIN) == 1
    begin = once.index(sync.EXCERPT_BEGIN)
    assert once.index("<!-- contract:") < begin < once.index("| `amount`", begin) < once.index(sync.EXCERPT_END)
    assert sync.synced(once, README) == once


def test_a_readme_edit_makes_the_starter_stale():
    once = sync.synced(STARTER, README)
    edited = README.replace("Currency units", "Currency units, not cents")
    assert sync.synced(once, edited) != once, "--check would pass a stale excerpt"


def test_removing_the_marker_removes_its_excerpt():
    once = sync.synced(STARTER, README)
    unmarked = re.sub(r"# MAGIC <!-- contract:.*-->\n", "", once)
    assert sync.EXCERPT_BEGIN not in sync.synced(unmarked, README)


def _md_cells(source: str) -> list[str]:
    tail = source.split(sync.HINTS_END, 1)[-1] if sync.HINTS_END in source else source.split(sync.END, 1)[-1]
    return [c for c in tail.split(sync.SEP) if "# MAGIC %md" in c]


@pytest.mark.parametrize("section", SECTIONS, ids=lambda p: p.name)
def test_every_step_of_every_starter_shows_its_contract(section):
    source = (section / "assignment.py").read_text()
    readme = (section / "README.md").read_text()
    assert sync.synced(source, readme) == source, "starter is stale: run tools/sync_assignment_tasks.py"
    steps = [c for c in _md_cells(source) if re.search(r"^# MAGIC ##", c, re.M)]
    assert steps, f"{section.name}: no step cells found"
    for cell in steps:
        heading = next(l for l in cell.splitlines() if l.startswith("# MAGIC ##"))
        assert any(sync.CONTRACT.match(l) for l in cell.splitlines()), (
            f"{section.name}: {heading!r} has no contract marker"
        )


@pytest.mark.parametrize("section", SECTIONS, ids=lambda p: p.name)
def test_the_last_step_shows_a_whole_schema_and_every_requirement(section):
    source = (section / "assignment.py").read_text()
    body, _ = sync.split_hints((section / "README.md").read_text())
    markers = [m.group(1) for l in source.splitlines() if (m := sync.CONTRACT.match(l))]
    items = [i.strip() for i in markers[-1].split(";") if i.strip()]
    tables = [i for i in items if not i.startswith(("requirement", "text:"))]
    assert any(":" not in t for t in tables), f"{section.name}: last step shows no whole table"
    shown = {int(n) for i in items if i.startswith("requirement")
             for n in i.split(":", 1)[1].split(",")}
    assert shown == set(sync.requirements(body)), f"{section.name}: last step omits requirements"
