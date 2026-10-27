"""What each unit (section) creates, as declared and as its notebooks actually do.

`grading/<SECTION>/resources.json` declares every Unity Catalog object and raw
volume path a unit creates, in three groups (setup, lesson, assignment). The
study app shows the list on the unit's start page and the `cleanup_unit` job
removes exactly what it names, so a table a notebook creates under a name the
list does not know would survive every clean-up and count towards the
100-tables-per-schema limit for ever.

`created_by_notebooks()` is the check: it reads a unit's notebooks
(generator, lessons, assignments and reference solutions) and returns the
objects they create, resolving the `{CATALOG}.{SCHEMA}.name` style f-strings
and the constants the notebooks assign names to. A name built from something it
cannot resolve (a loop variable) becomes a `*` pattern, which a declared
pattern must cover. Markdown cells are ignored: they show code, they do not run
it.

A name held in a loop variable (`for name in (...): saveAsTable(name)`) is
not seen at all; the app's "Not managed by the app" list is the net for those.

Not scanned: `solutions/<SECTION>/transplant_check.py`, a maintainer-only
script whose `<output>_backup` tables are dropped again by the script itself.
"""

from __future__ import annotations

import fnmatch
import json
import re
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW = "/Volumes/workspace/de_prep/raw"
GROUPS = ("setup", "lesson", "assignment")
KINDS = {"table", "view", "materialized_view", "function", "folder", "file", "volume", "catalog", "share", "recipient", "connection"}

# The unit a section's extra assignment (ASSOC-S2-AUTO-LOADER) belongs to.
EXTRA_RE = re.compile(r"^((?:ASSOC|PRO)-S\d+)-[A-Z0-9-]+$")


@dataclass(frozen=True)
class Created:
    kind: str  # table | function | catalog | share | recipient | connection | volume | path
    name: str
    source: str  # repo-relative file

    def __str__(self) -> str:
        return f"{self.kind} {self.name} ({self.source})"


def load(section: str) -> dict:
    return json.loads((REPO_ROOT / "grading" / section / "resources.json").read_text())


def declared(section: str) -> list[dict]:
    doc = load(section)
    return [dict(r, group=g) for g in GROUPS for r in doc.get(g, [])]


def unit_files(section: str, exam_dir: str) -> list[Path]:
    """Every notebook whose objects belong to the unit, extra assignments included."""
    number = section.split("-S")[1]
    files: list[Path] = []
    files += sorted((REPO_ROOT / "notebooks" / "lessons" / exam_dir / f"S{number}").rglob("*.py"))
    gen = REPO_ROOT / "notebooks" / "datasets" / f"generate_{section}.py"
    if gen.exists():
        files.append(gen)
    for base in (REPO_ROOT / "notebooks" / "assignments", REPO_ROOT / "solutions"):
        for d in sorted(base.glob(f"{section}*")):
            if d.name != section and not (EXTRA_RE.match(d.name) and EXTRA_RE.match(d.name).group(1) == section):
                continue
            files += [p for p in sorted(d.glob("*.py")) if p.name != "transplant_check.py"]
    return files


# ---------------------------------------------------------------------------
# Scanning
# ---------------------------------------------------------------------------

def code_of(text: str) -> str:
    """The notebook's executable text: markdown cells dropped, `# MAGIC` prefixes stripped."""
    out = []
    for cell in re.split(r"^# COMMAND -+\s*$", text, flags=re.M):
        lines = cell.strip("\n").splitlines()
        first = next((l for l in lines if l.strip() and l.strip() != "# Databricks notebook source"), "")
        if first.startswith("# MAGIC %md"):
            continue
        out.append("\n".join(re.sub(r"^# MAGIC ?", "", l) for l in lines))
    return "\n".join(out)


ASSIGN_RE = re.compile(r"""^\s*([A-Za-z_]\w*)\s*=\s*f?(["'])([^"'\n]+)\2\s*(?:#.*)?$""", re.M)
TUPLE_ASSIGN_RE = re.compile(r"""^\s*([A-Za-z_]\w*(?:\s*,\s*[A-Za-z_]\w*)+)\s*=\s*((?:["'][^"'\n]+["']\s*,?\s*)+)$""", re.M)
# What follows CREATE <kind> when the match is not a name: "GRANT CREATE FOREIGN
# CATALOG ON CONNECTION", "CREATE TABLE AS SELECT" quoted in an assertion.
KEYWORDS = {"ON", "AS", "USING", "LIKE", "IF"}
PLACEHOLDER_RE = re.compile(r"\{([A-Za-z_]\w*)[^{}]*\}")
NAME = r"""(`?[\w{}.`*]+`?)"""
SQL_RE = re.compile(
    r"\bCREATE\s+(?:OR\s+REPLACE\s+)?(?:TEMP(?:ORARY)?\s+)?"
    r"(TABLE|VIEW|MATERIALIZED\s+VIEW|STREAMING\s+TABLE|FUNCTION|SHARE|RECIPIENT|FOREIGN\s+CATALOG|CATALOG|CONNECTION|VOLUME|SCHEMA)"
    r"\s+(?:IF\s+NOT\s+EXISTS\s+)?" + NAME,
    re.I,
)
WRITE_RE = re.compile(r"""\.(saveAsTable|toTable|writeTo)\(\s*(f?(["'])([^"']+)\3|[A-Za-z_]\w*)""")
# The SDK route the PRO-S4 notebooks take for recipients (SQL cannot set the
# DATABRICKS authentication type with a sharing identifier).
SDK_RE = re.compile(r"""\.(recipients|shares|catalogs|connections)\.create\(\s*(?:name\s*=\s*)?(f?(["'])([^"']+)\3|[A-Za-z_]\w*)""")
PATH_RE = re.compile(r"/Volumes/workspace/de_prep/raw(/[^\s\"'`)<>:,]*)?")


