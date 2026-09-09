# Assignment — `ASSOC-S2` Data Ingestion and Loading

**Objectives exercised:** `ASSOC-S2-O1`, `ASSOC-S2-O3`, `ASSOC-S2-O6`, `ASSOC-S2-O7`

## Before you start

1. Work through the three lessons in `notebooks/lessons/associate/S2/`.
2. Make sure the datasets exist — run `notebooks/datasets/generate_ASSOC-S2.py`,
   or `databricks bundle run generate_datasets_assoc_s2 -t free`.

> **The lesson's code will not solve this.** The assignment uses a different
> dataset with a different shape, on purpose. Copying the lesson notebook and
> changing the paths produces a table that fails the tests. Read the source before
> you write anything.

## The task

`/Volumes/workspace/de_prep/raw/s2_assess/` holds JSON files of sensor telemetry.
Produce a clean, analysis-ready table from them.

**You are not told the schema.** Inspecting the source is part of the job, and it
is what the exam means by understanding a data source before ingesting it.

## The output contract

Create a table **`workspace.de_prep.silver_sensor_readings`** with exactly this
schema, in this column order:

| Column | Type | Meaning |
|---|---|---|
| `event_id` | `STRING` | Unique per row. This is the business key |
| `device_id` | `STRING` | Which sensor reported it |
| `site` | `STRING` | Where that sensor is |
| `firmware` | `STRING` | Firmware version reported by the device |
| `recorded_at` | `TIMESTAMP` | When the reading was taken |
| `temperature_c` | `DOUBLE` | Degrees Celsius |
| `humidity_pct` | `DOUBLE` | Percent |
| `battery_pct` | `DOUBLE` | Percent. **Null for readings taken before the devices began reporting it** |

### Requirements

1. **One row per reading.** The source is not shaped this way.
2. **`event_id` must be unique.** The source contains the same reading more than
   once. Decide what "the same" means and keep one.
3. **`recorded_at` must be a real timestamp** in March 2026. If your dates land in
   the year 58000, you have made the mistake this dataset is designed to catch —
   and note that it produced no error.
4. **`battery_pct` must survive.** Some source files do not have it. If your read
   drops the column, or nulls it everywhere, the tests will say so.
5. **Column order matters.** The tests use `assertSchemaEqual`.

## How you are graded

**Unit tests — authoritative.** Run them with:

```bash
databricks bundle run grade_assoc_s2 -t free --profile FREE
```

They check the schema, the row count, that deduplication happened, that timestamps
are sane, that `battery_pct` survived, and a handful of known answers for specific
`event_id`s.

**AI review — advisory, optional.** If you have attached a model (see
`docs/grading.md`), it also reviews *how* you did it — whether you used the
technique the objective is about or merely got the numbers right by another route.
It can never overturn a unit test result.

## Hints, if you want them

<details>
<summary>I do not know where to start</summary>

Read one file first and print the schema:
`spark.read.json(".../s2_assess/events_2026-03-01.json").printSchema()`
The shape of the problem should be obvious from that.
</details>

<details>
<summary>My row count is too high</summary>

Requirement 2. Find the duplicates before you remove them:
`GROUP BY event_id HAVING count(*) > 1`.
</details>

<details>
<summary>`battery_pct` does not exist in my DataFrame</summary>

Spark infers JSON schemas from a sample of files. The column only appears in one of
them. Lesson 3 named the option that fixes this — it applies to batch reads too.
</details>

<details>
<summary>My timestamps are absurd</summary>

Look at the raw value. What unit is it in, and what unit does `CAST(... AS
TIMESTAMP)` expect?
</details>
