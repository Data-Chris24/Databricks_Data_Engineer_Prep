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

Both exams are covered end to end: every section has notes, lessons, a graded
assignment and questions. Work now goes into depth and polish rather than gaps.

| | State |
| --- | --- |
| Objective maps (78 objectives, both exams) | ✅ Complete, traced to official guides |
| Free Edition feasibility analysis | ✅ Verified against a live workspace |
| Question bank | ✅ 197 questions covering all 78 objectives, each with near misses for Medium and Hard; some objectives have only one or two questions so far |
| Notes, lessons, assignments | ✅ All 17 sections, with interactive diagrams in the notes |
| Study app | ✅ Databricks App in [`app/`](app/): Learn + Test, practice and timed tests for both exams |

`python3 tools/validate_content.py` and `python3 tools/build_app_content.py --stats`
print the current coverage, so these numbers can be checked rather than trusted.

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
| `grading/` | Per-section graders, tests and fixtures the app runs, plus the optional [AI reviewer](docs/grading.md) |
| `solutions/` | Reference solutions and anti-transplant proofs. **Never deployed to a learner's workspace** (maintainer `verify` target only) |
| `ops/` | Housekeeping jobs the app runs for you, such as waking its database |
| [`tools/`](tools/) | Content validators + tests — CI runs these |
| [`app/`](app/) | The study app (AppKit + Lakebase): Learn, Practice, timed Test |
| [`bundle/`](bundle/) | Declarative Automation Bundle; deploys the labs and the app |
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

### 2. Capacity this needs

Free Edition counts some things per **account** or **metastore**, so a
workspace you already use may have spent part of what this repo needs. Check
before deploying:

```bash
python3 tools/preinstall_check.py --profile <PROFILE>
```

