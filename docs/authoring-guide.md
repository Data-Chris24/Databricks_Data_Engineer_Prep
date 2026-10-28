# Authoring guide

How to add content without breaking the contracts the tooling depends on.

Run `python3 tools/validate_content.py` before every commit. CI runs it too.

---

## The one rule that matters most

**No real exam content, ever.**

Both certifications are under NDA. Recalled questions must never enter this repo —
not in content files, not in commit messages, not in issues. Beyond the ethics, it
would make the repo unshareable and worthless as a public study resource.

---

## Objectives

`content/objectives/*.yaml` is the source of truth for everything else. Edit it
only to track an official guide update.

**Objective IDs are permanent.** Lessons, questions and assignments reference them,
so renumbering silently re-points every reference. If a guide restructures, add new
IDs and mark removed ones — never renumber.

After editing, regenerate the docs (they're generated, so don't hand-edit them):

```bash
python3 tools/render_objectives.py
```

### When the exam guide changes

The map keeps every guide it has tracked, so a learner who prepared for an
earlier exam can still view it as it was. Nothing is deleted when a guide
changes. Instead:

1. **Add the version.** Append an entry to `guide_versions` (oldest first) with
   the new guide's date, item count, weighting source and its numbered sections.
   Each guide section lists the stable units (`sections:` IDs) it is made of. If
   the guide merges two sections, list both units under one number; the units,
   their folders, jobs and learner progress stay as they are.
2. **Close and open objective rows.** An objective is a Type 2 history:
   - wording changed, same skill → close the old row with `to: <new date>` and
     add a row `from: <new date>` under `versions:`. The ID stays.
   - dropped → give its last row `to: <new date>`.
   - new → a new ID with `from: <new date>`.
   - moved to another section → close the old ID and open a new one in the new
     section; IDs carry their section prefix.
3. **Fence version-specific note passages.** In a note, wrap a passage that
   belongs to some guides only:

   ```markdown
   <!-- guide: to=2026-10-09 -->
   ...taught for the guides before 9 Oct 2026...
   <!-- /guide -->
   ```

   `from=` and `to=` mean what they mean on a row (`to` is exclusive). Fences
   pair up, never nest, and name only tracked versions; the build fails
   otherwise.
4. **Questions follow their objectives.** A question belongs to every guide in
   which one of its objectives is live, so it needs no change of its own.
   Question IDs are still never reused.
5. Update `docs/exam-guides/SOURCES.md` and re-run the checks.

### Lab-feasibility tags

Only annotate exceptions. An absent tag is a positive claim that the objective is
fully practisable on Free Edition.

| Tag | When to use it |
| --- | --- |
| `free_edition_lab: partial` | Concept reachable, part of the surface isn't |
| `free_edition_lab: theory_only` | Not practisable on Free Edition at all |
| `optional_classic_lab: true` | A classic-compute lab covers the gap |
| `verify_in_workspace: true` | You genuinely don't know — say so, don't guess |

`verify_in_workspace` is not an admission of laziness; it's the honest state for
anything the docs left ambiguous. Guessing is the failure mode here.

Anything marked `theory_only` needs either an `optional_classic_lab` or a `note`
saying why the gap exists. The validator warns otherwise.

---

## Questions

Files live under `content/questions/<exam>/`, validated against
`content/questions/schema.json`.

### IDs

`<EXAM>-<SECTION>-Q<NNN>` — e.g. `ASSOC-S2-Q014`. The section prefix must match the
section of the **first** entry in `objective_ids`; the validator enforces this so
questions always file under the section they actually test.

IDs are never reused, even after a question is deleted.

### Writing good ones

- **Scenario-based beats recall.** Both real exams describe a situation and ask
  what to do. "A pipeline's runtime doubled after…" teaches more than "Which of
  these is a Delta Lake feature?"
- **Distractors must be plausible.** A wrong option nobody would pick tests
  nothing. The best distractors are real misconceptions — approaches that work in
  another system, or that used to be right.
