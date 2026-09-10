# Databricks notebook source
# MAGIC %md
# MAGIC # ASSOC-S4 assignment — your work goes here
# MAGIC
# MAGIC Read `README.md` in this folder for the task and the output contract.
# MAGIC
# MAGIC **The lesson's linear chain will not survive this source. One file has a value that will not cast, and there is a directory the main glob never looks at.**
# MAGIC
# MAGIC When you are done, go back to the study app and press **Grade my assignment**.
# MAGIC Each failing check says what it expected and why.

# COMMAND ----------

from pyspark.sql import functions as F

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")
RAW = "/Volumes/workspace/de_prep/raw/s4_assess"
GOLD = "s4_gold_regional_orders"
QUARANTINE = "s4_quarantine_orders"

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 0 — look at the landing area, including subdirectories
# MAGIC
# MAGIC Requirement 3: the late arrivals live somewhere the obvious glob misses.

# COMMAND ----------

for f in dbutils.fs.ls(RAW):
    print(f.path, f.size)
# What is inside any subdirectory?

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1 — read everything as text, remembering the file
# MAGIC
# MAGIC Requirement 1: a value that will not cast must not stop the read. Read as strings and keep `_metadata.file_path` (or `input_file_name()`) so quarantine can cite the file.

# COMMAND ----------

# raw = (spark.read.option("header", True).csv(...)
#            .withColumn("source_file", F.col("_metadata.file_path")))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2 — separate what publishes from what does not
# MAGIC
# MAGIC `try_cast` returns null where `cast` raises. A row with any failed cast goes to quarantine with its raw values.

# COMMAND ----------

# typed = raw.withColumn("units", F.expr("try_cast(raw_units AS INT)")) ...
# good = typed.filter(...)
# bad = typed.filter(...)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3 — write both tables, idempotently
# MAGIC
# MAGIC Requirement 4: the grader runs this twice. `append` doubles the data; choose a mode that does not.

# COMMAND ----------

# good.select("order_id", "region", "units", "ordered_on").write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(GOLD)
# bad.select("order_id", "region", "raw_units", "raw_ordered_on", "source_file").write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(QUARANTINE)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Check yourself before grading

# COMMAND ----------

# print("published:", spark.table(GOLD).count(), "| quarantined:", spark.table(QUARANTINE).count())
# Run this notebook a second time: both counts must be unchanged.
