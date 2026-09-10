# Databricks notebook source
# MAGIC %md
# MAGIC # PRO-S6 assignment — your work goes here
# MAGIC
# MAGIC Read `README.md` in this folder for the task and the output contract.
# MAGIC
# MAGIC **The lesson's table was slow for one reason and clustering fixed it. This one is slow for three, and clustering the wrong column would make it worse.**
# MAGIC
# MAGIC When you are done, go back to the study app and press **Grade my assignment**.
# MAGIC Each failing check says what it expected and why.

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
