# Databricks notebook source
# MAGIC %md
# MAGIC # ASSOC-S6 assignment — your work goes here
# MAGIC
# MAGIC The task and the output contract are in the next cell (the same text as `README.md` in the repo).
# MAGIC
# MAGIC **The lesson's GROUP BY finds one of three problems here. Two of them leave the row count and the distinct-key count looking perfectly normal.**
# MAGIC
# MAGIC When you are done, go back to the study app and press **Grade my assignment**.
# MAGIC Each failing check says what it expected and why.

# COMMAND ----------

# MAGIC %md
# MAGIC <!-- task:begin  generated from README.md by tools/sync_assignment_tasks.py; edit the README, then re-run it -->
# MAGIC ## Assignment — `ASSOC-S6` Troubleshooting, Monitoring and Optimization
# MAGIC
# MAGIC **Objectives:** `ASSOC-S6-O1`, `O2`, `O3`, `O4`
# MAGIC
# MAGIC ### Before you start
# MAGIC
# MAGIC Work the two lessons in `notebooks/lessons/associate/S6/`, and generate the data
# MAGIC (the study app runs the `generate_datasets_assoc_s6` job the first time you open this section; `databricks bundle run generate_datasets_assoc_s6 -t free` does the same from a terminal).
# MAGIC
# MAGIC > **The lesson's `GROUP BY` finds one of three problems here.** Two of them leave the
# MAGIC > row count and the distinct-key count looking perfectly normal.
# MAGIC
# MAGIC ### The task
# MAGIC
# MAGIC `workspace.de_prep.s6_assess_orders` is unhealthy in **three distinct ways**. Diagnose
# MAGIC all three and publish a report.
# MAGIC
# MAGIC You are graded on the **diagnosis**, not on a fix. Do not clean the table.
# MAGIC
# MAGIC ### The output contract
# MAGIC
# MAGIC **`workspace.de_prep.s6_health_report`** — one row per finding.
# MAGIC
# MAGIC | Column | Type | Meaning |
# MAGIC |---|---|---|
# MAGIC | `finding` | `STRING` | One of `duplicate_keys`, `null_regression`, `skew` |
# MAGIC | `column_name` | `STRING` | The column the finding concerns |
# MAGIC | `metric` | `DOUBLE` | The number that evidences it (see below) |
# MAGIC | `detail` | `STRING` | A sentence a colleague could act on |
# MAGIC
# MAGIC #### What `metric` must hold
# MAGIC
# MAGIC | `finding` | `metric` |
# MAGIC |---|---|
# MAGIC | `duplicate_keys` | how many rows are redeliveries |
# MAGIC | `null_regression` | how many nulls appear **after** the regression begins |
# MAGIC | `skew` | the largest group's share of all rows, as a percentage |
# MAGIC
# MAGIC #### Requirements
# MAGIC
# MAGIC 1. **All three findings**, one row each.
# MAGIC 2. Each names the **right column**.
# MAGIC 3. Each `metric` is correct.
# MAGIC 4. `detail` is non-trivial — a colleague should know what to do next.
# MAGIC
# MAGIC ### Grading
# MAGIC
# MAGIC ```bash
# MAGIC databricks bundle run grade_assoc_s6 -t free --profile FREE
# MAGIC ```
# MAGIC
# MAGIC ### Hints
# MAGIC
# MAGIC <details><summary>I only found the skew</summary>
# MAGIC
# MAGIC That is the one the lesson's query finds. Ask two more questions: does the row count
# MAGIC equal the distinct key count, and is the null rate the same across the whole date
# MAGIC range?
# MAGIC </details>
# MAGIC
# MAGIC <details><summary>How do I find a regression date?</summary>
# MAGIC
# MAGIC Group by date and compute the null rate per day. The regression is where it jumps.
# MAGIC </details>
# MAGIC
# MAGIC <details><summary>Duplicates or a legitimate repeat?</summary>
# MAGIC
# MAGIC Compare `count(*)` with `count(distinct order_id)`. If they differ, some order id
# MAGIC appears more than once.
# MAGIC </details>
# MAGIC <!-- task:end -->

# COMMAND ----------

from pyspark.sql import functions as F

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")
SOURCE = "s6_assess_orders"           # do not clean it; the state is the evidence
REPORT = "s6_health_report"
orders = spark.table(SOURCE)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 0 — look
# MAGIC
# MAGIC Row count, distinct keys, null counts per column, the biggest groups. Which numbers look normal but are not?

# COMMAND ----------

# print(orders.count(), orders.select("order_id").distinct().count())
# display(orders.describe())

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1 — duplicate_keys
# MAGIC
# MAGIC How many rows are redeliveries, i.e. rows beyond the first for a key?

# COMMAND ----------

# dup_rows = orders.count() - orders.select(<key>).distinct().count()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2 — null_regression
# MAGIC
# MAGIC A column that was fine and then started arriving null. Find when it begins and count the nulls after that point.

# COMMAND ----------

# by_day = orders.groupBy(<date col>).agg(F.sum(F.col(<col>).isNull().cast("int")).alias("nulls")).orderBy(<date col>)
# display(by_day)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3 — skew
# MAGIC
# MAGIC The largest group's share of all rows, as a percentage. Which column is skewed?

# COMMAND ----------

# shares = orders.groupBy(<col>).count().withColumn("pct", F.col("count") * 100.0 / orders.count()).orderBy(F.desc("pct"))
# display(shares)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 4 — write the report
# MAGIC
# MAGIC One row per finding, naming the column, with a `detail` a colleague could act on. Column order matters.

# COMMAND ----------

# rows = [("duplicate_keys", <column>, float(<metric>), "..."),
#         ("null_regression", <column>, float(<metric>), "..."),
#         ("skew", <column>, float(<metric>), "...")]
# spark.createDataFrame(rows, "finding STRING, column_name STRING, metric DOUBLE, detail STRING") \
#     .write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(REPORT)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Check yourself before grading

# COMMAND ----------

# display(spark.table(REPORT))
