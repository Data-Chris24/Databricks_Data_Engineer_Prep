"""Shared loading for the objective maps.

The YAML files under content/objectives/ are the single source of truth for both
exams. Everything else - rendered docs, question links, assignment coverage - is
derived from them, so this module is the one place that knows their shape.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field, replace
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - dependency guidance is the point
    sys.exit(
        "PyYAML is required.\n"
        "  python3 -m venv .venv && .venv/bin/pip install pyyaml\n"
        "then re-run with .venv/bin/python"
    )

REPO_ROOT = Path(__file__).resolve().parent.parent
OBJECTIVES_DIR = REPO_ROOT / "content" / "objectives"

EXAMS = ("associate", "professional")

# A missing free_edition_lab tag means the objective is fully practisable on Free
# Edition. Only exceptions are annotated, so absence is a positive claim.
DEFAULT_LAB_FEASIBILITY = "full"
VALID_LAB_FEASIBILITY = ("full", "partial", "theory_only")


@dataclass
class ObjectiveRow:
    """One Type 2 row: the wording an objective had from one guide version
    until (not including) another. to_version None means it is current."""

    from_version: str
    to_version: str | None
    text: str

    def live_in(self, version: str) -> bool:
        return self.from_version <= version and (
            self.to_version is None or version < self.to_version
        )


@dataclass
class Objective:
    id: str
    text: str
    section_id: str
    exam: str
    group: str | None = None
    lab_feasibility: str = DEFAULT_LAB_FEASIBILITY
    optional_classic_lab: bool = False
    verify_in_workspace: bool = False
    note: str | None = None
    rows: list[ObjectiveRow] = field(default_factory=list)

    def row_in(self, version: str) -> ObjectiveRow | None:
        return next((r for r in self.rows if r.live_in(version)), None)


@dataclass
class GuideSection:
    """A numbered section as one guide version prints it, made of stable units."""

    number: int
    title: str
    weighting_pct: int
    units: list[str]


@dataclass
class GuideVersion:
    version: str
    retrieved: str
    scored_items: int
    weighting_source: str
    sections: list[GuideSection] = field(default_factory=list)


@dataclass
class Section:
    """A stable unit (PRO-S4, ...) as one guide version presents it: number,
    title and weighting come from the guide section it belongs to."""

    id: str
    number: int
    title: str
    weighting_pct: int
    exam: str
    objectives: list[Objective] = field(default_factory=list)
    groups: list[str] = field(default_factory=list)
    unit_title: str = ""


@dataclass
class Exam:
    id: str
    name: str
    guide_version: str
    retrieved: str
    scored_items: int
    time_limit_minutes: int
    weighting_source: str
    sections: list[Section] = field(default_factory=list)
    recommended_training: dict = field(default_factory=dict)
    source_path: Path | None = None
    versions: list[GuideVersion] = field(default_factory=list)
    # Every unit and every objective with its full history, whatever the version.
    units: dict[str, Section] = field(default_factory=dict)

    @property
    def objectives(self) -> list[Objective]:
        return [o for s in self.sections for o in s.objectives]

    @property
    def guide(self) -> GuideVersion:
        return next(v for v in self.versions if v.version == self.guide_version)

    @property
    def total_weighting(self) -> int:
        return sum(s.weighting_pct for s in self.guide.sections)

    @property
    def latest_version(self) -> str:
        return self.versions[-1].version


def _rows(o: dict, oldest: str) -> list[ObjectiveRow]:
    if "versions" in o:
        return [
            ObjectiveRow(
                from_version=str(r.get("from", oldest)),
                to_version=str(r["to"]) if r.get("to") else None,
                text=" ".join(r["text"].split()),
            )
            for r in o["versions"]
        ]
    return [
        ObjectiveRow(
            from_version=str(o.get("from", oldest)),
            to_version=str(o["to"]) if o.get("to") else None,
            text=" ".join(o["text"].split()),
        )
    ]


def load_exam(exam_id: str, as_of: str | None = None) -> Exam:
    """The objective map as of one guide version (default: the latest)."""
    path = OBJECTIVES_DIR / f"{exam_id}.yaml"
    raw = yaml.safe_load(path.read_text())
    meta = raw["exam"]

    versions = [
        GuideVersion(
            version=str(v["version"]),
            retrieved=str(v["retrieved"]),
            scored_items=v["scored_items"],
            weighting_source=v["weighting_source"],
            sections=[
                GuideSection(
                    number=g["number"],
                    title=g["title"],
                    weighting_pct=g["weighting_pct"],
                    units=list(g["units"]),
                )
                for g in v["sections"]
            ],
        )
        for v in raw["guide_versions"]
    ]
    oldest = versions[0].version
    as_of = str(as_of) if as_of else versions[-1].version
    guide = next((v for v in versions if v.version == as_of), None)
    if guide is None:
        raise ValueError(
            f"{exam_id} has no guide version {as_of!r}; "
            f"known: {[v.version for v in versions]}"
        )

    exam = Exam(
        id=meta["id"],
        name=meta["name"],
        guide_version=guide.version,
        retrieved=guide.retrieved,
        scored_items=guide.scored_items,
        time_limit_minutes=meta["time_limit_minutes"],
        weighting_source=guide.weighting_source,
        recommended_training=raw.get("recommended_training", {}),
        source_path=path,
        versions=versions,
    )

    for s in raw["sections"]:
        unit = Section(
            id=s["id"],
            number=0,
            title=s["title"],
            weighting_pct=0,
            exam=exam.id,
            groups=s.get("groups", []) or [],
            unit_title=s["title"],
        )
        for o in s["objectives"]:
            rows = _rows(o, oldest)
            unit.objectives.append(
                Objective(
                    id=o["id"],
                    text=rows[-1].text,
                    section_id=unit.id,
                    exam=exam.id,
                    group=o.get("group"),
                    lab_feasibility=o.get("free_edition_lab", DEFAULT_LAB_FEASIBILITY),
                    optional_classic_lab=bool(o.get("optional_classic_lab", False)),
                    verify_in_workspace=bool(o.get("verify_in_workspace", False)),
                    note=" ".join(o["note"].split()) if o.get("note") else None,
                    rows=rows,
                )
            )
        exam.units[unit.id] = unit

    # The sections of this version, in guide order: each unit the guide lists,
    # holding only the objectives with a row live in this version.
    for g in guide.sections:
        for uid in g.units:
            unit = exam.units.get(uid)
            if unit is None:
                continue  # reported by check_history
            live = []
            for o in unit.objectives:
                row = o.row_in(guide.version)
                if row:
                    live.append(replace(o, text=row.text))
            exam.sections.append(
                replace(
                    unit,
                    number=g.number,
                    title=g.title if len(g.units) == 1 else unit.unit_title,
                    weighting_pct=g.weighting_pct,
                    objectives=live,
                )
            )

    return exam


def check_history(exam: Exam) -> list[str]:
    """Problems with the versioned shape of one exam's map, as messages."""
    problems: list[str] = []
    known = [v.version for v in exam.versions]
    if known != sorted(known) or len(set(known)) != len(known):
        problems.append(f"guide_versions must be unique and oldest first: {known}")

    for v in exam.versions:
        listed = [u for g in v.sections for u in g.units]
        for uid in listed:
            if uid not in exam.units:
                problems.append(f"guide {v.version} lists unknown unit {uid}")
        if len(set(listed)) != len(listed):
            problems.append(f"guide {v.version} lists a unit in two sections")
        numbers = [g.number for g in v.sections]
        if numbers != list(range(1, len(numbers) + 1)):
            problems.append(f"guide {v.version} sections are not numbered 1..n: {numbers}")
        total = sum(g.weighting_pct for g in v.sections)
        if total != 100:
            problems.append(f"guide {v.version} weightings total {total}%, expected 100%")

    unit_versions = {
        uid: {v.version for v in exam.versions for g in v.sections if uid in g.units}
        for uid in exam.units
    }
    for unit in exam.units.values():
        if not unit_versions[unit.id]:
            problems.append(f"unit {unit.id} is in no guide version")
        for o in unit.objectives:
            for r in o.rows:
                for end in (r.from_version, r.to_version):
                    if end is not None and end not in known:
                        problems.append(f"{o.id}: {end!r} is not a guide version")
                if r.to_version is not None and r.to_version <= r.from_version:
                    problems.append(f"{o.id}: row ends ({r.to_version}) before it starts")
            for v in known:
                live = [r for r in o.rows if r.live_in(v)]
                if len(live) > 1:
                    problems.append(f"{o.id}: {len(live)} rows overlap in guide {v}")
                if live and v not in unit_versions[unit.id]:
                    problems.append(
                        f"{o.id} is live in guide {v}, which does not include {unit.id}"
                    )
    return problems


def load_all(as_of: dict[str, str] | None = None) -> list[Exam]:
    """Both exams, each as of its latest guide unless as_of names another."""
    return [load_exam(e, (as_of or {}).get(e)) for e in EXAMS]


def objective_index() -> dict[str, Objective]:
    """Every objective keyed by its stable ID, across both exams and all guide
    versions - an ID never changes meaning, so retired ones still resolve."""
    return {o.id: o for exam in load_all() for u in exam.units.values() for o in u.objectives}
