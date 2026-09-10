#!/usr/bin/env python3
"""Validate every content file in the repo. This is what CI runs.

Checks, in order of how badly they'd hurt if they broke:

  objectives  - YAML parses, weightings total 100%, IDs unique and well-formed
  questions   - match the JSON Schema, resolve to real objectives, one correct
                answer, IDs unique, section prefix agrees with the objective
  coverage    - reports objectives with no questions yet (a warning, not a failure,
                since the bank is built out incrementally)

Exit code is non-zero if any ERROR was found. Warnings never fail the build.

    python3 tools/validate_content.py
    python3 tools/validate_content.py --strict   # warnings become errors
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from objectives import (
    REPO_ROOT,
    VALID_LAB_FEASIBILITY,
    load_all,
    objective_index,
)

try:
    import jsonschema
    import yaml
except ImportError:  # pragma: no cover
    sys.exit(
        "Missing dependencies.\n"
        "  python3 -m venv .venv && .venv/bin/pip install -r tools/requirements.txt\n"
        "then re-run with .venv/bin/python"
    )

QUESTIONS_DIR = REPO_ROOT / "content" / "questions"
SCHEMA_PATH = QUESTIONS_DIR / "schema.json"

QUESTION_ID_RE = re.compile(r"^(?P<exam>[A-Z]+)-(?P<section>S\d+)-Q\d{3}$")

errors: list[str] = []
warnings: list[str] = []


def error(msg: str) -> None:
    errors.append(msg)


def warn(msg: str) -> None:
    warnings.append(msg)


def rel(p: Path) -> str:
    return str(p.relative_to(REPO_ROOT))


def check_objectives() -> None:
    seen: dict[str, str] = {}

    for exam in load_all():
        src = rel(exam.source_path)

        if exam.total_weighting != 100:
            error(f"{src}: section weightings total {exam.total_weighting}%, expected 100%")

        if not exam.sections:
            error(f"{src}: no sections defined")

        numbers = [s.number for s in exam.sections]
        if numbers != sorted(numbers):
            error(f"{src}: sections are not in ascending order: {numbers}")

        for section in exam.sections:
            if not section.objectives:
                error(f"{src}: section {section.id} has no objectives")

            for obj in section.objectives:
                if obj.id in seen:
                    error(f"{src}: duplicate objective ID {obj.id} (also in {seen[obj.id]})")
                seen[obj.id] = src

                if not obj.id.startswith(f"{section.id}-O"):
                    error(
                        f"{src}: objective {obj.id} does not belong to its section "
                        f"{section.id} by ID"
                    )

                if obj.lab_feasibility not in VALID_LAB_FEASIBILITY:
                    error(
                        f"{src}: {obj.id} has free_edition_lab="
                        f"{obj.lab_feasibility!r}, expected one of "
                        f"{list(VALID_LAB_FEASIBILITY)}"
                    )

                # A theory-only objective with no optional lab and no note is an
                # unexplained gap in coverage - say why, or give people a way to
                # practise it.
                if (
                    obj.lab_feasibility == "theory_only"
                    and not obj.optional_classic_lab
                    and not obj.note
                ):
                    warn(
                        f"{src}: {obj.id} is theory_only with no optional_classic_lab "
                        f"and no note explaining why"
                    )

                if len(obj.text) < 20:
                    error(f"{src}: {obj.id} text looks truncated: {obj.text!r}")

        print(
            f"  {exam.id:13} {len(exam.sections):2} sections, "
            f"{len(exam.objectives):2} objectives, "
            f"weightings {exam.total_weighting}%  [guide {exam.guide_version}]"
        )


def check_questions() -> dict[str, int]:
    schema = json.loads(SCHEMA_PATH.read_text())
    validator = jsonschema.Draft202012Validator(schema)
    objectives = objective_index()

    per_objective: dict[str, int] = defaultdict(int)
    seen_ids: dict[str, str] = {}
    primary_of: dict[str, str] = {}
    variants: list[tuple[str, str, str]] = []  # (src, qid, variant_of)
    total = 0

    files = sorted(QUESTIONS_DIR.rglob("*.yaml"))
    if not files:
        warn("no question files found under content/questions/")
        return per_objective

    for path in files:
        src = rel(path)
        try:
            doc = yaml.safe_load(path.read_text())
        except yaml.YAMLError as exc:
            error(f"{src}: YAML parse failed: {exc}")
            continue

        schema_errors = sorted(validator.iter_errors(doc), key=lambda e: e.path)
        if schema_errors:
            for e in schema_errors:
                loc = "/".join(str(p) for p in e.path) or "(root)"
                error(f"{src}: schema violation at {loc}: {e.message}")
            continue

        for q in doc["questions"]:
            total += 1
            qid = q["id"]

            if qid in seen_ids:
                error(f"{src}: duplicate question ID {qid} (also in {seen_ids[qid]})")
            seen_ids[qid] = src

            if q["correct"] not in q["options"]:
                error(
                    f"{src}: {qid} marks {q['correct']!r} correct but that option "
                    f"does not exist (has {sorted(q['options'])})"
                )

            for key in q.get("distractor_rationale", {}):
                if key not in q["options"]:
                    error(f"{src}: {qid} explains non-existent option {key!r}")
                if key == q["correct"]:
                    error(
                        f"{src}: {qid} lists the correct answer {key!r} under "
                        f"distractor_rationale"
                    )

            unknown = [o for o in q["objective_ids"] if o not in objectives]
            if unknown:
                error(f"{src}: {qid} references unknown objectives {unknown}")

            for oid in q["objective_ids"]:
                per_objective[oid] += 1

            primary_of[qid] = q["objective_ids"][0]
            if q.get("variant_of"):
                variants.append((src, qid, q["variant_of"]))

            # The ID's section prefix should agree with the primary objective, so
            # a question always files itself under the section it's really testing.
            m = QUESTION_ID_RE.match(qid)
            primary = q["objective_ids"][0]
            if m and primary in objectives:
                want = objectives[primary].section_id
                got = f"{m.group('exam')}-{m.group('section')}"
                if got != want:
                    error(
                        f"{src}: {qid} is filed under {got} but its primary objective "
                        f"{primary} belongs to {want}"
                    )

    # Variants: a concise rewrite of an existing question. The app groups a
    # question with its variants into one family and draws one per test, so the
    # link has to resolve, stay on the same primary objective, and be one level
    # deep (a variant of a variant would make "family" ambiguous).
    variant_ids = {qid for _, qid, _ in variants}
    for src, qid, target in variants:
        if target == qid:
            error(f"{src}: {qid} is a variant of itself")
        elif target not in primary_of:
            error(f"{src}: {qid} is a variant of unknown question {target}")
        else:
            if primary_of[target] != primary_of[qid]:
                error(
                    f"{src}: {qid} (primary {primary_of[qid]}) is a variant of {target} "
                    f"(primary {primary_of[target]}) - variants share their primary objective"
                )
            if target in variant_ids:
                error(
                    f"{src}: {qid} is a variant of {target}, which is itself a variant - "
                    f"point variant_of at the original question"
                )

    print(f"  {total} questions across {len(files)} file(s), {len(variants)} variant(s)")
    return per_objective


def check_coverage(per_objective: dict[str, int]) -> None:
    objectives = objective_index()
    uncovered = [oid for oid in objectives if per_objective.get(oid, 0) == 0]

    covered = len(objectives) - len(uncovered)
    pct = covered / len(objectives) * 100 if objectives else 0
    print(f"  {covered}/{len(objectives)} objectives have at least one question ({pct:.0f}%)")

    if uncovered:
        warn(f"{len(uncovered)} objectives have no questions yet")


def check_notebook_cells() -> None:
    """Every cell containing `# MAGIC` lines must declare its magic on the first line.

    A markdown cell whose `# MAGIC %md` header is missing is not a syntax error to
    Python - the MAGIC lines are just comments - so it deploys happily and renders
    prose as an empty code cell. Where the prose contains a character Python cannot
    parse, it fails at runtime instead, several cells from the real mistake.
    """
    roots = [REPO_ROOT / "notebooks", REPO_ROOT / "solutions"]
    checked = 0
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.py")):
            checked += 1
            for i, cell in enumerate(path.read_text().split("# COMMAND ----------")):
                lines = [ln for ln in cell.strip().splitlines() if ln.strip()]
                if i == 0 and lines and lines[0] == "# Databricks notebook source":
                    lines = lines[1:]
                if not lines:
                    continue
                if any(ln.startswith("# MAGIC") for ln in lines) and not lines[0].startswith("# MAGIC %"):
                    rel = path.relative_to(REPO_ROOT)
                    error(
                        f"{rel} cell {i}: has # MAGIC lines but no magic declaration "
                        f"(first line is {lines[0][:60]!r}) - add '# MAGIC %md'"
                    )
    print(f"  {checked} notebooks checked for missing cell magics")


ASSIGNMENT_LINK_RE = re.compile(r"assignments/(?P<sec>(?:ASSOC|PRO)-S\d+)/assignment\b")


def check_lesson_notebooks_link_to_assignment() -> None:
    """A lesson notebook must end by pointing at its section's assignment notebook.

    The study app sends learners from a section page into the lesson notebooks,
    and the last cell of each one is what carries them on to the assignment. Only
    sections that have a learner-facing `assignment.py` are checked, so a section
    whose starter has not been written yet is a warning, not an error.
    """
    lessons_root = REPO_ROOT / "notebooks" / "lessons"
    assignments_root = REPO_ROOT / "notebooks" / "assignments"
    prefix = {"associate": "ASSOC", "professional": "PRO"}
    checked = 0
    if not lessons_root.exists():
        return
    for exam_dir in sorted(p for p in lessons_root.iterdir() if p.is_dir()):
        pre = prefix.get(exam_dir.name)
        if not pre:
            continue
        for section_dir in sorted(p for p in exam_dir.iterdir() if p.is_dir()):
            sid = f"{pre}-{section_dir.name}"
            starter = assignments_root / sid / "assignment.py"
            notebooks = sorted(section_dir.glob("*.py"))
            if not starter.exists():
                if notebooks:
                    warn(f"{sid}: no assignment.py starter yet, lesson notebooks cannot link to it")
                continue
            for nb in notebooks:
                checked += 1
                cells = nb.read_text().split("# COMMAND ----------")
                last = cells[-1] if cells else ""
                m = ASSIGNMENT_LINK_RE.search(last)
                if not m:
                    error(
                        f"{rel(nb)}: last cell does not link to assignments/{sid}/assignment - "
                        f"add a closing '# MAGIC %md' cell with the link"
                    )
                elif m.group("sec") != sid:
                    error(f"{rel(nb)}: last cell links to {m.group('sec')}, expected {sid}")
    print(f"  {checked} lesson notebooks checked for an assignment link")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strict", action="store_true", help="treat warnings as errors"
    )
    args = parser.parse_args()

    print("objectives")
    check_objectives()

    print("questions")
    per_objective = check_questions()

    print("coverage")
    check_coverage(per_objective)

    print("notebooks")
    check_notebook_cells()
    check_lesson_notebooks_link_to_assignment()

    if warnings:
        print(f"\n{len(warnings)} warning(s):")
        for w in warnings:
            print(f"  WARN  {w}")

    if errors:
        print(f"\n{len(errors)} error(s):", file=sys.stderr)
        for e in errors:
            print(f"  ERROR {e}", file=sys.stderr)
        return 1

    if args.strict and warnings:
        print("\n--strict: warnings are errors", file=sys.stderr)
        return 1

    print("\nAll content valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
