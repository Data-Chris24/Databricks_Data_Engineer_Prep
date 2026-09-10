#!/usr/bin/env python3
"""Build the study app's content bundle from the YAML and markdown in content/.

The YAML objective maps, the question bank and the lesson notes stay the single
source of truth. This renders them into JSON under app/shared/content/, which the
app imports at build time. The JSON is committed so the remote app build needs no
Python and so a deployed app is reproducible from a commit; `--check` is what CI
runs to prove the committed files are current.

    python3 tools/build_app_content.py            # write app/shared/content/*.json
    python3 tools/build_app_content.py --check    # fail if the committed JSON is stale
    python3 tools/build_app_content.py --stats    # coverage report only
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from objectives import REPO_ROOT, load_all  # noqa: E402

QUESTIONS_DIR = REPO_ROOT / "content" / "questions"
LESSONS_DIR = REPO_ROOT / "content" / "lessons"
NOTEBOOKS_DIR = REPO_ROOT / "notebooks"
BUNDLE_RESOURCES = REPO_ROOT / "bundle" / "resources"
OUT_DIR = REPO_ROOT / "app" / "shared" / "content"

OUTPUTS = ("exams.json", "questions.json", "notes.json", "notebooks.json", "starters.json", "meta.json")

OBJECTIVE_RE = re.compile(r"\b(?:ASSOC|PRO)-S\d+-O\d+\b")
HEADING_RE = re.compile(r"^(#{1,4})\s+(.*?)\s*$")
EXAM_DIR = {"associate": "ASSOC", "professional": "PRO"}


# ---------------------------------------------------------------------------
# Slugs - must match what rehype-slug (github-slugger) produces in the client,
# because the table of contents links to the headings the client renders.
# ---------------------------------------------------------------------------


def slugify(text: str) -> str:
    """github-slugger's algorithm: lowercase, drop punctuation, spaces to hyphens."""
    lowered = text.lower()
    kept = re.sub(r"[^\w\s-]", "", lowered)
    return kept.replace(" ", "-")


class Slugger:
    """Per-document de-duplication, as github-slugger does with `-1`, `-2` suffixes."""

    def __init__(self) -> None:
        self.seen: dict[str, int] = {}

    def slug(self, text: str) -> str:
        base = slugify(text)
        n = self.seen.get(base, 0)
        self.seen[base] = n + 1
        return base if n == 0 else f"{base}-{n}"


def heading_text(raw: str) -> str:
    """Plain text of a markdown heading as the browser would see it."""
    text = re.sub(r"`([^`]*)`", r"\1", raw)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    return text.strip()


def toc_for(markdown: str, prefix: str = "") -> list[dict]:
    """H2/H3 entries with the anchor the client will give each heading."""
    slugger = Slugger()
    entries = []
    in_fence = False
    for line in markdown.splitlines():
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = HEADING_RE.match(line)
        if not m:
            continue
        level = len(m.group(1))
        text = heading_text(m.group(2))
        anchor = prefix + slugger.slug(text)
        if level in (2, 3):
            entries.append({
                "level": level,
                "text": OBJECTIVE_RE.sub("", text).replace(" — ", " ").rstrip(" ,—-"),
                "anchor": anchor,
                "objective_ids": OBJECTIVE_RE.findall(m.group(2)),
            })
    return entries


# ---------------------------------------------------------------------------
# Collectors
# ---------------------------------------------------------------------------


def collect_exams() -> tuple[list[dict], dict[str, dict]]:
    exams = []
    all_objectives: dict[str, dict] = {}
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
    return exams, all_objectives


def collect_questions(all_objectives: dict[str, dict]) -> list[dict]:
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
                "variant_of": q.get("variant_of"),
            })

    # A family is a question plus its variants. Test mode draws one member per
    # family, so a variant can never sit next to its source in the same test.
    by_id = {q["id"]: q for q in questions}
    for q in questions:
        root = q
        hops = 0
        while root.get("variant_of"):
            parent = by_id.get(root["variant_of"])
            if parent is None:
                raise SystemExit(f"{q['id']} is a variant of unknown question {root['variant_of']}")
            root = parent
            hops += 1
            if hops > 10:
                raise SystemExit(f"{q['id']}: variant_of chain does not terminate")
        q["family"] = root["id"]
    return questions


def section_from_stem(stem: str) -> str | None:
    m = re.fullmatch(r"(ASSOC|PRO)-S\d+", stem)
    return m.group(0) if m else None


