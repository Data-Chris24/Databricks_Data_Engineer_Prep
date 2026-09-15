# Databricks notebook source
# MAGIC %md
# MAGIC # ASSOC-S2 assignment — your work goes here
# MAGIC
# MAGIC The task and the output contract are in the next cell (the same text as `README.md` in the repo).
# MAGIC
# MAGIC **The lesson's code will not solve this.** The source has a different shape.
# MAGIC Copying `01_copy_into.py` or `02_auto_loader.py` and changing the paths
# MAGIC produces a table that fails the tests — that is deliberate, and the failures
# MAGIC will tell you which assumption broke.
# MAGIC
# MAGIC Grade your work with:
# MAGIC ```
# MAGIC databricks bundle run grade_assoc_s2 -t free --profile FREE
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC <!-- task:begin  generated from README.md by tools/sync_assignment_tasks.py; edit the README, then re-run it -->
# MAGIC ## Assignment — `ASSOC-S2` Data Ingestion and Loading
# MAGIC
# MAGIC **Objectives exercised:** `ASSOC-S2-O1`, `ASSOC-S2-O3`, `ASSOC-S2-O6`, `ASSOC-S2-O7`
# MAGIC
# MAGIC ### Before you start
# MAGIC
# MAGIC 1. Work through the three lessons in `notebooks/lessons/associate/S2/`.
# MAGIC 2. The datasets: the study app runs the `generate_datasets_assoc_s2` job the
# MAGIC    first time you open this section (`databricks bundle run
# MAGIC    generate_datasets_assoc_s2 -t free` does the same from a terminal).
# MAGIC
# MAGIC > **The lesson's code will not solve this.** The assignment uses a different
# MAGIC > dataset with a different shape, on purpose. Copying the lesson notebook and
# MAGIC > changing the paths produces a table that fails the tests. Read the source before
# MAGIC > you write anything.
# MAGIC
# MAGIC ### The task
# MAGIC
# MAGIC `/Volumes/workspace/de_prep/raw/s2_assess/` holds JSON files of sensor telemetry.
# MAGIC Produce a clean, analysis-ready table from them.
# MAGIC
# MAGIC **You are not told the schema.** Inspecting the source is part of the job, and it
# MAGIC is what the exam means by understanding a data source before ingesting it.
# MAGIC
# MAGIC ### The output contract
# MAGIC
# MAGIC Create a table **`workspace.de_prep.silver_sensor_readings`** with exactly this
# MAGIC schema, in this column order:
# MAGIC
# MAGIC | Column | Type | Meaning |
# MAGIC |---|---|---|
# MAGIC | `event_id` | `STRING` | Unique per row. This is the business key |
# MAGIC | `device_id` | `STRING` | Which sensor reported it |
# MAGIC | `site` | `STRING` | Where that sensor is |
# MAGIC | `firmware` | `STRING` | Firmware version reported by the device |
# MAGIC | `recorded_at` | `TIMESTAMP` | When the reading was taken |
# MAGIC | `temperature_c` | `DOUBLE` | Degrees Celsius |
# MAGIC | `humidity_pct` | `DOUBLE` | Percent |
# MAGIC | `battery_pct` | `DOUBLE` | Percent. **Null for readings taken before the devices began reporting it** |
# MAGIC
# MAGIC #### Requirements
# MAGIC
# MAGIC 1. **One row per reading.** The source is not shaped this way.
# MAGIC 2. **`event_id` must be unique.** The source contains the same reading more than
# MAGIC    once. Decide what "the same" means and keep one.
# MAGIC 3. **`recorded_at` must be a real timestamp** in March 2026. If your dates land in
# MAGIC    the year 58000, you have made the mistake this dataset is designed to catch —
# MAGIC    and note that it produced no error.
# MAGIC 4. **`battery_pct` must survive.** Some source files do not have it. If your read
# MAGIC    drops the column, or nulls it everywhere, the tests will say so.
# MAGIC 5. **Column order matters.** The tests use `assertSchemaEqual`.
# MAGIC
# MAGIC ### How you are graded
# MAGIC
# MAGIC **Unit tests — authoritative.** Run them with:
# MAGIC
# MAGIC ```bash
# MAGIC databricks bundle run grade_assoc_s2 -t free --profile FREE
# MAGIC ```
# MAGIC
# MAGIC They check the schema, the row count, that deduplication happened, that timestamps
# MAGIC are sane, that `battery_pct` survived, and a handful of known answers for specific
# MAGIC `event_id`s.
# MAGIC
# MAGIC **AI review — advisory, optional.** If you have attached a model (see
# MAGIC `docs/grading.md`), it also reviews *how* you did it — whether you used the
# MAGIC technique the objective is about or merely got the numbers right by another route.
# MAGIC It can never overturn a unit test result.
# MAGIC
# MAGIC ### Hints, if you want them
# MAGIC
# MAGIC <details>
# MAGIC <summary>I do not know where to start</summary>
# MAGIC
# MAGIC Read one file first and print the schema:
# MAGIC `spark.read.json(".../s2_assess/events_2026-03-01.json").printSchema()`
# MAGIC The shape of the problem should be obvious from that.
# MAGIC </details>
# MAGIC
# MAGIC <details>
# MAGIC <summary>My row count is too high</summary>
# MAGIC
# MAGIC Requirement 2. Find the duplicates before you remove them:
# MAGIC `GROUP BY event_id HAVING count(*) > 1`.
# MAGIC </details>
# MAGIC
# MAGIC <details>
# MAGIC <summary>`battery_pct` does not exist in my DataFrame</summary>
# MAGIC
# MAGIC Spark infers JSON schemas from a sample of files. The column only appears in one of
# MAGIC them. Lesson 3 named the option that fixes this — it applies to batch reads too.
# MAGIC </details>
# MAGIC
# MAGIC <details>
# MAGIC <summary>My timestamps are absurd</summary>
# MAGIC
# MAGIC Look at the raw value. What unit is it in, and what unit does `CAST(... AS
# MAGIC TIMESTAMP)` expect?
# MAGIC </details>
# MAGIC <!-- task:end -->

