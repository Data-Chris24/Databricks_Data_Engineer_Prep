# Assignment — `ASSOC-S1` Databricks Intelligence Platform

**Objectives:** `ASSOC-S1-O1`, `ASSOC-S1-O2`

## Before you start

Work the two lessons in `notebooks/lessons/associate/S1/`, and generate the data
(`databricks bundle run generate_datasets_assoc_s1 -t free`).

> **A query against the current table cannot produce the right answer.** The data you
> need is not there any more. It is still recoverable.

## The scenario

`workspace.de_prep.s1_assess_catalog` was overwritten by a broken upstream job. The
load succeeded, nothing errored, and the table still looks plausible — it just holds
fewer rows and every price is zero.

Recover the data and write up what happened.

## The output contract

**`workspace.de_prep.s1_recovered_catalog`** — the last good state of the table.

| Column | Type |
|---|---|
| `sku` | `STRING` |
| `category` | `STRING` |
| `price` | `DOUBLE` |
| `listed_on` | `DATE` |

**`workspace.de_prep.s1_incident_report`** — exactly one row.

| Column | Type | Meaning |
|---|---|---|
| `bad_version` | `INT` | The version that caused the damage |
| `good_version` | `INT` | The last version before it |
| `rows_lost` | `INT` | How many rows the bad load destroyed |
| `value_lost` | `DOUBLE` | How much `price` value it destroyed |
| `detail` | `STRING` | A sentence a colleague could act on |

### Requirements

1. **Identify the last good version by measurement**, not assumption. Do not hardcode
   a version number you guessed.
2. **Do not restore the source table in place.** The damaged history is the evidence.
3. `rows_lost` and `value_lost` are the difference between the good version and the
   current one.
4. Column order matters — the tests compare the whole schema.

## Grading

In the study app, open **Learn → ASSOC-S1** and press **Grade my assignment**: it
runs this section's checks against the tables you produced and shows what
passed and what didn't. The same job from a terminal:

```bash
databricks bundle run grade_assoc_s1 -t free --profile FREE
```

## Hints

<details><summary>How do I see earlier versions?</summary>

`DESCRIBE HISTORY <table>` lists them. `SELECT * FROM <table> VERSION AS OF <n>`
queries one.
</details>

<details><summary>Which version is the good one?</summary>

Requirement 1 — profile them. The bad load zeroed every price, so check each version
for how many rows have `price = 0.0`.
</details>