def collect_notes(exams: list[dict]) -> dict[str, dict]:
    """Section notes keyed by section id, with sub-pages from S<n>/ folders."""
    known = {s["id"]: (e["id"], s) for e in exams for s in e["sections"]}
    notes: dict[str, dict] = {}

    for path in sorted(LESSONS_DIR.rglob("*.md")):
        rel = path.relative_to(LESSONS_DIR)
        parts = rel.parts  # e.g. ("associate", "ASSOC-S3.md") or ("associate", "S2", "x.md")
        if len(parts) < 2:
            continue
        exam_id = parts[0]
        prefix = EXAM_DIR.get(exam_id)
        if not prefix:
            raise SystemExit(f"{rel}: lessons must live under associate/ or professional/")

        if len(parts) == 2:
            sid = section_from_stem(path.stem)
            if sid is None or sid not in known:
                raise SystemExit(f"{rel}: file name must be a section id like {prefix}-S3.md")
            markdown = path.read_text()
            _, section = known[sid]
            notes.setdefault(sid, _empty_note(sid, exam_id, section))
            notes[sid]["markdown"] = markdown
            notes[sid]["toc"] = toc_for(markdown)
            first = next((ln for ln in markdown.splitlines() if ln.startswith("# ")), None)
            if first:
                title = heading_text(first[2:])
                notes[sid]["title"] = re.sub(r"\s+—\s+\d+%$", "", title)
            continue

        if len(parts) == 3:
            sid = f"{prefix}-{parts[1]}"
            if sid not in known:
                raise SystemExit(f"{rel}: folder {parts[1]} is not a section of the {exam_id} exam")
            markdown = path.read_text()
            _, section = known[sid]
            notes.setdefault(sid, _empty_note(sid, exam_id, section))
            slug = path.stem
            first = next((ln for ln in markdown.splitlines() if ln.startswith("# ")), None)
            objectives_line = next(
                (ln for ln in markdown.splitlines() if ln.startswith("**Objectives:**")), ""
            )
            notes[sid]["subpages"].append({
                "slug": slug,
                "title": heading_text(first[2:]) if first else slug,
                "objective_ids": OBJECTIVE_RE.findall(objectives_line),
                "markdown": markdown,
                "toc": toc_for(markdown, prefix=f"{slug}--"),
            })
            continue

        raise SystemExit(f"{rel}: lessons nest at most one folder deep")

    # A section with only sub-pages and no main note is a content error: the
    # page would have nothing to put the sub-page under.
    for sid, note in notes.items():
        if note["markdown"] is None:
            raise SystemExit(f"{sid} has sub-pages but no {sid}.md")
    return dict(sorted(notes.items()))


def _empty_note(sid: str, exam_id: str, section: dict) -> dict:
    return {
        "section_id": sid,
        "exam": exam_id,
        "title": section["title"],
        "weight": section["weight"],
        "markdown": None,
        "toc": [],
        "subpages": [],
    }


def notebook_title(path: Path) -> str:
    """The notebook's H1, minus the objective list that usually trails it."""
    for line in path.read_text().splitlines():
        if line.startswith("# MAGIC # "):
            title = heading_text(line[len("# MAGIC # "):])
            if " — " in title:
                head, tail = title.split(" — ", 1)
                if OBJECTIVE_RE.search(tail):
                    title = head
            if " · " in title:
                # "PRO-S4 · Delta Sharing" -> "Delta Sharing"
                head, tail = title.split(" · ", 1)
                if re.fullmatch(r"(ASSOC|PRO)-S\d+", head.strip()):
                    title = tail
            title = OBJECTIVE_RE.sub("", title)
            return title.strip(" ,—-·")
    return path.stem


def grade_jobs() -> dict[str, str]:
    """Section id -> bundle job key that grades its assignment."""
    jobs: dict[str, str] = {}
    for path in sorted(BUNDLE_RESOURCES.glob("*.yml")):
        doc = yaml.safe_load(path.read_text()) or {}
        for key, job in (doc.get("resources", {}).get("jobs", {}) or {}).items():
            for task in job.get("tasks", []) or []:
                nb = (task.get("notebook_task") or {}).get("notebook_path", "")
                m = re.search(r"grading/((?:ASSOC|PRO)-S\d+)/grade\.py$", nb)
                if m and key.startswith("grade"):
                    jobs[m.group(1)] = key
    return jobs


def collect_notebooks(exams: list[dict]) -> dict[str, dict]:
    grade = grade_jobs()
    out: dict[str, dict] = {}
    for exam in exams:
        for s in exam["sections"]:
            sid = s["id"]
            number = sid.split("-S")[1]
            lesson_dir = NOTEBOOKS_DIR / "lessons" / exam["id"] / f"S{number}"
            lessons = []
            if lesson_dir.exists():
                for nb in sorted(lesson_dir.glob("*.py")):
                    lessons.append({
                        "path": str(nb.relative_to(REPO_ROOT).with_suffix("")),
                        "title": notebook_title(nb),
                    })
            assignment_dir = NOTEBOOKS_DIR / "assignments" / sid
            readme = assignment_dir / "README.md"
            starter = assignment_dir / "assignment.py"
            out[sid] = {
                "lessons": lessons,
                "assignment": {
                    "readme": str(readme.relative_to(REPO_ROOT)) if readme.exists() else None,
                    "notebook": str(starter.relative_to(REPO_ROOT).with_suffix("")) if starter.exists() else None,
                    "grade_job": grade.get(sid),
                },
            }
    return out