def resolve(s: str, env: dict[str, str], depth: int = 0) -> str:
    """Substitute `{VAR}` from the notebook's own constants; anything unknown becomes `*`."""
    if depth > 5:
        return PLACEHOLDER_RE.sub("*", s)

    def sub(m: re.Match) -> str:
        v = env.get(m.group(1))
        return resolve(v, env, depth + 1) if v is not None else "*"

    return PLACEHOLDER_RE.sub(sub, s)


def qualify(name: str) -> str:
    """Three-part table name: the notebooks `USE workspace.de_prep` before bare names."""
    name = name.strip("`").replace("`", "")
    parts = name.split(".")
    if len(parts) == 1:
        return f"workspace.de_prep.{name}"
    if len(parts) == 2:
        return f"workspace.{name}"
    return name


def scan_text(text: str, source: str) -> list[Created]:
    code = code_of(text)
    env: dict[str, str] = {"CATALOG": "workspace", "SCHEMA": "de_prep"}
    for m in ASSIGN_RE.finditer(code):
        env.setdefault(m.group(1), m.group(3))
    for m in TUPLE_ASSIGN_RE.finditer(code):
        names = [n.strip() for n in m.group(1).split(",")]
        values = re.findall(r"""["']([^"']+)["']""", m.group(2))
        if len(names) == len(values):
            for n, v in zip(names, values):
                env.setdefault(n, v)
    found: list[Created] = []
    for m in SQL_RE.finditer(code):
        kind = re.sub(r"\s+", "_", m.group(1).lower())
        raw = resolve(m.group(2), env)
        if raw.strip("`*") == "" or raw == "..." or raw.upper() in KEYWORDS:
            continue
        if kind in ("view", "materialized_view", "streaming_table"):
            kind = "table"
        if kind == "foreign_catalog":
            kind = "catalog"
        if kind == "schema":
            continue  # schemas are prerequisites, never a unit's to remove
        name = qualify(raw) if kind in ("table", "function", "volume") else raw.strip("`")
        found.append(Created(kind, name, source))
    for m in WRITE_RE.finditer(code):
        arg = m.group(4) if m.group(4) is not None else env.get(m.group(2))
        if arg is None:
            continue  # a parameter or loop variable: nothing to resolve
        name = resolve(arg, env)
        if name.strip("*") == "":
            continue
        found.append(Created("table", qualify(name), source))
    for m in SDK_RE.finditer(code):
        arg = m.group(4) if m.group(4) is not None else env.get(m.group(2))
        if arg is not None and resolve(arg, env).strip("*"):
            found.append(Created(m.group(1).rstrip("s"), resolve(arg, env), source))
    expanded = PLACEHOLDER_RE.sub(lambda m: resolve(m.group(0), env), code)
    for m in PATH_RE.finditer(expanded):
        rest = (m.group(1) or "").rstrip("/.")
        if rest:
            found.append(Created("path", RAW + rest, source))
    return found


def created_by_notebooks(section: str, exam_dir: str) -> list[Created]:
    out: list[Created] = []
    for p in unit_files(section, exam_dir):
        out += scan_text(p.read_text(), str(p.relative_to(REPO_ROOT)))
    return out


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

TABLE_KINDS = ("table", "view", "materialized_view")


def covers(decl: list[dict], c: Created) -> bool:
    """Does the declared list name what the notebook creates?"""
    for r in decl:
        kind, name = r["kind"], r["name"]
        if c.kind == "table":
            # Either side may be a pattern: a declared `al_lesson_*`, or a name the
            # notebook builds in a loop (`{cat}.{schema}.s5_channel_summary`).
            if kind in TABLE_KINDS and (fnmatch.fnmatchcase(c.name, name) or fnmatch.fnmatchcase(name, c.name)):
                return True
            if kind == "catalog" and c.name.split(".")[0] == name:
                return True
        elif c.kind == "path":
            if kind in ("folder", "file") and (c.name == name or c.name.startswith(name + "/")):
                return True
            # A parent of declared folders (a generator wiping `raw/pro_s2` before
            # rebuilding `raw/pro_s2/teach` and `raw/pro_s2/assess`).
            if kind == "folder" and name.startswith(c.name + "/"):
                return True
            if kind == "volume" and c.name.startswith("/Volumes/" + name.replace(".", "/")):
                return True
        elif c.kind == "volume":
            if kind == "volume" and c.name == name:
                return True
        elif kind == c.kind and name == c.name:
            return True
        if c.kind == "function" and kind == "catalog" and c.name.split(".")[0] == name:
            return True
    return False

