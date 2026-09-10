# Databricks notebook source
# MAGIC %md
# MAGIC # PRO-S9 assignment — your work goes here
# MAGIC
# MAGIC Read `README.md` in this folder for the task and the output contract.
# MAGIC
# MAGIC **There is no error to read. Every run succeeded. The evidence is in the data, not the run history.**
# MAGIC
# MAGIC When you are done, go back to the study app and press **Grade my assignment**.
# MAGIC Each failing check says what it expected and why.

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

# display(daily.groupBy("run_date").agg(F.sum("rows").alias("rows")).orderBy("run_date"))
# display(daily.groupBy("source_system").agg(F.max("run_date").alias("last_seen")))

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

# spark.createDataFrame([(first_bad_date, missing_source, degraded_days, rows_lost, detail)],
#                       "first_bad_date STRING, missing_source STRING, degraded_days INT, rows_lost INT, detail STRING") \
#     .write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(TARGET)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Check yourself before grading

# COMMAND ----------

# display(spark.table(TARGET))
