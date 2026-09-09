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

    print(f"  {total} questions across {len(files)} file(s)")
    return per_objective


def check_coverage(per_objective: dict[str, int]) -> None:
    objectives = objective_index()
    uncovered = [oid for oid in objectives if per_objective.get(oid, 0) == 0]

    covered = len(objectives) - len(uncovered)
    pct = covered / len(objectives) * 100 if objectives else 0
    print(f"  {covered}/{len(objectives)} objectives have at least one question ({pct:.0f}%)")

    if uncovered:
        warn(f"{len(uncovered)} objectives have no questions yet")


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
