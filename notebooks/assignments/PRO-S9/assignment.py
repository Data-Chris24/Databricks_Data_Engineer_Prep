# Databricks notebook source
# MAGIC %md
# MAGIC # PRO-S9 assignment — your work goes here
# MAGIC
# MAGIC The task and the output contract are in the next cell (the same text as `README.md` in the repo).
# MAGIC
# MAGIC **There is no error to read. Every run succeeded. The evidence is in the data, not the run history.**
# MAGIC
# MAGIC When you are done, go back to the study app and press **Grade my assignment**.
# MAGIC Each failing check says what it expected and why.

# COMMAND ----------

# MAGIC %md
# MAGIC <!-- task:begin  generated from README.md by tools/sync_assignment_tasks.py; edit the README, then re-run it -->
# MAGIC ## Assignment — `PRO-S9` Debugging and Deploying
# MAGIC
# MAGIC **Objectives:** `PRO-S9-O1`, `O2`, `O3`
# MAGIC
# MAGIC ### Before you start
# MAGIC
# MAGIC Work the two lessons in `notebooks/lessons/professional/S9/`, and generate the data
# MAGIC (the study app generates the data the first time you open this section; `databricks bundle run generate_datasets_pro_s9 -t free` does the same from a terminal).
# MAGIC
# MAGIC > **There is no error to read.** Every run of this pipeline succeeded. There is no
# MAGIC > exception, no error class, no failed task in the history. The lesson's first
# MAGIC > notebook — read the message, find the bad rows — has nothing to work with here.
# MAGIC
# MAGIC ### The scenario
# MAGIC
# MAGIC `workspace.de_prep.pro_s9_assess_daily` is rebuilt daily by a job that has reported
# MAGIC **SUCCESS every single day**. It has nevertheless been producing incomplete output
# MAGIC for about a week.
# MAGIC
# MAGIC Diagnose it.
# MAGIC
# MAGIC ### The output contract
# MAGIC
# MAGIC **`workspace.de_prep.pro_s9_incident_report`** — exactly one row.
# MAGIC
# MAGIC | Column | Type | Meaning |
# MAGIC |---|---|---|
# MAGIC | `first_bad_date` | `STRING` | The first `run_date` on which output was incomplete, `YYYY-MM-DD` |
# MAGIC | `missing_source` | `STRING` | The source system that stopped contributing |
# MAGIC | `degraded_days` | `INT` | How many days have been affected |
# MAGIC | `rows_lost` | `INT` | Estimated rows missing across those days |
# MAGIC | `detail` | `STRING` | A sentence a colleague could act on |
# MAGIC
# MAGIC #### Requirements
# MAGIC
# MAGIC 1. Identify the **first** degraded day, not merely that something is wrong.
# MAGIC 2. Name the source that stopped.
# MAGIC 3. Estimate `rows_lost` from the healthy daily average against the degraded one.
# MAGIC 4. Do not modify the source table.
# MAGIC 5. `detail` must cite a number.
# MAGIC
# MAGIC ### Grading
# MAGIC
# MAGIC ```bash
# MAGIC databricks bundle run grade_pro_s9 -t free --profile FREE
# MAGIC ```
# MAGIC
# MAGIC ### Hints
# MAGIC
# MAGIC <details><summary>Where do I even start with no error?</summary>
# MAGIC
# MAGIC A single day tells you nothing. Group by `run_date` and look at how the numbers move
# MAGIC between days — the signal is the change, not any one value.
# MAGIC </details>
# MAGIC
# MAGIC <details><summary>How do I find which source stopped?</summary>
# MAGIC
# MAGIC Compare the set of `source_system` values before the regression with the set after.
# MAGIC </details>
# MAGIC
# MAGIC <details><summary>How do I estimate rows lost?</summary>
# MAGIC
# MAGIC Average rows per healthy day, minus average per degraded day, times the number of
# MAGIC degraded days.
# MAGIC </details>
# MAGIC <!-- task:end -->

# COMMAND ----------

from pyspark.sql import functions as F

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")
SOURCE = "pro_s9_assess_daily"        # do not modify it
TARGET = "pro_s9_incident_report"
daily = spark.table(SOURCE)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 0 — look at the daily totals, then per source
# MAGIC
# MAGIC A total that drifts down while the job stays green is the whole story. Which contributor stopped?

# COMMAND ----------

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1 — the first bad day
# MAGIC
# MAGIC Requirement 1: the first degraded `run_date`, not merely that something is wrong.

# COMMAND ----------

# first_bad_date = ...

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2 — the missing source and the damage
# MAGIC
# MAGIC Requirement 3: rows lost is the healthy daily average of that source times the degraded days.

# COMMAND ----------

# missing_source = ...
# degraded_days = ...
# rows_lost = ...

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3 — write the one-row report
# MAGIC
# MAGIC `first_bad_date` as `YYYY-MM-DD` text; `detail` cites a number.

# COMMAND ----------


# COMMAND ----------

# MAGIC %md
# MAGIC ## Check yourself before grading

# COMMAND ----------

# display(spark.table(TARGET))
