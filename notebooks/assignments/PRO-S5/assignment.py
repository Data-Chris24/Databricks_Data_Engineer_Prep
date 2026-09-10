# Databricks notebook source
# MAGIC %md
# MAGIC # PRO-S5 assignment — your work goes here
# MAGIC
# MAGIC Read `README.md` in this folder for the task and the output contract.
# MAGIC
# MAGIC **The lesson's fixed threshold cannot work here, and you can prove it: no single number separates weekends from degraded weekdays.**
# MAGIC
# MAGIC When you are done, go back to the study app and press **Grade my assignment**.
# MAGIC Each failing check says what it expected and why.

# COMMAND ----------

from pyspark.sql import Window
from pyspark.sql import functions as F

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")
SOURCE = "pro_s5_assess_metrics"
TARGET = "pro_s5_alert_evaluation"
metrics = spark.table(SOURCE).orderBy("run_date")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 0 — look at the series
# MAGIC
# MAGIC Plot or list `rows_processed` by date. Where is the weekly cycle, where is the campaign, where does the degradation start?

# COMMAND ----------

# display(metrics)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1 — day_type
# MAGIC
# MAGIC `weekday` or `weekend`. Requirement 1: baselines compare like with like.

# COMMAND ----------

# typed = metrics.withColumn("day_type", F.when(F.dayofweek("run_date").isin(1, 7), "weekend").otherwise("weekday"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2 — a baseline from prior history of the same day type
# MAGIC
# MAGIC Only earlier days count (no peeking), and days without enough history are excluded.

# COMMAND ----------

# w = Window.partitionBy("day_type").orderBy("run_date").rowsBetween(-N, -1)
# with_base = typed.withColumn("baseline", F.avg("rows_processed").over(w)).filter("baseline IS NOT NULL")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3 — pct_of_baseline and the alert rule
# MAGIC
# MAGIC Requirement 3: alert on direction, not deviation, so the campaign spike stays quiet. Requirement 2: nothing fires in the healthy period; Requirement 4: the degradation is caught reasonably promptly.

# COMMAND ----------

# evaluated = with_base.withColumn("pct_of_baseline", F.col("rows_processed") * 100.0 / F.col("baseline")) \
#                      .withColumn("should_alert", ...)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 4 — write the evaluation
# MAGIC
# MAGIC One row per evaluated day, contracted column order.

# COMMAND ----------

# evaluated.select("run_date", "day_type", "rows_processed", "baseline", "pct_of_baseline", "should_alert") \
#     .write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(TARGET)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Check yourself before grading

# COMMAND ----------

# e = spark.table(TARGET); display(e.filter("should_alert").orderBy("run_date"))