def collect_starters(exams: list[dict]) -> dict[str, list[dict]]:
    """Learner starter notebooks, embedded so the app can give each learner a copy.

    Every `.py` in an assignment folder is a starter (assignment.py, plus e.g.
    ASSOC-S5's publish_summary.py). The README is the task and stays a link.
    """
    out: dict[str, list[dict]] = {}
    for exam in exams:
        for s in exam["sections"]:
            folder = NOTEBOOKS_DIR / "assignments" / s["id"]
            starters = []
            if folder.exists():
                for nb in sorted(folder.glob("*.py")):
                    starters.append({"name": nb.stem, "source": nb.read_text()})
            out[s["id"]] = starters
    return out


def collect() -> dict[str, object]:
    exams, all_objectives = collect_exams()
    questions = collect_questions(all_objectives)
    notes = collect_notes(exams)
    notebooks = collect_notebooks(exams)
    starters = collect_starters(exams)

    families = {}
    for exam in exams:
        families[exam["id"]] = len({q["family"] for q in questions if q["exam"] == exam["id"]})

    digest = hashlib.sha256()
    digest.update(json.dumps([exams, questions, notes, notebooks, starters], sort_keys=True).encode())
    meta = {
        "content_version": digest.hexdigest()[:12],
        "question_count": len(questions),
        "families_per_exam": families,
        "notes_count": len(notes),
    }
    return {
        "exams.json": exams,
        "questions.json": questions,
        "notes.json": notes,
        "notebooks.json": notebooks,
        "starters.json": starters,
        "meta.json": meta,
    }


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def render_file(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, indent=1, sort_keys=False) + "\n"


def write(bundle: dict[str, object], out_dir: Path = OUT_DIR) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in OUTPUTS:
        (out_dir / name).write_text(render_file(bundle[name]))


def check(bundle: dict[str, object], out_dir: Path = OUT_DIR) -> list[str]:
    stale = []
    for name in OUTPUTS:
        target = out_dir / name
        if not target.exists() or target.read_text() != render_file(bundle[name]):
            stale.append(name)
    return stale


def stats(bundle: dict[str, object]) -> None:
    questions = bundle["questions.json"]
    notes = bundle["notes.json"]
    by_obj: dict[str, int] = {}
    for q in questions:
        for oid in q["objectives"]:
            by_obj[oid] = by_obj.get(oid, 0) + 1

    print(f"{len(questions)} questions, {len(notes)} section notes\n")
    for exam in bundle["exams.json"]:
        total_obj = sum(len(s["objectives"]) for s in exam["sections"])
        covered = sum(1 for s in exam["sections"] for o in s["objectives"] if by_obj.get(o["id"]))
        fam = bundle["meta.json"]["families_per_exam"][exam["id"]]
        gate = "test mode ON" if fam >= exam["items"] else f"test mode needs {exam['items']}"
        print(f"{exam['short']}: {fam} families | {covered}/{total_obj} objectives covered | {gate}")
        for s in exam["sections"]:
            n = sum(1 for q in questions if q["section"] == s["id"])
            have = sum(1 for o in s["objectives"] if by_obj.get(o["id"]))
            note = "notes" if s["id"] in notes else "-----"
            bar = "#" * min(20, n)
            print(f"  {s['id']:9} {s['weight']:>3}%  {n:>3}q  obj {have}/{len(s['objectives'])}  {note}  {bar}")
        print()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="fail if committed JSON is stale")
    ap.add_argument("--stats", action="store_true", help="print coverage and exit")
    args = ap.parse_args()

    bundle = collect()

    if args.stats:
        stats(bundle)
        return 0

    if args.check:
        stale = check(bundle)
        if stale:
            print(
                f"stale app content: {', '.join(stale)} - run: python3 tools/build_app_content.py",
                file=sys.stderr,
            )
            return 1
        print(f"app content is current ({OUT_DIR.relative_to(REPO_ROOT)})")
        return 0

    write(bundle)
    meta = bundle["meta.json"]
    print(
        f"wrote {OUT_DIR.relative_to(REPO_ROOT)}/  "
        f"({meta['question_count']} questions, {meta['notes_count']} notes, "
        f"version {meta['content_version']})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
