# Design: the CI/CD assignment (`ASSOC-S5`)

Status: **specified, not built.** Build it after the Phase 2 vertical slice has
settled the assignment machinery.

This one is unusual and worth designing deliberately, because building this repo's
own pipeline turned out to teach `ASSOC-S5` better than any notebook could.

---

## Why this assignment exists

Setting up this repo's CI/CD covered, in one continuous task:

| Objective | Where it showed up |
| --- | --- |
| `ASSOC-S5-O1` — branches, commits, pull requests | The whole PR workflow |
| `ASSOC-S5-O2` — environment-specific config via bundle variables and overrides | Bundle targets |
| `ASSOC-S5-O3` — deploy bundles across dev/test/prod | `bundle deploy -t <target>` |
| `ASSOC-S5-O4` — the CLI validating and deploying bundles in automation | `deploy.yml` |
| `PRO-S9-O4` — build and deploy Databricks resources with bundles | Same |
| `PRO-S9-O5` — Git-based CI/CD workflows | Same |

That is all four Associate CI/CD objectives plus two Professional ones, in a task
the learner actually performs rather than reads about. Almost nothing else in
either exam guide has that property.

---

## How it breaks the usual model — and how the pairing still works

Every other assignment pairs a `teach` dataset with a structurally different
`assess` dataset. This one has **no dataset at all**. The thing being learned is a
*configuration*, so the pairing has to work differently:

- **`teach`** — this repository's own pipeline. The learner reads
  [`docs/ci-cd.md`](../ci-cd.md), the three workflows, and `bundle/databricks.yml`,
  all of which are real and working.
- **`assess`** — the learner builds a pipeline in their **own fork**, to a
  specification that is *deliberately a different shape* from ours.

The anti-transplant property still has to hold: copying our `.github/workflows/`
and `databricks.yml` must **not** satisfy the assignment. So the required spec
differs structurally, not cosmetically:

| | This repo (`teach`) | The assignment (`assess`) |
| --- | --- | --- |
| Environments | One (`databricks-free`) | **Two** — `staging` and `production` |
| Approval | Required on the single environment | **Only** on `production`; `staging` deploys unattended |
| Deploy trigger | Push to `main` | `staging` on push to `main`; **`production` on a `v*` tag** |
| Bundle variables | Declared, never overridden per target | **Catalog and schema must differ per target** via overrides |
| Bundle resources | None yet | **A real job** that must run in both environments |

The variable-override requirement is the important one. Our bundle declares
variables and never overrides them per target, so `ASSOC-S5-O2` is the objective
this repo demonstrates *least* well — which makes it exactly the right thing to put
in the assignment. A learner who copies our file has no per-target override and
fails.

---

## Grading

### Tier 1 — deterministic

`tools/verify_ci_setup.py` was written to check *this* repo's configuration, and it
is already 90% of the grader. Generalise it to take a spec:

```bash
python3 tools/verify_ci_setup.py --spec content/assignments/ASSOC-S5/expected.yaml \
                                 --repo <learner>/<their-fork>
```

The spec asserts the shape above: two environments, approval on `production` only,
correct deployment branch/tag policies, secrets present on both, a ruleset with the
required checks.

Then the Databricks half, which the GitHub API cannot see:

- `databricks bundle validate -t staging` and `-t production` both succeed
- the resolved catalog/schema **differ** between the two targets — this is what
  proves a real override rather than two hardcoded copies
- the bundle is deployed in both, and the job exists in each

Both halves are mechanical, so the pass/fail is honest.

### Tier 2 — AI review (advisory)

Give the reviewer the learner's `databricks.yml` and workflow files and ask whether
they *promoted one definition across environments* or *duplicated it into two*.
Both pass the deterministic checks. Only one is the objective. This is precisely
the kind of judgement unit tests cannot make and an LLM can.

---

## Notes for whoever builds this

- **The learner needs their own Databricks workspace.** Free Edition is fine, but
  it allows one Lakebase project and a single warehouse — so `staging` and
  `production` must be two *targets and schemas* inside one workspace, not two
  workspaces. Say so explicitly; a learner who tries to sign up twice has
  misunderstood the exercise.
- **Do not require them to reproduce our exact ordering trap**, but do make them
  hit it: the ruleset step has to come after a first PR, and discovering that is
  half the lesson. `docs/ci-cd.md` explains it — the assignment should not.
- **Budget for the 14-day trial only if classic compute is involved.** It is not
  here; everything in this assignment runs serverless.
- Keep this assignment's spec in `content/assignments/ASSOC-S5/` alongside the
  others once built, so the validator can check it like any other.

## Ordering

The project plan schedules `ASSOC-S5` in Phase 4, group 3. Consider promoting it:
the process is freshly documented and verified, and the grader mostly exists. But
build the Phase 2 slice first — that is what establishes the assignment contract,
and generalising from an unusual config-based assignment would give us the wrong
pattern.
