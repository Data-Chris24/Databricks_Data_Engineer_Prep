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

A learner on the last step should not have to scroll back to the top to see the
schema. Each step's markdown cell carries a hand-written contract marker naming
what that step must satisfy:

    # MAGIC <!-- contract: silver_sensor_readings: event_id, recorded_at; requirements: 2, 3 -->

and the sync writes that excerpt of the README right under the marker, between
`excerpt:begin` / `excerpt:end`. The marker is authored; the excerpt is
generated, so the README stays the only place the contract is written down. A
marker naming a table, column, requirement or text the README no longer has is
an error, which makes `--check` catch a README edit that orphans a step.
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
CONTRACT = re.compile(r"^# MAGIC <!-- contract:(.*?)-->\s*$")
EXCERPT_BEGIN = "# MAGIC <!-- excerpt:begin  generated from README.md by tools/sync_assignment_tasks.py; edit the README or the contract marker above, then re-run it -->"
EXCERPT_END = "# MAGIC <!-- excerpt:end -->"
EXCERPT_TITLE = "**What this step must satisfy** (from the contract at the top)"
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


class ContractError(ValueError):
    """A contract marker names something the README does not have."""


def _blocks(readme: str) -> list[tuple[str, list[str]]]:
    """The README as (kind, lines) blocks: heading, table or paragraph.

    Fenced code is skipped; a table indented under a list item stays part of the
    item's paragraph, since it belongs to that item.
    """
    blocks: list[tuple[str, list[str]]] = []
    cur: list[str] = []
    in_fence = False

    def flush() -> None:
        if cur:
            blocks.append(("table" if all(l.startswith("|") for l in cur) else "para", cur.copy()))
            cur.clear()

    for line in readme.splitlines():
        if line.startswith("```"):
            flush()
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if not line.strip():
            flush()
        elif re.match(r"^#{1,6} ", line):
            flush()
            blocks.append(("heading", [line]))
        elif cur and line.startswith("|") != cur[-1].startswith("|"):
            flush()
            cur.append(line)
        else:
            cur.append(line)
    flush()
    return blocks


def _names(text: str, key: str) -> bool:
    """Whether `text` names `key`.

    A key with a space is a phrase, matched case-insensitively against the text
    without its markdown. A bare key must equal a backticked name or its last
    dotted part, so `pro_s2_scans` does not also match `pro_s2_scans_bronze`.
    """
    if " " in key:
        return key.lower() in re.sub(r"[`*]", "", text).lower().replace("\n", " ")
    return any(key in (tok, tok.rsplit(".", 1)[-1]) for tok in re.findall(r"`([^`]+)`", text))


def _heading_text(line: str) -> str:
    return line.lstrip("#").strip()


def _cell(row: str) -> set[str]:
    """The names a table row answers to: its first cell, or that cell's
    backticked name and the name's last dotted part."""
    first = row.strip().strip("|").split("|")[0].strip()
    tok = re.match(r"`([^`]+)`", first)
    return {tok.group(1), tok.group(1).rsplit(".", 1)[-1]} if tok else {first}


def _table(blocks, key: str, columns: list[str]) -> list[str]:
    for i, (kind, lines) in enumerate(blocks):
        if kind != "table" or i == 0 or blocks[i - 1][0] == "table":
            continue
        label_kind, label = blocks[i - 1]
        if not _names("\n".join(label), key):
            continue
        rows = lines[2:]
        if columns:
            have = set().union(*map(_cell, rows))
            missing = [c for c in columns if c not in have]
            if missing:
                raise ContractError(f"table {key!r} has no row for {', '.join(missing)}")
            rows = [r for r in rows if _cell(r) & set(columns)]
        if label_kind == "heading":
            head = [f"**{_heading_text(label[0])}**"]
        elif columns:
            # The label may say "exactly this schema"; a few rows are not that.
            name = re.search(r"`([^`]+)`", "\n".join(label))
            head = [f"From **`{name.group(1)}`** (the full table is at the top):" if name
                    else "From the contract table (the full table is at the top):"]
        else:
            head = label
        return head + [""] + lines[:2] + rows
    raise ContractError(f"no table labelled {key!r}")


