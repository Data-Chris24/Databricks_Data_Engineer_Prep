# Assignment — `ASSOC-S4` Working with Lakeflow Jobs

**Objectives:** `ASSOC-S4-O1`, `O2`, `O3`, `O4`

## Before you start

Work the two lessons in `notebooks/lessons/associate/S4/`, and generate the data
(`databricks bundle run generate_datasets_assoc_s4 -t free`).

> **The lesson's linear chain will not survive this source.** One region's file
> contains a value that will not cast, and a chain that reads everything at once dies
> with it. There is also a directory the lesson never looked at.

## The task

Build a pipeline over `/Volumes/workspace/de_prep/raw/s4_assess/` that publishes
regional order data — **without letting one bad region stop the others**.

## The output contract

**`workspace.de_prep.s4_gold_regional_orders`**

| Column | Type |
|---|---|
| `order_id` | `STRING` |
| `region` | `STRING` |
| `units` | `INT` |
| `ordered_on` | `DATE` |

**`workspace.de_prep.s4_quarantine_orders`** — every row that could not be published,
with its raw values preserved and the file it came from.

| Column | Type |
|---|---|
| `order_id` | `STRING` |
| `region` | `STRING` |
| `raw_units` | `STRING` |
| `raw_ordered_on` | `STRING` |
| `source_file` | `STRING` |

### Requirements

1. **A bad row must not stop the pipeline.** Publish everything that is valid.
2. **Nothing is silently dropped.** Every row that does not publish appears in
   quarantine with its original values.
3. **Include the late arrivals.** There is a subdirectory the main glob will not pick
   up. Its rows belong in the published table.
4. **Be idempotent.** The grader runs your job **twice**. Row counts must be identical
   after the second run.
5. Column order matters — the tests compare the whole schema.

## Grading

```bash
databricks bundle run grade_assoc_s4 -t free --profile FREE
```

## Hints

<details><summary>My job fails reading the files</summary>

Requirement 1. What happens if you read with a declared `INT` schema and one value is
`"twelve"`? Read as text and separate good from bad yourself — `try_cast` returns null
where `cast` raises.
</details>

<details><summary>I published 360 rows</summary>

Two things are missing: the 89 good rows from the region that also has a bad one, and
the late arrivals.
</details>

<details><summary>The second run doubled my data</summary>

Requirement 4. `append` is not idempotent.
</details>
