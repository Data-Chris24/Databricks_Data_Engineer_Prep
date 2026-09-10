# Databricks notebook source
# MAGIC %md
# MAGIC # ASSOC-S1 assignment — your work goes here
# MAGIC
# MAGIC Read `README.md` in this folder for the task and the output contract.
# MAGIC
# MAGIC **A query against the current table cannot produce the right answer. The data is not there any more; it is still recoverable.**
# MAGIC
# MAGIC When you are done, go back to the study app and press **Grade my assignment**.
# MAGIC Each failing check says what it expected and why.

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
