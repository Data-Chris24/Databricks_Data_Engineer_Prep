#!/usr/bin/env python3
"""Render the objective YAML into the markdown maps under docs/exam-guides/.

The YAML is the source of truth; these docs are generated so they can never drift
from it. `--check` verifies the committed docs match what the YAML would produce,
which is what CI runs.

    python3 tools/render_objectives.py            # write the docs
    python3 tools/render_objectives.py --check    # fail if they're stale
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from objectives import REPO_ROOT, Exam, load_all

OUT_DIR = REPO_ROOT / "docs" / "exam-guides"

GENERATED_BANNER = (
    "<!-- GENERATED FILE - do not edit by hand.\n"
    "     Source: content/objectives/{source}\n"
    "     Regenerate: python3 tools/render_objectives.py -->"
)

FEASIBILITY_LABEL = {
    "full": "Hands-on on Free Edition",
    "partial": "Partly hands-on on Free Edition",
    "theory_only": "Theory only on Free Edition",
}


def render(exam: Exam) -> str:
    lines: list[str] = []
    add = lines.append

    add(GENERATED_BANNER.format(source=exam.source_path.name))
    add("")
    add(f"# {exam.name}")
    add("")
    add(f"Official exam guide version **{exam.guide_version}**, retrieved {exam.retrieved}.")
    add(f"See [SOURCES.md](SOURCES.md) for the guide URL and the full exam facts.")
    add("")
    add(
        f"**{exam.scored_items} scored multiple-choice items · "
        f"{exam.time_limit_minutes} minutes.**"
    )
    add("")

    if exam.weighting_source == "certification_page":
        add(
            "> **On the weightings below:** this exam's guide PDF lists its sections "
            "*without* percentages. These come from the Databricks certification web "
            "page, so treat them as indicative rather than quoted."
        )
        add("")

    add("## Section weightings")
    add("")
    add("| # | Section | Weighting | Objectives |")
    add("| --- | --- | --- | --- |")
    for s in exam.sections:
        add(f"| {s.number} | {s.title} | {s.weighting_pct}% | {len(s.objectives)} |")
    add(f"| | **Total** | **{exam.total_weighting}%** | **{len(exam.objectives)}** |")
    add("")

    add("## Objectives")
    add("")
    for s in exam.sections:
        add(f"### Section {s.number}: {s.title} ({s.weighting_pct}%)")
        add("")
        if s.groups:
            add("Guide groups these objectives under:")
            for g in s.groups:
                add(f"- {' '.join(g.split())}")
            add("")
        for o in s.objectives:
            add(f"- **`{o.id}`** — {o.text}")
            flags = []
            if o.lab_feasibility != "full":
                flags.append(FEASIBILITY_LABEL[o.lab_feasibility])
            if o.optional_classic_lab:
                flags.append("optional classic-compute lab")
            if o.verify_in_workspace:
                flags.append("feasibility unverified")
            if flags:
                add(f"  - _{' · '.join(flags)}_")
            if o.note:
                add(f"  - {o.note}")
        add("")

    training = exam.recommended_training or {}
    if training:
        add("## Recommended training (from the guide)")
        add("")
        for label, key in (("Instructor-led", "instructor_led"), ("Self-paced", "self_paced")):
            items = training.get(key) or []
            if items:
                add(f"**{label}**")
                add("")
                for item in items:
                    add(f"- {item}")
                add("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify committed docs match the YAML instead of writing them",
    )
    args = parser.parse_args()

    stale: list[Path] = []
    for exam in load_all():
        target = OUT_DIR / f"{exam.id}-objectives.md"
        rendered = render(exam)

        if args.check:
            current = target.read_text() if target.exists() else ""
            if current != rendered:
                stale.append(target)
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered)
        print(f"wrote {target.relative_to(REPO_ROOT)}")

    if args.check:
        if stale:
            for p in stale:
                print(f"STALE: {p.relative_to(REPO_ROOT)}", file=sys.stderr)
            print(
                "\nRun: python3 tools/render_objectives.py",
                file=sys.stderr,
            )
            return 1
        print("objective docs are up to date")

    return 0


if __name__ == "__main__":
    sys.exit(main())
