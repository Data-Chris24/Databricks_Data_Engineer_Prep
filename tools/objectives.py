"""Shared loading for the objective maps.

The YAML files under content/objectives/ are the single source of truth for both
exams. Everything else - rendered docs, question links, assignment coverage - is
derived from them, so this module is the one place that knows their shape.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
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


@dataclass
class Section:
    id: str
    number: int
    title: str
    weighting_pct: int
    exam: str
    objectives: list[Objective] = field(default_factory=list)
    groups: list[str] = field(default_factory=list)


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

    @property
    def objectives(self) -> list[Objective]:
        return [o for s in self.sections for o in s.objectives]

    @property
    def total_weighting(self) -> int:
        return sum(s.weighting_pct for s in self.sections)


def load_exam(exam_id: str) -> Exam:
    path = OBJECTIVES_DIR / f"{exam_id}.yaml"
    raw = yaml.safe_load(path.read_text())
    meta = raw["exam"]

    exam = Exam(
        id=meta["id"],
        name=meta["name"],
        guide_version=str(meta["guide_version"]),
        retrieved=str(meta["retrieved"]),
        scored_items=meta["scored_items"],
        time_limit_minutes=meta["time_limit_minutes"],
        weighting_source=meta["weighting_source"],
        recommended_training=raw.get("recommended_training", {}),
        source_path=path,
    )

    for s in raw["sections"]:
        section = Section(
            id=s["id"],
            number=s["number"],
            title=s["title"],
            weighting_pct=s["weighting_pct"],
            exam=exam.id,
            groups=s.get("groups", []) or [],
        )
        for o in s["objectives"]:
            section.objectives.append(
                Objective(
                    id=o["id"],
                    text=" ".join(o["text"].split()),
                    section_id=section.id,
                    exam=exam.id,
                    group=o.get("group"),
                    lab_feasibility=o.get("free_edition_lab", DEFAULT_LAB_FEASIBILITY),
                    optional_classic_lab=bool(o.get("optional_classic_lab", False)),
                    verify_in_workspace=bool(o.get("verify_in_workspace", False)),
                    note=" ".join(o["note"].split()) if o.get("note") else None,
                )
            )
        exam.sections.append(section)

    return exam


def load_all() -> list[Exam]:
    return [load_exam(e) for e in EXAMS]


def objective_index() -> dict[str, Objective]:
    """Every objective keyed by its stable ID, across both exams."""
    return {o.id: o for exam in load_all() for o in exam.objectives}
