# Databricks notebook source
# MAGIC %md
# MAGIC # ASSOC-S2 assignment — your work goes here
# MAGIC
# MAGIC Read `README.md` in this folder for the task and the output contract.
# MAGIC
# MAGIC **The lesson's code will not solve this.** The source has a different shape.
# MAGIC Copying `01_copy_into.py` or `02_auto_loader.py` and changing the paths
# MAGIC produces a table that fails the tests — that is deliberate, and the failures
# MAGIC will tell you which assumption broke.
# MAGIC
# MAGIC Grade your work with:
# MAGIC ```
# MAGIC databricks bundle run grade_assoc_s2 -t free --profile FREE
# MAGIC ```

# COMMAND ----------

from pyspark.sql import functions as F

CATALOG, SCHEMA = "workspace", "de_prep"
RAW = f"/Volumes/{CATALOG}/{SCHEMA}/raw/s2_assess"
TARGET = "silver_sensor_readings"

spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 0 — look at the source first
# MAGIC
# MAGIC You have not been told the schema. Find it. What shape are the records, what
# MAGIC type is the timestamp field, and is every file the same?

# COMMAND ----------

for f in dbutils.fs.ls(RAW):
    print(f.name, f"{f.size:,} bytes")

# COMMAND ----------

# Print the schema of a single file, then of all of them. Are they the same?
# spark.read.json(f"{RAW}/events_2026-03-01.json").printSchema()


# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1 — read the source
# MAGIC
# MAGIC Mind the batch whose schema differs.

# COMMAND ----------

# raw = ...


# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2 — reshape to one row per reading

# COMMAND ----------




# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3 — types, and the timestamp
# MAGIC
# MAGIC Check your dates land in 2026 before moving on. A wrong unit here produces no
# MAGIC error at all.

# COMMAND ----------




# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 4 — deduplicate on the business key

# COMMAND ----------




# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 5 — write the contracted table
# MAGIC
# MAGIC Column order matters; the tests compare the whole schema.

# COMMAND ----------

# final.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(TARGET)


# COMMAND ----------

# MAGIC %md
# MAGIC ## Check yourself before grading

# COMMAND ----------

# t = spark.table(TARGET)
# print("rows:", t.count(), "| distinct event_id:", t.select("event_id").distinct().count())
# t.printSchema()
# display(t.orderBy("event_id").limit(5))