- **The explanation is the product.** Learners read it after answering; it's where
  the actual teaching happens. Explain the *reasoning*, and name the general
  principle so it transfers to the next question.
- **Fill in `distractor_rationale`.** Understanding why an attractive wrong answer
  is wrong is usually worth more than the correct one.
- **Never name an option by its letter** in an explanation or a distractor
  rationale ("Option B…", "B and C both…"). The app shuffles the options, and
  spreads the right answer over A–D, so the letter on screen is not the letter
  in the YAML; describe the option instead ("the other three options…").
  `validate_content.py` rejects the "Option B" form. Author the right answer
  under any letter you like.
- **One correct answer.** Neither exam uses multi-select, and the schema doesn't
  model it.

### Near misses (medium and hard tests)

A test or practice round can be taken at three levels (`app/shared/optionOrder.ts`):
**standard** shows the question as written, **medium** swaps one wrong option for a
near miss, **hard** shows only near misses. A question shows above standard only
once it has all three `near_misses`; until then it appears as written at every level.

```yaml
    near_misses:
      - text: >-
          Every file in the source is processed again, because the schema location is
          reset along with the checkpoint.
        why: >-
          Deleting the checkpoint leaves the schema location alone. Files are reprocessed
          because the record of what was consumed lived in the checkpoint.
```

- **Shaped like the answer, wrong by a detail** a reader can find: the wrong option
  key, the wrong clause, the wrong layer, the wrong direction.
- **Never accidentally right.** A near miss is a claim about behaviour, so run it.
  On the ASSOC-S2 pilot (2026-10-17) running every claim found an existing distractor
  that was in fact correct (`inferSchema` does make that COPY INTO load) and showed
  that several plausible wrong options fail *silently*, which is better material than
  the error you expected.
- **Share wrong details between near misses.** If each one changes a different single
  detail, the right answer is the option that agrees with the majority, and a reader
  can pick it knowing nothing. `validate_content.py` rejects a set where the answer is
  the most similar option to the other three. The fix is to cross two dimensions: two
  near misses share one wrong detail, two share another.
- The `why` names the detail and what actually happens - the error class, or what the
  result looks like - not just "this is wrong".

### Code questions (fill in the blank)

Put the snippet in `code`, mark the gap with four or more underscores, set
`code_language` (`python` or `sql`) and `option_style: code`; the validator insists on
both when a gap is present. Options and near misses are code fragments, written as
`|-` blocks so quotes need no escaping.

Every option of a code question is executed before it ships: the answer must run and
do what the stem asks, each wrong option must fail or do something else, and its
rationale quotes what happened (`CLOUDFILES_SCHEMA_LOCATION_REQUIRED`,
`UDTF_ALIAS_NUMBER_MISMATCH`). Python-only mistakes can be checked with `compile()`;
anything Spark decides needs a serverless run. Watch for options that look wrong but
work: Spark option keys are case-insensitive, `dbutils.secrets.get` accepts positional
arguments, and `explode_outer` equals `explode` unless an array is empty.

### Provenance

Every question declares where it came from:

| `provenance` | Meaning |
| --- | --- |
| `original` | Written for this repo |
| `official-sample` | A retired sample Databricks publishes in an exam guide. Requires `source_note` |
| `concept-inspired` | Concept taken from third-party material, question written from scratch. Requires `source_note` |

### Third-party material and copyright

Reworded questions from a paid course are **derivative works**. Changing a few
words does not clear the problem. The process is:

1. From the source question, extract **only the concept under test**, and map it to
   an objective ID.
2. **Discard everything else** — wording, scenario, numbers, options.
3. Write a genuinely new question on that concept: different scenario domain,
   different data, independently written distractors.
4. Tag `provenance: concept-inspired` with a `source_note` naming the course —
   never quoting it.

Never paste source text into the repo, including into commit messages.

This isn't only a legal position. Concept-first authoring produces better
questions, because it tests the idea rather than one phrasing of it.

---

## Lessons and paired datasets

Every lesson teaches on a **`teach`** dataset. Every assignment is set on a
structurally different **`assess`** dataset, so assignment code can't be assembled
by pasting from the lesson.

