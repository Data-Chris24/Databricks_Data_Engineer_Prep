# How assignments are graded

Assignments in this repo are graded in two tiers. Only one of them counts.

| | Tier 1 — unit tests | Tier 2 — AI review |
| --- | --- | --- |
| Verdict | **Authoritative** | Advisory |
| Determinism | Same input, same result, always | Varies between runs |
| Needs credentials | No | Yes — yours |
| Judges | Did you produce the required output? | Did you use the intended technique? |

**Every assignment is fully gradeable by tier 1 alone.** If you never attach a
model, you still get a real pass or fail. Tier 2 is there to catch what tests
structurally cannot.

---

## Tier 1: unit tests

Each section has a grader under `grading/<SECTION>/`: `grade.py` runs the
`tests/` suite in-process against the tables the learner produced, using the
fixtures in `expected.json` that the reference solution generated. It returns a
structured result through the notebook's exit value:

```json
{"section": "ASSOC-S3", "passed": false, "total": 9,
 "failed": [{"test": "test_row_count", "outcome": "failed", "message": "assert 870 == 600 ..."}],
 "tests": [...], "report_tail": "..."}
```

**Where the learner's work lives.** The assignment step on a section page is
locked until every hands-on notebook of that section has been opened from the
app. It then creates the learner's own copy of the starter under the app
principal's `learners/<email>/<SECTION>/` folder (the deployed copy is never
edited). *Reset* puts the starter back in that copy, drops the objects the
section's `grading/<SECTION>/outputs.json` names (the tables the contract asks
for; for PRO-S4 the share and recipient; never an assess input) through the
`reset_assignment` job, and forgets the grades recorded for the section, so a
fresh attempt cannot pass on old work. Sections whose starter has not been
written yet link to the README instead, and can still reset their tables.
The same job also restores the section's *deployed* assignment notebooks from
the starters the build embedded, so even someone who edited the copy under
`.bundle/` directly gets the repo's clean version back.
*Start this exam over* on the Learn home offers the same for every section at
once, in a single job run, or lets the learner keep their assignments and only
clear reading progress.

**From the study app** (the normal path): the section page's *Grade my
assignment* button triggers the `grade_<section>` job as the app's service
principal, polls it, and shows the result inline: a pass, or the failing checks
with their messages. The learner never opens the job or the grader. Results are
kept per user in Lakebase (`study.grading_runs`) and the Learn home shows a
*Graded* chip once a section passes.

**From a terminal** (the same job, by hand):

```bash
databricks bundle run grade_assoc_s3 -t free --profile FREE
```

The verdict is binary and the tests are the contract: a test that cannot be
satisfied from the README's output contract is a bug in the assignment.

### This tier is also exam content

The harness is built from `assertDataFrameEqual`, `assertSchemaEqual` and
`DataFrame.transform` — which is exactly what `PRO-S1-O11` examines. Read the test
suites. They're a worked example of an objective you'll be tested on.

---

## Tier 2: AI review (bring your own model)

Unit tests can't tell whether you solved the problem the intended way. A `for`
loop over `read.json` might satisfy every assertion while completely missing Auto
Loader and schema evolution — passing the test and failing the lesson. They also
can't grade written justifications.

That's what this tier is for.

### Attaching a model

The repo ships **no credentials**. You provide the model; copy
`grading/.env.example` to `grading/.env` (gitignored) and fill in one provider.

**Databricks Foundation Model APIs — recommended.** No extra signup, no extra
bill, and it uses the workspace you already have:

```bash
DATABRICKS_PROFILE=FREE
GRADER_PROVIDER=databricks
GRADER_MODEL=databricks-claude-sonnet-4-5
```

Anthropic or OpenAI work too:

```bash
GRADER_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
GRADER_MODEL=claude-sonnet-4-5
```

Then:

```bash
python3 grading/ai_grader.py --assignment ASSOC-S2
python3 grading/ai_grader.py --assignment ASSOC-S2 --dry-run   # no model needed
```

`--dry-run` prints the assembled prompt and exits, so you can see exactly what
would be sent before sending anything.

### What it returns

Structured JSON, not prose:

```json
{
  "verdict": "fail",
  "missed_requirements": [
    "Schema evolution was not enabled; a new column would silently break this."
  ],
  "issues": [
    {"severity": "major", "location": "cell 4", "note": "Reads with spark.read.json in a loop rather than Auto Loader, so there is no checkpointing and reprocessing is not incremental."}
  ],
  "summary": "Output is correct for the current data but will not survive the next schema change."
}
```

### The rules that keep this honest

- **An AI verdict never overrides a unit test.** Where the two disagree, both are
  shown and the test wins. LLM graders are non-deterministic, and a grader that
  can fail you on a whim is worse than no grader.
- **It sees your code and the rubric, not the reference solution.** It's reviewing
  your approach, not diffing you against one right answer.
- **Treat its output as a second opinion.** If it flags something you believe is
  correct, you're probably right — go and confirm why, which is the useful part.

---

## Writing assignments (for contributors)

See [authoring-guide.md](authoring-guide.md) for the full contract spec. The
non-negotiables:

1. **Tier 1 must be sufficient.** If an assignment can only be graded by an LLM,
   it isn't specified tightly enough yet.
2. **Prove the anti-transplant property.** Paste the lesson's solution into the
   assignment and confirm the suite fails. If it passes, the dataset pairing is
   broken — fix the datasets, not the tests.
3. **Fixtures are committed**, generated from the reference solution, so the tests
   stand alone.
