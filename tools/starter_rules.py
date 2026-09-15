"""What a starter notebook may and may not contain.

A starter is the learner's blank: constants, the task text, one empty code cell
per requirement, and a self-check. It must never carry the solution, not even
commented out; a commented `.write.mode("overwrite").saveAsTable(TARGET)` with
one blank to fill is the answer with a fig leaf (found in eleven starters on
2026-09-15). Shared by the cleanup script and the layout test.
"""
from __future__ import annotations

import re

# A commented line that does work: transformations, reads, writes, SQL DDL.
CODE = re.compile(
    r"(\.write\.|saveAsTable|withColumn\(|\.filter\(|\.join\(|\.groupBy\(|\.select\(|Window\."
    r"|\bF\.\w+\(|spark\.sql\(|spark\.read|createDataFrame|\bCREATE |\bALTER |row_number|\blag\("
    r"|sha2|regexp_replace|left_anti|\.agg\(|\.count\(\)\s*-|\.distinct\(\)\.count\(\)\s*\*)"
)
# `name = ...` names the value the contract wants without showing how to get it.
PLACEHOLDER = re.compile(r"^\s*#\s*\w+\s*=\s*\.\.\.\s*$")
# Reading an output table back is a self-check, not a step.
SELF_CHECK = re.compile(r"^\s*#\s*(display|print)\(.*spark\.table\(")


def is_answer_line(line: str) -> bool:
    if not line.lstrip().startswith("#") or line.startswith("# MAGIC") or line.startswith("# COMMAND"):
        return False
    if PLACEHOLDER.match(line) or SELF_CHECK.match(line):
        return False
    return bool(CODE.search(line))


def offending_lines(source: str) -> list[tuple[int, str]]:
    body = source.split("task:end -->", 1)[-1] if "task:end -->" in source else source
    offset = source.count("\n", 0, source.find(body)) if body is not source else 0
    return [(offset + i + 1, l) for i, l in enumerate(body.splitlines()) if is_answer_line(l)]
