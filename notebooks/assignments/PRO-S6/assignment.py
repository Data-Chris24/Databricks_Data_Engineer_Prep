# Databricks notebook source
# MAGIC %md
# MAGIC # PRO-S6 assignment — your work goes here
# MAGIC
# MAGIC The task and the output contract are in the next cell (the same text as `README.md` in the repo).
# MAGIC
# MAGIC **The lesson's table was slow for one reason and clustering fixed it. This one is slow for three, and clustering the wrong column would make it worse.**
# MAGIC
# MAGIC When you are done, go back to the study app and press **Grade my assignment**.
# MAGIC Each failing check says what it expected and why.

# COMMAND ----------

# MAGIC %md
# MAGIC <!-- task:begin  generated from README.md by tools/sync_assignment_tasks.py; edit the README, then re-run it -->
# MAGIC ## Assignment — `PRO-S6` Cost and Performance Optimization
# MAGIC
# MAGIC **Objectives:** `PRO-S6-O1`, `O2`, `O3`, `O5`
# MAGIC
# MAGIC ### Before you start
# MAGIC
# MAGIC Work the two lessons in `notebooks/lessons/professional/S6/`, and generate the data
# MAGIC (`databricks bundle run generate_datasets_pro_s6 -t free`).
# MAGIC
# MAGIC > **The lesson's table was slow for one reason and clustering fixed it.** This one is
# MAGIC > slow for three unrelated reasons, and clustering addresses one of them. Applying
# MAGIC > the lesson's `ALTER TABLE ... CLUSTER BY` and stopping there gets a third of the
# MAGIC > marks and, on one of the columns, would make things worse.
# MAGIC
# MAGIC ### The task
# MAGIC
# MAGIC `workspace.de_prep.pro_s6_assess_orders` is expensive to query. Diagnose **three
# MAGIC distinct causes** and recommend a fix for each.
# MAGIC
# MAGIC You are graded on the **analysis**. Do not optimise the table — the current state is
# MAGIC the evidence.
# MAGIC
# MAGIC ### The output contract
# MAGIC
# MAGIC **`workspace.de_prep.pro_s6_optimization_report`** — one row per finding.
# MAGIC
# MAGIC | Column | Type | Meaning |
# MAGIC |---|---|---|
# MAGIC | `finding` | `STRING` | One of `small_files`, `wide_projection`, `bad_cluster_key` |
# MAGIC | `recommendation` | `STRING` | What to do about it |
# MAGIC | `metric` | `DOUBLE` | The number evidencing it (below) |
# MAGIC | `detail` | `STRING` | A sentence a colleague could act on |
# MAGIC
# MAGIC #### What `metric` must hold
# MAGIC
# MAGIC | `finding` | `metric` |
# MAGIC |---|---|
# MAGIC | `small_files` | the number of files in the table |
# MAGIC | `wide_projection` | the number of columns |
# MAGIC | `bad_cluster_key` | that column's cardinality as a percentage of row count |
# MAGIC
# MAGIC #### Requirements
# MAGIC
# MAGIC 1. All three findings, one row each.
# MAGIC 2. `bad_cluster_key`'s `recommendation` must **name the column that would be the
# MAGIC    wrong choice**, and the detail must say what to cluster on instead.
# MAGIC 3. Do not modify the source table.
# MAGIC 4. `detail` must cite a number.
# MAGIC
# MAGIC ### Grading
# MAGIC
# MAGIC ```bash
# MAGIC databricks bundle run grade_pro_s6 -t free --profile FREE
# MAGIC ```
# MAGIC
# MAGIC ### Hints
# MAGIC
# MAGIC <details><summary>Where do I start?</summary>
# MAGIC
# MAGIC `DESCRIBE DETAIL` gives file count and total size in one row. Divide.
# MAGIC </details>
# MAGIC
# MAGIC <details><summary>What makes a clustering key bad?</summary>
# MAGIC
# MAGIC Count distinct values against row count. If nearly every row is unique, no file can
# MAGIC be skipped — clustering costs a rewrite and buys nothing.
# MAGIC </details>
# MAGIC
# MAGIC <details><summary>Why is a wide table a problem if I filter well?</summary>
# MAGIC
# MAGIC Filtering chooses rows. Projection chooses columns. `SELECT *` on 25 columns reads
# MAGIC all 25 regardless of how good your filter is.
# MAGIC </details>
# MAGIC <!-- task:end -->

# COMMAND ----------

from pyspark.sql import functions as F

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")
SOURCE = "pro_s6_assess_orders"      # do not optimise it; the state is the evidence
TARGET = "pro_s6_optimization_report"
orders = spark.table(SOURCE)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 0 — describe the table
# MAGIC
# MAGIC `DESCRIBE DETAIL` gives file counts and sizes; the schema gives width.

# COMMAND ----------

# display(spark.sql(f"DESCRIBE DETAIL {SOURCE}"))
# print(len(orders.columns), "columns")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1 — small_files
# MAGIC
# MAGIC The number of files in the table, and what that means per file.

# COMMAND ----------

# num_files = ...

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2 — wide_projection
# MAGIC
# MAGIC The number of columns, and what a typical query actually needs.

# COMMAND ----------

# num_columns = len(orders.columns)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3 — bad_cluster_key
# MAGIC
# MAGIC For each candidate column, distinct values as a percentage of rows. Requirement 2: name the column that would be the wrong choice, and say what to cluster on instead.

# COMMAND ----------

# n = orders.count()
# for c in orders.columns:
#     print(c, orders.select(c).distinct().count() * 100.0 / n)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 4 — write the report
# MAGIC
# MAGIC One row per finding with a recommendation and a detail that cites a number.

# COMMAND ----------

# rows = [("small_files", "...", float(num_files), "..."), ("wide_projection", "...", float(num_columns), "..."), ("bad_cluster_key", "...", float(...), "...")]
# spark.createDataFrame(rows, "finding STRING, recommendation STRING, metric DOUBLE, detail STRING") \
#     .write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(TARGET)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Check yourself before grading

# COMMAND ----------

# display(spark.table(TARGET))
