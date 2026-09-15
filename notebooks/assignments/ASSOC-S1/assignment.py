# Databricks notebook source
# MAGIC %md
# MAGIC # ASSOC-S1 assignment — your work goes here
# MAGIC
# MAGIC The task and the output contract are in the next cell (the same text as `README.md` in the repo).
# MAGIC
# MAGIC **A query against the current table cannot produce the right answer. The data is not there any more; it is still recoverable.**
# MAGIC
# MAGIC When you are done, go back to the study app and press **Grade my assignment**.
# MAGIC Each failing check says what it expected and why.

# COMMAND ----------

# MAGIC %md
# MAGIC <!-- task:begin  generated from README.md by tools/sync_assignment_tasks.py; edit the README, then re-run it -->
# MAGIC ## Assignment — `ASSOC-S1` Databricks Intelligence Platform
# MAGIC
# MAGIC **Objectives:** `ASSOC-S1-O1`, `ASSOC-S1-O2`
# MAGIC
# MAGIC ### Before you start
# MAGIC
# MAGIC Work the two lessons in `notebooks/lessons/associate/S1/`, and generate the data
# MAGIC (the study app runs the `generate_datasets_assoc_s1` job the first time you open this section; `databricks bundle run generate_datasets_assoc_s1 -t free` does the same from a terminal).
# MAGIC
# MAGIC > **A query against the current table cannot produce the right answer.** The data you
# MAGIC > need is not there any more. It is still recoverable.
# MAGIC
# MAGIC ### The scenario
# MAGIC
# MAGIC `workspace.de_prep.s1_assess_catalog` was overwritten by a broken upstream job. The
# MAGIC load succeeded, nothing errored, and the table still looks plausible — it just holds
# MAGIC fewer rows and every price is zero.
# MAGIC
# MAGIC Recover the data and write up what happened.
# MAGIC
# MAGIC ### The output contract
# MAGIC
# MAGIC **`workspace.de_prep.s1_recovered_catalog`** — the last good state of the table.
# MAGIC
# MAGIC | Column | Type |
# MAGIC |---|---|
# MAGIC | `sku` | `STRING` |
# MAGIC | `category` | `STRING` |
# MAGIC | `price` | `DOUBLE` |
# MAGIC | `listed_on` | `DATE` |
# MAGIC
# MAGIC **`workspace.de_prep.s1_incident_report`** — exactly one row.
# MAGIC
# MAGIC | Column | Type | Meaning |
# MAGIC |---|---|---|
# MAGIC | `bad_version` | `INT` | The version that caused the damage |
# MAGIC | `good_version` | `INT` | The last version before it |
# MAGIC | `rows_lost` | `INT` | How many rows the bad load destroyed |
# MAGIC | `value_lost` | `DOUBLE` | How much `price` value it destroyed |
# MAGIC | `detail` | `STRING` | A sentence a colleague could act on |
# MAGIC
# MAGIC #### Requirements
# MAGIC
# MAGIC 1. **Identify the last good version by measurement**, not assumption. Do not hardcode
# MAGIC    a version number you guessed.
# MAGIC 2. **Do not restore the source table in place.** The damaged history is the evidence.
# MAGIC 3. `rows_lost` and `value_lost` are the difference between the good version and the
# MAGIC    current one.
# MAGIC 4. Column order matters — the tests compare the whole schema.
# MAGIC
# MAGIC ### Grading
# MAGIC
# MAGIC In the study app, open **Learn → ASSOC-S1** and press **Grade my assignment**: it
# MAGIC runs this section's checks against the tables you produced and shows what
# MAGIC passed and what didn't. The same job from a terminal:
# MAGIC
# MAGIC ```bash
# MAGIC databricks bundle run grade_assoc_s1 -t free --profile FREE
# MAGIC ```
# MAGIC
# MAGIC ### Hints
# MAGIC
# MAGIC <details><summary>How do I see earlier versions?</summary>
# MAGIC
# MAGIC `DESCRIBE HISTORY <table>` lists them. `SELECT * FROM <table> VERSION AS OF <n>`
# MAGIC queries one.
# MAGIC </details>
# MAGIC
# MAGIC <details><summary>Which version is the good one?</summary>
# MAGIC
# MAGIC Requirement 1 — profile them. The bad load zeroed every price, so check each version
# MAGIC for how many rows have `price = 0.0`.
# MAGIC </details>
# MAGIC <!-- task:end -->

# COMMAND ----------

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")
SOURCE = "s1_assess_catalog"          # damaged; do NOT restore it in place
RECOVERED = "s1_recovered_catalog"
REPORT = "s1_incident_report"

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 0 — look at the history
# MAGIC
# MAGIC Every write to a Delta table is a version. Which one did the damage?

# COMMAND ----------

display(spark.sql(f"DESCRIBE HISTORY {SOURCE}"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1 — measure each version
# MAGIC
# MAGIC Requirement 1: identify the last good version by measurement, not assumption.
# MAGIC The bad load zeroed every price; profile row counts and zero-price counts per version.

# COMMAND ----------

# for v in range(...):
#     df = spark.read.option("versionAsOf", v).table(SOURCE)
#     print(v, df.count(), df.filter("price = 0.0").count())

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2 — pick the versions
# MAGIC
# MAGIC `good_version` is the last one before the damage; `bad_version` is the one that caused it.

# COMMAND ----------

# good_version = ...
# bad_version = ...

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3 — write the recovered table
# MAGIC
# MAGIC Requirement 2: leave the source alone. Read the good version and write it under the contracted name, in the contracted column order.

# COMMAND ----------

# spark.read.option("versionAsOf", good_version).table(SOURCE) \
#     .select("sku", "category", "price", "listed_on") \
#     .write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(RECOVERED)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 4 — write the incident report
# MAGIC
# MAGIC Exactly one row. `rows_lost` and `value_lost` are good-version minus current.

# COMMAND ----------

# report = spark.createDataFrame([(bad_version, good_version, rows_lost, value_lost, detail)],
#                                 "bad_version INT, good_version INT, rows_lost INT, value_lost DOUBLE, detail STRING")
# report.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(REPORT)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Check yourself before grading

# COMMAND ----------

# display(spark.table(RECOVERED).limit(5)); print(spark.table(RECOVERED).count())
# display(spark.table(REPORT))
