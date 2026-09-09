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
- **One correct answer.** Neither exam uses multi-select, and the schema doesn't
  model it.

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

## Assignments

One per **section**, not per objective — 17 rather than 78. Section-level forces
objectives to be combined, which is closer to the exam and to real work.

Each assignment ships:

```
notebooks/assignments/<SECTION>/
  README.md              task + explicit output contract
  assignment.py          learner starter notebook
  tests/test_<SECTION>.py   authoritative pytest suite
solutions/<SECTION>/     reference solution + fixture generator
grading/rubrics/<SECTION>.yaml   rubric for the AI reviewer
```

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
