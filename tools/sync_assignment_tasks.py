#!/usr/bin/env python3
"""Embed each assignment's README.md into its assignment.py starter.

The learner's copy of a starter lives alone in a workspace folder the app
provisions; the README never travels with it, so "read README.md in this
folder" pointed at nothing. The task and output contract now sit in the
notebook's second cell, generated from the README between two markers so the
README stays the single source of truth. Run after editing any assignment
README; `--check` (used in CI) fails when a starter is stale.
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
HEADER_LINE = "# MAGIC The task and the output contract are in the next cell (the same text as `README.md` in the repo)."
OLD_HEADER_LINES = (
    "# MAGIC Read `README.md` in this folder for the task and the output contract.",
    "# MAGIC Read `README.md` first. The contract there is what the tests check.",
    "# MAGIC Read `README.md` first. The table there is the contract.",
    "# MAGIC See `README.md` for the task and the output contract.",
)


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
    cell = task_cell(readme)
    for old in OLD_HEADER_LINES:
        source = source.replace(old, HEADER_LINE)
    cells = source.split(SEP)
    for i, c in enumerate(cells):
        if BEGIN in c:
            cells[i] = "\n" + cell + "\n"
            return SEP.join(cells)
    # No task cell yet: it becomes the second cell, right after the header.
    cells.insert(1, "\n" + cell + "\n")
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
