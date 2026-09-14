# Databricks notebook source
# MAGIC %md
# MAGIC # ASSOC-S3 assignment — your work goes here
# MAGIC
# MAGIC The task and the output contract are in the next cell (the same text as `README.md` in the repo).
# MAGIC
# MAGIC **The lesson's joins will not survive this data.** Inspect the source before
# MAGIC writing anything.

# COMMAND ----------

# MAGIC %md
# MAGIC <!-- task:begin  generated from README.md by tools/sync_assignment_tasks.py; edit the README, then re-run it -->
# MAGIC ## Assignment — `ASSOC-S3` Data Transformation and Modeling
# MAGIC
# MAGIC **Objectives:** `ASSOC-S3-O1`, `O2`, `O4`, `O6`, `O7`
# MAGIC
# MAGIC ### Before you start
# MAGIC
# MAGIC Work through the three lessons in `notebooks/lessons/associate/S3/`, and make sure
# MAGIC the tables exist (`databricks bundle run generate_datasets_assoc_s3 -t free`).
# MAGIC
# MAGIC > **The lesson's joins will not survive this data.** The lessons used clean
# MAGIC > dimensions — one row per key, every foreign key resolving. This source has neither.
# MAGIC > Copy the lesson and you will produce a table with the wrong number of rows.
# MAGIC
# MAGIC ### The task
# MAGIC
# MAGIC Enrich `s3_assess_billing_events` with plan details from `s3_assess_plans` and produce
# MAGIC an analysis-ready gold table.
# MAGIC
# MAGIC **Inspect both tables first.** In particular, check whether `plan_id` is unique in the
# MAGIC dimension, and what `amount_cents` actually contains.
# MAGIC
# MAGIC ### The output contract
# MAGIC
# MAGIC Create **`workspace.de_prep.s3_gold_billing_enriched`** with exactly this schema, in
# MAGIC this order:
# MAGIC
# MAGIC | Column | Type | Meaning |
# MAGIC |---|---|---|
# MAGIC | `billing_id` | `STRING` | Unique. One row per billing event |
# MAGIC | `account_id` | `STRING` | |
# MAGIC | `plan_id` | `STRING` | As recorded on the event |
# MAGIC | `event_date` | `DATE` | |
# MAGIC | `event_type` | `STRING` | `charge` or `refund` |
# MAGIC | `amount` | `DOUBLE` | The event amount **in currency units, not minor units** |
# MAGIC | `signed_amount` | `DOUBLE` | Negative for refunds, positive for charges |
# MAGIC | `plan_name` | `STRING` | From the plan version in effect **on the event date**. Null when unknown |
# MAGIC | `tier` | `STRING` | Same. Null when unknown |
# MAGIC | `plan_missing` | `BOOLEAN` | True when no plan version matched |
# MAGIC
# MAGIC #### Requirements
# MAGIC
# MAGIC 1. **Exactly one row per billing event.** Not one per event-plan pair.
# MAGIC 2. **No event may be dropped**, including events whose plan is absent from the
# MAGIC    dimension. Flag those with `plan_missing`.
# MAGIC 3. **Use the plan version in effect on the event date.** Plans change price over time.
# MAGIC 4. **`amount` is in currency units.** Get this wrong and every total is 100x out, with
# MAGIC    no error.
# MAGIC 5. **Column order matters** — the tests compare the whole schema.
# MAGIC
# MAGIC ### Grading
# MAGIC
# MAGIC ```bash
# MAGIC databricks bundle run grade_assoc_s3 -t free --profile FREE
# MAGIC ```
# MAGIC
# MAGIC ### Hints
# MAGIC
# MAGIC <details><summary>My row count is 870, not 600</summary>
# MAGIC
# MAGIC `plan_id` appears more than once in the dimension — it is slowly-changing. A join
# MAGIC returns one row per matching *pair*. Put the validity window in the join condition.
# MAGIC </details>
# MAGIC
# MAGIC <details><summary>My row count is 580</summary>
# MAGIC
# MAGIC An inner join dropped the events whose plan is missing. Requirement 2.
# MAGIC </details>
# MAGIC
# MAGIC <details><summary>My totals look enormous</summary>
# MAGIC
# MAGIC Requirement 4. Look at the raw column name.
# MAGIC </details>
# MAGIC <!-- task:end -->

# COMMAND ----------

from pyspark.sql import functions as F

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")
TARGET = "s3_gold_billing_enriched"

events = spark.table("s3_assess_billing_events")
plans = spark.table("s3_assess_plans")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 0 — look before you join
# MAGIC
# MAGIC Is `plan_id` unique in the dimension? Do all event plan_ids exist there? What
# MAGIC does `amount_cents` hold?

# COMMAND ----------

display(plans.orderBy("plan_id", "valid_from"))

# COMMAND ----------

# How many rows would a naive equi-join produce? Compare it to the event count.
# print("events:", events.count())
# print("naive :", events.join(plans, on="plan_id").count())


# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1 — join correctly

# COMMAND ----------




# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2 — amounts

# COMMAND ----------




# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3 — write the contracted table

# COMMAND ----------

# final.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(TARGET)


# COMMAND ----------

# MAGIC %md
# MAGIC ## Check yourself before grading

# COMMAND ----------

# t = spark.table(TARGET)
# print("rows:", t.count(), "| distinct billing_id:", t.select("billing_id").distinct().count())
# print("orphans:", t.filter("plan_missing").count())
# t.printSchema()