### Making the pairing actually work

Cosmetic differences don't. Renamed columns over an identical shape fall to
find-and-replace in ten seconds. **Each pair must differ in at least two of:**

- **Shape** — flat vs nested (arrays/structs needing `explode`)
- **Types** — ISO timestamp strings vs epoch millis; numerics arriving as strings
- **Edge cases** — the `assess` set carries a hazard the `teach` set lacks:
  duplicate business keys, a malformed batch, mid-stream schema drift, timezone
  skew, negative quantities
- **Grain** — per-transaction vs pre-aggregated, changing what dedup and
  aggregation mean

Worked example — `ASSOC-S3-O1`, bronze to silver cleaning:

| | `teach` | `assess` |
| --- | --- | --- |
| Domain | Retail orders | IoT sensor readings |
| Shape | Flat | Nested arrays |
| Timestamps | ISO strings | Epoch millis |
| Hazard | Nulls in numerics | Duplicate event IDs |

Same objective, same techniques, non-transferable code.

Generators are **seeded**, so everyone gets byte-identical data and known-answer
probes stay valid.

**Do not document the `assess` schema up front.** Discovering it is part of the
task, and it mirrors both real work and the guides' own schema-discovery
objectives.

---

### Further reading footers

Every note ends with a `## Further reading` section: official documentation, one
link per topic the section tests, then one to three videos with channel and
length. Before adding a link, fetch it and check for a 200 (the docs site does
return real 404s); resolve a video through `https://www.youtube.com/oembed?url=...`
so the title and channel are what you think they are. Prefer `docs.databricks.com/aws/en/`
paths and the Databricks or Databricks Skill Builder channels; label community
videos with their channel. `docs/content-review.md` records the depth review the
footers came from and the visuals plan.

### Interactive diagrams

A diagram is one self-contained HTML file in `content/visuals/`, embedded from
any note on a line of its own:

```markdown
![Fail a task and pick each dependant's run_if](visual:job-dag-repair)
```

The build fails on a reference to a diagram that does not exist, and on a file
that loads anything from the network. The app renders it in a sandboxed iframe
that grows and shrinks to fit. `content/visuals/README.md` has the full contract
(size, width, light and dark, accessibility). A diagram makes claims about
behaviour, so check it like a note: on Free Edition or against the docs.

## Assignments

One per **section**, not per objective — 17 rather than 78. Section-level forces
objectives to be combined, which is closer to the exam and to real work.

Each assignment ships:

```
notebooks/assignments/<SECTION>/
  README.md                 task + explicit output contract   (learner-facing)
  assignment.py             learner starter notebook          (learner-facing)
grading/<SECTION>/
  grade.py                  runs the suite; the study app triggers this job
  tests/test_<SECTION>.py   authoritative pytest suite
  expected.json             fixtures the solution generated
grading/rubrics/<SECTION>.yaml   rubric for the AI reviewer
solutions/<SECTION>/
  solution.py               reference solution + fixture generator
  transplant_check.py       proves the lesson's code fails the suite
```

**Why the split.** Learners fork the repo and deploy it as admins of their own
workspace, so nothing can be hidden from them by permission. The layout does the
work instead: the app links only into `notebooks/`, the graders sit in their own
tree that the app runs on the learner's behalf, and `solutions/` is excluded from
the learner targets' sync entirely. Only the maintainer `verify` target deploys
solutions and the jobs that run them:

```bash
databricks bundle deploy -t verify --profile FREE
databricks bundle run run_solution_assoc_s3 -t verify --profile FREE      # regenerate fixtures
databricks bundle run transplant_check_assoc_s3 -t verify --profile FREE  # prove the property
```

A learner who wants to peek can still open `grading/<SECTION>/tests/` in their
workspace and read what is checked and the expected numbers. That is friction,
not secrecy, and it is the honest limit of a public repo.

### Optional lessons and extra assignments

Some material goes deeper than the exam needs. It is marked by name, and the app
keeps it off the learner's required path:

