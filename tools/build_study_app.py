#!/usr/bin/env python3
"""Build the self-contained study app from the objective maps and question bank.

The YAML in content/ stays the single source of truth. This renders it into one
HTML file with the questions embedded, so the published page needs no backend and
works offline once loaded.

    python3 tools/build_study_app.py            # writes build/study.html
    python3 tools/build_study_app.py --stats    # coverage report only
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from objectives import REPO_ROOT, load_all  # noqa: E402

QUESTIONS_DIR = REPO_ROOT / "content" / "questions"
TEMPLATE = Path(__file__).resolve().parent / "templates" / "study.html"
OUT = REPO_ROOT / "build" / "study.html"


def collect() -> dict:
    exams = []
    all_objectives = {}

    for exam in load_all():
        sections = []
        for s in exam.sections:
            sections.append({
                "id": s.id,
                "number": s.number,
                "title": s.title,
                "weight": s.weighting_pct,
                "objectives": [
                    {"id": o.id, "text": o.text, "lab": o.lab_feasibility}
                    for o in s.objectives
                ],
            })
            for o in s.objectives:
                all_objectives[o.id] = {"section": s.id, "exam": exam.id}
        exams.append({
            "id": exam.id,
            "name": exam.name,
            "short": "Associate" if exam.id == "associate" else "Professional",
            "items": exam.scored_items,
            "minutes": exam.time_limit_minutes,
            "guide": exam.guide_version,
            "sections": sections,
        })

    questions = []
    for path in sorted(QUESTIONS_DIR.rglob("*.yaml")):
        doc = yaml.safe_load(path.read_text())
        for q in doc["questions"]:
            primary = q["objective_ids"][0]
            meta = all_objectives.get(primary)
            if not meta:
                raise SystemExit(f"{q['id']} references unknown objective {primary}")
            questions.append({
                "id": q["id"],
                "exam": meta["exam"],
                "section": meta["section"],
                "objectives": q["objective_ids"],
                "stem": q["stem"],
                "code": q.get("code"),
                "options": q["options"],
                "correct": q["correct"],
                "explanation": q["explanation"],
                "why": q.get("distractor_rationale", {}),
                "difficulty": q.get("difficulty", "application"),
                "provenance": q["provenance"],
                "tags": q.get("tags", []),
            })

    return {"exams": exams, "questions": questions}


def stats(data: dict) -> None:
    by_obj: dict[str, int] = {}
    for q in data["questions"]:
        for oid in q["objectives"]:
            by_obj[oid] = by_obj.get(oid, 0) + 1

    print(f"{len(data['questions'])} questions\n")
    for exam in data["exams"]:
        total_obj = sum(len(s["objectives"]) for s in exam["sections"])
        covered = sum(
            1 for s in exam["sections"] for o in s["objectives"] if by_obj.get(o["id"])
        )
        qs = sum(1 for q in data["questions"] if q["exam"] == exam["id"])
        print(f"{exam['short']}: {qs} questions | {covered}/{total_obj} objectives covered")
        for s in exam["sections"]:
            n = sum(1 for q in data["questions"] if q["section"] == s["id"])
            have = sum(1 for o in s["objectives"] if by_obj.get(o["id"]))
            bar = "#" * min(20, n)
            print(f"  {s['id']:9} {s['weight']:>3}%  {n:>3}q  obj {have}/{len(s['objectives'])}  {bar}")
        print()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stats", action="store_true", help="print coverage and exit")
    args = ap.parse_args()

    data = collect()

    if args.stats:
        stats(data)
        return 0

    if not TEMPLATE.exists():
        raise SystemExit(f"missing template: {TEMPLATE}")

    html = TEMPLATE.read_text().replace(
        "/*__DATA__*/null", json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html)
    kb = len(html) / 1024
    print(f"wrote {OUT.relative_to(REPO_ROOT)}  ({kb:.0f} KB, {len(data['questions'])} questions)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
