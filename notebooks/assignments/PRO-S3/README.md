# Assignment — `PRO-S3` Data Transformation, Cleansing and Quality

**Objectives:** `PRO-S3-O1`, `PRO-S3-O2`

## Before you start

Work the lesson in `notebooks/lessons/professional/S3/`, and generate the data
(`databricks bundle run generate_datasets_pro_s3 -t free`).

> **Every row in this table is individually valid.** Every value casts, no nulls, no
> negatives, no impossible magnitudes. The lesson's row-level rules find **nothing**,
> and that is the point: everything wrong here exists *between* rows.

## The task

`workspace.de_prep.pro_s3_assess_meter_readings` holds cumulative meter readings,
taken every 15 minutes per device. Find the three ways the data is wrong.

You are graded on the **findings**. Do not clean the table.

## The output contract

**`workspace.de_prep.pro_s3_quality_findings`** — one row per finding.

| Column | Type | Meaning |
|---|---|---|
| `finding` | `STRING` | One of `meter_backwards`, `sequence_gap`, `duplicate_timestamp` |
| `affected_rows` | `DOUBLE` | How many rows or intervals the finding covers |
| `affected_devices` | `STRING` | Comma-separated device ids, sorted |
| `detail` | `STRING` | A sentence a colleague could act on |

### What each finding means

| `finding` | Look for |
|---|---|
| `meter_backwards` | a reading lower than its predecessor — a cumulative meter cannot decrease |
| `sequence_gap` | an interval longer than 15 minutes, meaning readings are missing |
| `duplicate_timestamp` | more than one reading for a device at the same instant |

### Requirements

1. All three findings, one row each.
2. `affected_devices` sorted and comma-separated, so it compares reliably.
3. Do not modify the source table.
4. `detail` must cite a number.

## Grading

```bash
databricks bundle run grade_pro_s3 -t free --profile FREE
```

## Hints

<details><summary>My quality checks all pass</summary>

They would. Every row is valid on its own. Ask what the *previous* row was.
</details>

<details><summary>How do I find missing rows?</summary>

You cannot look at a row that is not there. Look at the interval between the rows
that are — `lag` on the timestamp.
</details>

<details><summary>My backwards count seems high</summary>

Check whether one defect is producing another. A duplicate reading with a higher
value makes the *next* reading look like a decrease. That interaction is real, and
worth noticing rather than correcting for.
</details>