# COMMAND ----------

from pyspark.sql import functions as F

CATALOG, SCHEMA = "workspace", "de_prep"
RAW = f"/Volumes/{CATALOG}/{SCHEMA}/raw/s2_assess"
TARGET = "silver_sensor_readings"

spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 0 — look at the source first
# MAGIC
# MAGIC You have not been told the schema. Find it. What shape are the records, what
# MAGIC type is the timestamp field, and is every file the same?

# COMMAND ----------

for f in dbutils.fs.ls(RAW):
    print(f.name, f"{f.size:,} bytes")

# COMMAND ----------

# Print the schema of a single file, then of all of them. Are they the same?
# spark.read.json(f"{RAW}/events_2026-03-01.json").printSchema()


# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1 — read the source
# MAGIC
# MAGIC Mind the batch whose schema differs.

# COMMAND ----------

# raw = ...


# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2 — reshape to one row per reading

# COMMAND ----------




# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3 — types, and the timestamp
# MAGIC
# MAGIC Check your dates land in 2026 before moving on. A wrong unit here produces no
# MAGIC error at all.

# COMMAND ----------




# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 4 — deduplicate on the business key

# COMMAND ----------




# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 5 — write the contracted table
# MAGIC
# MAGIC Column order matters; the tests compare the whole schema.

# COMMAND ----------

# final.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(TARGET)


# COMMAND ----------

# MAGIC %md
# MAGIC ## Check yourself before grading

# COMMAND ----------

# t = spark.table(TARGET)
# print("rows:", t.count(), "| distinct event_id:", t.select("event_id").distinct().count())
# t.printSchema()
# display(t.orderBy("event_id").limit(5))