def _text(blocks, key: str) -> list[str]:
    for i, (kind, lines) in enumerate(blocks):
        if kind == "table" or not _names("\n".join(lines), key):
            continue
        if kind == "heading":
            level = len(lines[0]) - len(lines[0].lstrip("#"))
            out = [f"**{_heading_text(lines[0])}**"]
            for k, more in blocks[i + 1 :]:
                if k == "heading" and len(more[0]) - len(more[0].lstrip("#")) <= level:
                    break
                out += [""] + more
            return out
        out = list(lines)
        for k, more in blocks[i + 1 :]:
            if k != "para" or not more[0].startswith(">"):
                break
            out += [""] + more
        return out
    raise ContractError(f"no text naming {key!r}")


def requirements(readme: str) -> dict[int, list[str]]:
    """The numbered items under the README's Requirements heading, dedented."""
    m = re.search(r"^#+ Requirements\s*$", readme, re.M)
    if not m:
        return {}
    items: dict[int, list[str]] = {}
    current = None
    for line in readme[m.end():].splitlines():
        if re.match(r"^#{1,6} ", line):
            break
        item = re.match(r"^(\d+)\.\s+", line)
        if item:
            current = int(item.group(1))
            items[current] = [line[item.end():]]
            indent = item.end()
        elif current is not None:
            items[current].append(line[indent:] if line[:indent].strip() == "" else line.strip())
    return {n: _trim(lines) for n, lines in items.items()}


def _trim(lines: list[str]) -> list[str]:
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def excerpt(readme: str, spec: str) -> list[str]:
    """The README lines a contract marker asks for, in the marker's order.

    `spec` is `;`-separated items: `TABLE` (the whole table), `TABLE: col, col`
    (only those rows), `requirements: 2, 3`, or `text: KEY` (the paragraph or
    subsection naming KEY). TABLE and KEY are a backticked name or a phrase.
    """
    blocks = _blocks(readme)
    reqs = requirements(readme)
    out: list[str] = []
    for item in filter(None, (i.strip() for i in spec.split(";"))):
        name, _, rest = (p.strip() for p in item.partition(":"))
        args = [a.strip() for a in rest.split(",") if a.strip()]
        if name in ("requirement", "requirements"):
            for a in args:
                if not a.isdigit() or int(a) not in reqs:
                    raise ContractError(f"no requirement {a!r}")
                body = reqs[int(a)]
                out += [f"**Requirement {a}.** {body[0]}", *body[1:], ""]
            continue
        part = _text(blocks, rest) if name == "text" else _table(blocks, name, args)
        out += part + [""]
    return _trim(out)


def excerpt_lines(readme: str, spec: str) -> list[str]:
    lines = [EXCERPT_BEGIN, "# MAGIC", "# MAGIC " + EXCERPT_TITLE, "# MAGIC"]
    lines += [("# MAGIC " + l).rstrip() for l in excerpt(readme, spec)]
    return lines + [EXCERPT_END]


def with_excerpts(source: str, readme: str) -> str:
    """Rewrite the generated excerpt under every contract marker."""
    out: list[str] = []
    skipping = False
    for line in source.splitlines():
        if line == EXCERPT_BEGIN:
            skipping = True
        if skipping:
            skipping = line != EXCERPT_END
            continue
        out.append(line)
        m = CONTRACT.match(line)
        if m:
            out += excerpt_lines(readme, m.group(1))
    return "\n".join(out) + ("\n" if source.endswith("\n") else "")


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
    return with_excerpts(SEP.join(cells), body)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="exit 1 if any starter is stale")
    args = ap.parse_args()
    stale = []
    for section in sorted(p for p in ASSIGNMENTS.iterdir() if p.is_dir()):
        readme, starter = section / "README.md", section / "assignment.py"
        if not readme.exists() or not starter.exists():
            continue
        try:
            want = synced(starter.read_text(), readme.read_text())
        except ContractError as e:
            print(f"{starter.relative_to(ROOT)}: contract marker: {e}")
            return 1
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
