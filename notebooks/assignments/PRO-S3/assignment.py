# Databricks notebook source
# MAGIC %md
# MAGIC # PRO-S3 assignment — your work goes here
# MAGIC
# MAGIC The task and the output contract are in the next cell (the same text as `README.md` in the repo).
# MAGIC
# MAGIC **Every row in this table is individually valid. The lesson's row-level rules find nothing; the problems live in the sequence.**
# MAGIC
# MAGIC When you are done, go back to the study app and press **Grade my assignment**.
# MAGIC Each failing check says what it expected and why.

# COMMAND ----------

# MAGIC %md
# MAGIC <!-- task:begin  generated from README.md by tools/sync_assignment_tasks.py; edit the README, then re-run it -->
# MAGIC ## Assignment — `PRO-S3` Data Transformation, Cleansing and Quality
# MAGIC
# MAGIC **Objectives:** `PRO-S3-O1`, `PRO-S3-O2`
# MAGIC
# MAGIC ### Before you start
# MAGIC
# MAGIC Work the lesson in `notebooks/lessons/professional/S3/`, and generate the data
# MAGIC (the study app generates the data the first time you open this section; `databricks bundle run generate_datasets_pro_s3 -t free` does the same from a terminal).
# MAGIC
# MAGIC > **Every row in this table is individually valid.** Every value casts, no nulls, no
# MAGIC > negatives, no impossible magnitudes. The lesson's row-level rules find **nothing**,
# MAGIC > and that is the point: everything wrong here exists *between* rows.
# MAGIC
# MAGIC ### The task
# MAGIC
# MAGIC `workspace.de_prep.pro_s3_assess_meter_readings` holds cumulative meter readings,
# MAGIC taken every 15 minutes per device. Find the three ways the data is wrong.
# MAGIC
# MAGIC You are graded on the **findings**. Do not clean the table.
# MAGIC
# MAGIC ### The output contract
# MAGIC
# MAGIC **`workspace.de_prep.pro_s3_quality_findings`** — one row per finding.
# MAGIC
# MAGIC | Column | Type | Meaning |
# MAGIC |---|---|---|
# MAGIC | `finding` | `STRING` | One of `meter_backwards`, `sequence_gap`, `duplicate_timestamp` |
# MAGIC | `affected_rows` | `DOUBLE` | How many rows or intervals the finding covers |
# MAGIC | `affected_devices` | `STRING` | Comma-separated device ids, sorted |
# MAGIC | `detail` | `STRING` | A sentence a colleague could act on |
# MAGIC
# MAGIC #### What each finding means
# MAGIC
# MAGIC | `finding` | Look for |
# MAGIC |---|---|
# MAGIC | `meter_backwards` | a reading lower than its predecessor — a cumulative meter cannot decrease |
# MAGIC | `sequence_gap` | an interval longer than 15 minutes, meaning readings are missing |
# MAGIC | `duplicate_timestamp` | more than one reading for a device at the same instant |
# MAGIC
# MAGIC #### Requirements
# MAGIC
# MAGIC 1. All three findings, one row each.
# MAGIC 2. `affected_devices` sorted and comma-separated, so it compares reliably.
# MAGIC 3. Do not modify the source table.
# MAGIC 4. `detail` must cite a number.
# MAGIC
# MAGIC ### Grading
# MAGIC
# MAGIC ```bash
# MAGIC databricks bundle run grade_pro_s3 -t free --profile FREE
# MAGIC ```
# MAGIC
# MAGIC ### Hints
# MAGIC
# MAGIC <details><summary>My quality checks all pass</summary>
# MAGIC
# MAGIC They would. Every row is valid on its own. Ask what the *previous* row was.
# MAGIC </details>
# MAGIC
# MAGIC <details><summary>How do I find missing rows?</summary>
# MAGIC
# MAGIC You cannot look at a row that is not there. Look at the interval between the rows
# MAGIC that are — `lag` on the timestamp.
# MAGIC </details>
# MAGIC
# MAGIC <details><summary>My backwards count seems high</summary>
# MAGIC
# MAGIC Check whether one defect is producing another. A duplicate reading with a higher
# MAGIC value makes the *next* reading look like a decrease. That interaction is real, and
# MAGIC worth noticing rather than correcting for.
# MAGIC </details>
# MAGIC <!-- task:end -->

# COMMAND ----------

from pyspark.sql import Window
from pyspark.sql import functions as F

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")
SOURCE = "pro_s3_assess_meter_readings"   # do not modify it
TARGET = "pro_s3_quality_findings"
readings = spark.table(SOURCE)
w = Window.partitionBy("device_id").orderBy("reading_ts")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 0 — look
# MAGIC
# MAGIC How many devices, what cadence, what does one device's series look like?

# COMMAND ----------

# display(readings.orderBy("device_id", "reading_ts").limit(20))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1 — meter_backwards
# MAGIC
# MAGIC A cumulative meter cannot decrease. Compare each reading with its predecessor.

# COMMAND ----------

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2 — sequence_gap
# MAGIC
# MAGIC Readings arrive every 15 minutes. An interval longer than that means readings are missing.

# COMMAND ----------

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3 — duplicate_timestamp
# MAGIC
# MAGIC More than one reading for a device at the same instant.

# COMMAND ----------

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 4 — write the findings
# MAGIC
# MAGIC One row each. `affected_devices` sorted and comma-separated; `detail` cites a number.

# COMMAND ----------

# rows = [("meter_backwards", float(...), devices(backwards), "..."), ...]

# COMMAND ----------

# MAGIC %md
# MAGIC ## Check yourself before grading

# COMMAND ----------

# display(spark.table(TARGET))
