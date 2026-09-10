# Databricks notebook source
# MAGIC %md
# MAGIC # PRO-S3 assignment — your work goes here
# MAGIC
# MAGIC Read `README.md` in this folder for the task and the output contract.
# MAGIC
# MAGIC **Every row in this table is individually valid. The lesson's row-level rules find nothing; the problems live in the sequence.**
# MAGIC
# MAGIC When you are done, go back to the study app and press **Grade my assignment**.
# MAGIC Each failing check says what it expected and why.

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

# with_prev = readings.withColumn("prev", F.lag("reading").over(w))
# backwards = with_prev.filter("reading < prev")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2 — sequence_gap
# MAGIC
# MAGIC Readings arrive every 15 minutes. An interval longer than that means readings are missing.

# COMMAND ----------

# with_gap = readings.withColumn("prev_ts", F.lag("reading_ts").over(w))
# gaps = with_gap.filter(F.col("reading_ts").cast("long") - F.col("prev_ts").cast("long") > 15 * 60)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3 — duplicate_timestamp
# MAGIC
# MAGIC More than one reading for a device at the same instant.

# COMMAND ----------

# dups = readings.groupBy("device_id", "reading_ts").count().filter("count > 1")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 4 — write the findings
# MAGIC
# MAGIC One row each. `affected_devices` sorted and comma-separated; `detail` cites a number.

# COMMAND ----------

# def devices(df): return ",".join(sorted(r[0] for r in df.select("device_id").distinct().collect()))
# rows = [("meter_backwards", float(...), devices(backwards), "..."), ...]
# spark.createDataFrame(rows, "finding STRING, affected_rows DOUBLE, affected_devices STRING, detail STRING") \
#     .write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(TARGET)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Check yourself before grading

# COMMAND ----------

# display(spark.table(TARGET))
