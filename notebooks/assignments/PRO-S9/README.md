# Assignment — `PRO-S9` Debugging and Deploying

**Objectives:** `PRO-S9-O1`, `O2`, `O3`

## Before you start

Work the two lessons in `notebooks/lessons/professional/S9/`, and generate the data
(`databricks bundle run generate_datasets_pro_s9 -t free`).

> **There is no error to read.** Every run of this pipeline succeeded. There is no
> exception, no error class, no failed task in the history. The lesson's first
> notebook — read the message, find the bad rows — has nothing to work with here.

## The scenario

`workspace.de_prep.pro_s9_assess_daily` is rebuilt daily by a job that has reported
**SUCCESS every single day**. It has nevertheless been producing incomplete output
for about a week.

Diagnose it.

## The output contract

**`workspace.de_prep.pro_s9_incident_report`** — exactly one row.

| Column | Type | Meaning |
|---|---|---|
| `first_bad_date` | `STRING` | The first `run_date` on which output was incomplete, `YYYY-MM-DD` |
| `missing_source` | `STRING` | The source system that stopped contributing |
| `degraded_days` | `INT` | How many days have been affected |
| `rows_lost` | `INT` | Estimated rows missing across those days |
| `detail` | `STRING` | A sentence a colleague could act on |

### Requirements

1. Identify the **first** degraded day, not merely that something is wrong.
2. Name the source that stopped.
3. Estimate `rows_lost` from the healthy daily average against the degraded one.
4. Do not modify the source table.
5. `detail` must cite a number.

## Grading

In the study app, open **Learn → PRO-S9** and press **Grade my assignment**: it
runs this section's checks against the tables you produced and shows what
passed and what didn't. The same job from a terminal:

```bash
databricks bundle run grade_pro_s9 -t free --profile FREE
```

## Hints

<details><summary>Where do I even start with no error?</summary>

A single day tells you nothing. Group by `run_date` and look at how the numbers move
between days — the signal is the change, not any one value.
</details>

<details><summary>How do I find which source stopped?</summary>

Compare the set of `source_system` values before the regression with the set after.
</details>

<details><summary>How do I estimate rows lost?</summary>

Average rows per healthy day, minus average per degraded day, times the number of
degraded days.
</details>
