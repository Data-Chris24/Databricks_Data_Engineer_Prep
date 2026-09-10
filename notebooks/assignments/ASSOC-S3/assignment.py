# Databricks notebook source
# MAGIC %md
# MAGIC # ASSOC-S3 assignment — your work goes here
# MAGIC
# MAGIC See `README.md` for the task and the output contract.
# MAGIC
# MAGIC **The lesson's joins will not survive this data.** Inspect the source before
# MAGIC writing anything.

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