It reports PASS, WARN or FAIL for each row below and exits non-zero on a FAIL.
**FAIL** means `bundle deploy` would fail or the app could not work at all;
**WARN** means the deploy works but a particular unit would hit a limit later.
A re-deploy passes: the app, project and schemas this repo made count as its
own. Run before step 2 of [Deploy your own copy](#deploy-your-own-copy), it
fails on the missing Lakebase project and prints the command that creates it;
what matters then is that no *other* project holds the account's one slot. The
deploy workflow runs the same check before it deploys.

| Limit | Free Edition allows | This repo uses | If it is already used up |
| --- | --- | --- | --- |
| Apps | 3 per account | **1** (`de-prep-study`) | FAIL: delete an app you no longer need |
| Lakebase projects | 1 per account | **1** (`projects/de-prep`, the app's progress store) | FAIL: the app has no other place to store progress |
| Resources per app | 20 | 1 (the Lakebase database; jobs are granted, not bound) | - |
| Schemas | 50 per catalog | 2 in `workspace`: `de_prep`, `de_prep_staging` (ASSOC-S5) | FAIL |
| Tables | 100 per schema | `workspace.de_prep`: about a dozen per unit, 80-100 if every unit is set up at once | WARN: clean up finished units |
| Tables | 500 per metastore | the same tables, plus a few in PRO-S8's catalogs | WARN |
| Volumes | 50 per metastore | 2 (`de_prep.raw`, PRO-S4's files) | WARN |
| Catalogs | 50 per metastore | up to 4: PRO-S8 makes `pro_s8_teach`, `pro_s8_assess` and a demo; PRO-S4 a foreign catalog | WARN: only those units are affected |
| Shares / recipients / connections | 50 each per metastore | PRO-S4: 3 / 4 / 1 | WARN: only PRO-S4 is affected |
| SQL warehouses | 1, 2X-Small | uses the one you have (ASSOC-S2 JDBC, PRO-S4 federation) | WARN if it was deleted |
| Pipelines | 1 active per type | ASSOC-S3's materialized view needs one briefly | WARN if one is running |
| Concurrent job tasks | 5 | one unit's job at a time | jobs queue rather than fail |
| Jobs | no limit found | about 55, all named `[DE prep] …` | - |
| Service principals | no limit found | PRO-S8 creates 4 account-level ones | - |

Only one unit's tables need to exist at a time: set a unit up when you start
it and clean it up when you are done, which keeps `workspace.de_prep` well
under its 100-table limit even in a workspace you also use for other things.

To look for yourself, these are the commands the check runs:

```bash
databricks apps list --profile <PROFILE>                      # app slots: 3 per account
databricks postgres list-projects --profile <PROFILE>         # Lakebase: 1 per account
databricks warehouses list --profile <PROFILE>
databricks pipelines list-pipelines --profile <PROFILE>
databricks schemas list workspace --profile <PROFILE>
databricks tables list workspace de_prep --profile <PROFILE> -o json | jq length
# Unity Catalog counts against their limits: tables, volumes, catalogs, shares, ...
databricks resource-quotas list-quotas --profile <PROFILE> -o json \
  | jq -r '.[] | "\(.parent_securable_type) \(.quota_name) \(.quota_count)/\(.quota_limit)"'
```

`list-quotas` leaves out a schema that is well below its limit, so count
`workspace.de_prep` with `tables list` as above if it is missing there. Its
metastore rows name the metastore by its ID; the `jq` filter above leaves that
out, so the output is safe to paste into an issue.

### 3. Local tooling

```bash
python3 -m venv .venv
./.venv/bin/pip install -r tools/requirements.txt -r tools/requirements-dev.txt
./.venv/bin/python tools/validate_content.py
./.venv/bin/python -m pytest tools/tests -q
```

---

## Deploy your own copy

This repo is meant to be **forked and deployed to your own Free Edition
workspace**. Nothing in it depends on the maintainer's account: jobs run as
whoever deploys, the app keys everything on whoever is signed in, and a reset
restores the repo's clean notebooks and drops what an assignment produced.

```bash
# 1. Authenticate to your workspace
databricks auth login --host <your-workspace-url> --profile FREE

# 2. The one Lakebase project Free Edition allows, for the app's progress store.
#    Run from the repo root. The request body is in a file so it reaches the CLI
#    intact in any shell (PowerShell and cmd.exe mangle inline JSON).
databricks postgres create-project de-prep --json @ops/lakebase-project.json --profile FREE

# 3. Check there is room for it (README, "Capacity this needs")
python3 tools/preinstall_check.py --profile FREE

# 4. Deploy everything - labs, graders and the app - and start the app
cd bundle
databricks bundle deploy -t free --profile FREE
databricks bundle run study_app -t free --profile FREE
databricks apps get de-prep-study --profile FREE -o json | grep '"url"'
```

Open that URL. Because the jobs run as you and you own the tables you create,
no grants are needed. Deploy from the same machine and profile each time (a
development-mode deploy is named after its deployer). The optional GitHub Actions
pipeline in [`.github/workflows/`](.github/workflows/) is how the upstream repo
deploys; [`docs/ci-cd.md`](docs/ci-cd.md) covers setting it up with a service
principal if you want the same.

Never edit the deployed notebooks under `.bundle/`: the app gives you your own
copy of each assignment, and a reset puts the repo's clean version back.

**Coming back after a break.** Free Edition switches the app's database off
after a few days unused. Just open the app: it turns the database back on by
itself, shows *Waking your study database…* for a minute or two, and your
progress is all there. Two things it cannot do for you:

- **Start itself.** Apps stop 24 hours after they start; press **Start** on the
  app's page in your workspace (Compute → Apps → `de-prep-study`).
- **Redeploy over a sleeping database.** If `bundle deploy` fails with an error
  about the endpoint being disabled or granting permissions, wake it first and
  deploy again: `databricks bundle run wake_database -t free --profile FREE`.

---

## How to study with this

Open the **study app** in your workspace (it deploys with the bundle) and pick
**Learn** or **Test**. It remembers where you were.

1. **Learn a section.** The notes are organised by objective, sized by exam
   weight, and end with links to that section's lesson notebooks. Associate
   Section 3 is 22% of the exam, Section 1 is 6% — the app shows you.
2. **Run the lesson notebooks** on the `teach` dataset. The last cell of each
   points at the next one. Once you have opened them all, the assignment unlocks
   and the app gives you your own copy of the starter notebook (resettable).
3. **Do the assignment**, on the `assess` dataset. It won't accept the lesson's
   code — that's the point. Back in the app, **Grade my assignment** runs the
   section's checks and shows you what passed and what didn't. Unit tests are
   authoritative; an [optional AI reviewer](docs/grading.md) adds feedback on
   your *approach* if you attach a model.
4. **Practice.** Instant feedback, why each wrong option is wrong, and spaced
   repetition on what you missed. The readiness bars are sized by exam weight.
5. **Sit a timed test** at the real length and time limit. Nothing is revealed
   until you submit; then review everything, or just what you got wrong.

The objective maps are still the source of truth if you prefer paper:
[Associate](docs/exam-guides/associate-objectives.md) ·
[Professional](docs/exam-guides/professional-objectives.md).

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
