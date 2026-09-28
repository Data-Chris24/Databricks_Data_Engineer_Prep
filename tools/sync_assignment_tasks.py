#!/usr/bin/env python3
"""Embed each assignment's README.md into its assignment.py starter.

The learner's copy of a starter lives alone in a workspace folder the app
provisions; the README never travels with it, so "read README.md in this
folder" pointed at nothing. The task and output contract now sit in the
notebook's second cell, generated from the README between two markers so the
README stays the single source of truth. Run after editing any assignment
README; `--check` (used in CI) fails when a starter is stale.

The hints are pulled out of that cell and given one cell each. A README hides
them behind `<details>`, which GitHub renders as a disclosure triangle and a
Databricks markdown cell silently strips, so every hint and its answer used to
arrive as one wall of text with nothing marking which line was the question.
One cell per hint, its first line naming the problem it answers, lets a learner
read only the ones they want and collapse the rest (Databricks collapses a cell
to its first line, and a source-format notebook cannot ship one pre-collapsed).
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSIGNMENTS = ROOT / "notebooks" / "assignments"
SEP = "# COMMAND ----------\n"
BEGIN = "# MAGIC <!-- task:begin  generated from README.md by tools/sync_assignment_tasks.py; edit the README, then re-run it -->"
END = "# MAGIC <!-- task:end -->"
HINTS_BEGIN = "# MAGIC <!-- hints:begin  generated from README.md by tools/sync_assignment_tasks.py; edit the README, then re-run it -->"
HINTS_END = "# MAGIC <!-- hints:end -->"
HINTS_HEADING = re.compile(r"^##+ Hints\b.*$", re.M)
DETAILS = re.compile(r"<details>\s*<summary>(.*?)</summary>\s*(.*?)\s*</details>", re.S)
HEADER_LINE = "# MAGIC The task and the output contract are in the next cell (the same text as `README.md` in the repo)."
OLD_HEADER_LINES = (
    "# MAGIC Read `README.md` in this folder for the task and the output contract.",
    "# MAGIC Read `README.md` first. The contract there is what the tests check.",
    "# MAGIC Read `README.md` first. The table there is the contract.",
    "# MAGIC See `README.md` for the task and the output contract.",
)


def split_hints(readme: str) -> tuple[str, list[tuple[str, str]]]:
    """The README without its hints section, and the hints as (problem, answer).

    A hints section that is not made purely of `<details>` blocks is left where
    it is rather than half-converted.
    """
    m = HINTS_HEADING.search(readme)
    if not m:
        return readme, []
    hints = [(s.strip(), b.strip()) for s, b in DETAILS.findall(readme[m.end():])]
    if not hints or DETAILS.sub("", readme[m.end():]).strip():
        return readme, []
    return readme[: m.start()].rstrip("\n") + "\n", hints


def hint_cells(hints: list[tuple[str, str]]) -> list[str]:
    """One markdown cell per hint, each opening with the problem it answers."""
    if not hints:
        return []
    intro = "\n".join([
        "# MAGIC %md",
        HINTS_BEGIN,
        "# MAGIC #### Hints, if you want them",
        "# MAGIC",
        "# MAGIC One per cell below, each opening with the problem it answers, so you can"
        " read only the one you need. To put a hint away again, collapse its cell from the"
        " cell menu on its right - a collapsed cell shows its first line only.",
    ]) + "\n"
    cells = [intro]
    for i, (problem, answer) in enumerate(hints, 1):
        lines = ["# MAGIC %md", f"# MAGIC **Hint {i} - {problem}**", "# MAGIC"]
        lines += [("# MAGIC " + line).rstrip() for line in answer.splitlines()]
        if i == len(hints):
            lines.append(HINTS_END)
        cells.append("\n".join(lines) + "\n")
    return cells


def task_cell(readme: str) -> str:
    """The README as one markdown cell, headings demoted under the notebook's H1."""
    lines = ["# MAGIC %md", BEGIN]
    in_fence = False
    for line in readme.rstrip("\n").splitlines():
        if line.startswith("```"):
            in_fence = not in_fence
        if not in_fence and re.match(r"^#{1,5} ", line):
            line = "#" + line
        lines.append(("# MAGIC " + line).rstrip())
    lines.append(END)
    return "\n".join(lines) + "\n"


def synced(source: str, readme: str) -> str:
    body, hints = split_hints(readme)
    cell = task_cell(body)
    for old in OLD_HEADER_LINES:
        source = source.replace(old, HEADER_LINE)
    cells = source.split(SEP)

    # Drop a previously generated hints block before writing the current one.
    start = next((i for i, c in enumerate(cells) if HINTS_BEGIN in c), None)
    if start is not None:
        end = next((i for i, c in enumerate(cells) if HINTS_END in c), start)
        del cells[start : end + 1]

    at = next((i for i, c in enumerate(cells) if BEGIN in c), None)
    if at is None:
        # No task cell yet: it becomes the second cell, right after the header.
        at = 1
        cells.insert(at, "\n" + cell + "\n")
    else:
        cells[at] = "\n" + cell + "\n"
    for offset, hint in enumerate(hint_cells(hints), 1):
        cells.insert(at + offset, "\n" + hint + "\n")
    return SEP.join(cells)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="exit 1 if any starter is stale")
    args = ap.parse_args()
    stale = []
    for section in sorted(p for p in ASSIGNMENTS.iterdir() if p.is_dir()):
        readme, starter = section / "README.md", section / "assignment.py"
        if not readme.exists() or not starter.exists():
            continue
        want = synced(starter.read_text(), readme.read_text())
        if want != starter.read_text():
            stale.append(starter.relative_to(ROOT))
            if not args.check:
                starter.write_text(want)
    if args.check and stale:
        print("stale starters (run tools/sync_assignment_tasks.py):", *stale, sep="\n  ")
        return 1
    print(f"{'stale' if args.check else 'updated'}: {len(stale)} starter(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
