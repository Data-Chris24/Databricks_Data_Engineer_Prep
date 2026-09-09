# Databricks Data Engineer Prep

A hands-on learning platform for the **Databricks Certified Data Engineer
Associate** and **Professional** exams.

Built around one idea: you don't learn data engineering by reading about it, and
you don't prove you've learned it by following along with a worked example. So the
lessons teach on one dataset, and **the assignments hand you a structurally
different one** — you can't finish them by pasting the lesson's code. Then they're
graded.

Everything on the required path runs on a **free** Databricks workspace.

---

## Status

Early. The exam objective maps are complete and verified against the official
guides; content is being built section by section.

| | State |
| --- | --- |
| Objective maps (78 objectives, both exams) | ✅ Complete, traced to official guides |
| Free Edition feasibility analysis | ✅ Verified against a live workspace |
| Question bank | 🚧 14 official samples seeded, 15/78 objectives covered |
| Lessons, labs, assignments | 🚧 Starting with Associate Section 2 |
| Study app | 🚧 Platform viability proven, not yet built |

---

## What's in here

| Path | What it is |
| --- | --- |
| [`content/objectives/`](content/objectives/) | **Source of truth.** Every exam objective, quoted from the official guides, under a stable ID |
| [`docs/exam-guides/`](docs/exam-guides/) | Rendered objective maps + [where they came from](docs/exam-guides/SOURCES.md) |
| [`content/questions/`](content/questions/) | Question bank, linked to objectives by ID |
| `notebooks/lessons/` | Worked examples, on the `teach` datasets |
| `notebooks/assignments/` | Graded assignments, on the `assess` datasets |
| `notebooks/optional-classic/` | [Optional labs](docs/optional-classic-track.md) needing a paid/trial workspace |
| `grading/` | Unit-test harness + optional [AI reviewer](docs/grading.md) |
| [`tools/`](tools/) | Content validators + tests — CI runs these |
| [`bundle/`](bundle/) | Declarative Automation Bundle; deploy target for labs and the app |
| [`.github/workflows/`](.github/workflows/) | [CI/CD](docs/ci-cd.md): PR gate, auto-merge, deploy to Databricks |

Design decisions and their rationale: [`docs/architecture.md`](docs/architecture.md).

---

## Getting set up

### 1. A Databricks workspace

Sign up for **[Databricks Free Edition](https://www.databricks.com/learn/free-edition)**.
It's genuinely free — not a trial — and everything required here runs on it.

```bash
databricks auth login --host <your-workspace-url> --profile FREE
databricks auth profiles      # should show FREE, Valid: YES
```

Free Edition has real limits (serverless-only, one 2X-Small warehouse, 3 apps,
apps auto-stop after 24h). They're documented, along with exactly which objectives
they affect, in
[`docs/free-edition-constraints.md`](docs/free-edition-constraints.md).

### 2. Local tooling

```bash
python3 -m venv .venv
./.venv/bin/pip install -r tools/requirements.txt -r tools/requirements-dev.txt
./.venv/bin/python tools/validate_content.py
./.venv/bin/python -m pytest tools/tests -q
```

---

## How to study with this

1. **Start from the objective map** for your exam —
   [Associate](docs/exam-guides/associate-objectives.md) ·
   [Professional](docs/exam-guides/professional-objectives.md). Weightings tell you
   where the marks are: Associate Section 3 is 22% of the exam, Section 1 is 6%.
2. **Work the lesson** for a section, on the `teach` dataset.
3. **Do the assignment**, on the `assess` dataset. It won't accept the lesson's
   code — that's the point.
4. **Get graded.** Unit tests are authoritative; an [optional AI
   reviewer](docs/grading.md) adds feedback on your *approach* if you attach a model.
5. **Drill the questions** for that section, then move on.

---

## About the exams

| | Associate | Professional |
| --- | --- | --- |
| Scored items | 45 | 59 |
| Time | 90 min | 120 min |
| Fee | USD 200 | USD 200 |
| Validity | 2 years | 2 years |
| Guide version tracked | 2026-05-04 | 2026-07-03 |

Databricks revises these guides. Before booking, check the version you're studying
against the live one — [`docs/exam-guides/SOURCES.md`](docs/exam-guides/SOURCES.md)
explains how, and how to update the repo when it changes.

---

## Contributing

Pull requests are gated by [CI](docs/ci-cd.md): content validation, tests, bundle
validation and an approving review. **Every PR must add or change tests** — apply
the `no-tests-needed` label if a change genuinely can't have any.

[`docs/authoring-guide.md`](docs/authoring-guide.md) covers the contracts:
objective IDs are permanent, dataset pairs must differ structurally, and every
assignment must be gradeable by unit tests alone.

**Two hard rules:**

- **No real exam content.** Both exams are under NDA. Recalled questions never
  enter this repo — not in content, not in commit messages, not in issues.
- **No reworded third-party questions.** Lightly editing someone's paid-course
  question is still a derivative work. Take the *concept*, discard the wording, and
  write a new question from scratch.

---

## License

[GNU AGPL-3.0](LICENSE). Note the network clause: if you host a modified version
for others to use, you must offer them its source.

Exam objective text is quoted from the official Databricks exam guides for study
purposes and attributed in
[`docs/exam-guides/SOURCES.md`](docs/exam-guides/SOURCES.md). This project is not
affiliated with or endorsed by Databricks.