- **An optional lesson** has `optional` in its file name
  (`notebooks/lessons/associate/S2/04_optional_auto_loader_deep_dive.py`). The app
  lists it with an Optional badge, and the section's assignment does not wait for it
  to be opened. Helper notebooks a lesson runs go in a subfolder (`S2/_helpers/`),
  which the app never lists.
- **An extra assignment** lives in `notebooks/assignments/<SECTION>-<SLUG>/`
  (`ASSOC-S2-AUTO-LOADER`) and ships everything a section's assignment does:
  `grading/<ID>/` with `grade.py`, tests, `expected.json` and `outputs.json`, a
  rubric, `solutions/<ID>/` with a solution and a transplant check, a grade job named
  `[DE prep] Grade <ID>` and its grant to the app. The app shows it after the
  section's assignment, gated on every lesson of the section, optional ones included;
  it is provisioned, graded and reset under its own id, and never counts toward the
  section's completion. `tools/tests/test_layout.py` holds it to the same layout
  rules.

### A starter is a blank, not a redacted answer

A starter holds constants, the task text, one empty code cell per requirement
and a self-check that reads the output tables back. It never holds the
solution, and "commented out with one blank to fill" is the solution: on
2026-09-15 eleven starters were found carrying their `.write...saveAsTable`,
window, join and filter lines as comments. What a comment may say: a question or
hint in words, a placeholder such as `# good_version = ...` naming the value the
contract wants, or a self-check like `# display(spark.table(TARGET))`.
`tools/starter_rules.py` encodes this and the layout test fails on a breach.

### The README travels inside the starter

A learner's copy of `assignment.py` is provisioned alone into their workspace
folder, so the starter's second cell carries the README's text, generated
between `task:begin` / `task:end` markers. Edit `README.md`, then run
`python tools/sync_assignment_tasks.py`; CI runs it with `--check` and fails on
a stale starter. Never edit the generated cell by hand.

### Each step shows its part of the contract

By the last step a learner is a long scroll away from that README cell, so every
step's markdown cell also carries the slice of the contract it must satisfy. The
author writes one marker per step, as the cell's last line; the sync writes the
excerpt under it between `excerpt:begin` / `excerpt:end`:

```
# MAGIC ## Step 4 — deduplicate on the business key
# MAGIC
# MAGIC <!-- contract: silver_sensor_readings: event_id; requirements: 2 -->
```

The marker is `;`-separated items, shown in the order written:

| Item | Shows |
|---|---|
| `TABLE` | the whole table, under its README label |
| `TABLE: col, col` | only those rows, in README order |
| `requirements: 2, 3` | those numbered items from the README's `Requirements` list |
| `text: KEY` | the first paragraph (plus any blockquote after it) or subsection naming KEY |

`TABLE` and `KEY` are either a backticked name from the table's label or heading
(`silver_sensor_readings` matches `` `workspace.de_prep.silver_sensor_readings` ``,
but not a longer name it prefixes) or, when they contain a space, a phrase from the
label (`share this schema`). Rows are matched on their first cell the same way.

Rules of thumb: a step shows the columns it produces and the requirements it
answers; the write step and the last step (check yourself) show every output table
whole and every requirement, which a test enforces. A marker naming a table, row,
requirement or text the README no longer has fails the sync, so renaming a column
in the README fails `--check` until the markers follow. The excerpts are README
text, so they never carry an answer the README does not.

### The output contract

State exactly what the learner must produce: table name, required schema, and the
semantics (deduplicated on which key, malformed rows quarantined where, which
timezone). If it isn't in the contract, the tests can't assert it and the learner
can't be expected to guess it.

### Before you call an assignment done

1. The reference solution passes every assertion.
2. **The lesson's own solution, pasted in, FAILS** on the assess-only hazards. If
   it passes, the dataset pairing is broken — fix the datasets, not the tests.
3. Tier-1 tests alone produce a meaningful pass/fail, with no model attached.
4. Fixtures are committed and the tests don't import the solution.

Point 2 is the whole feature. Verify it, don't assume it.
