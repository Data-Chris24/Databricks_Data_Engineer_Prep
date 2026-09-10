# Databricks notebook source
# MAGIC %md
# MAGIC # PRO-S2 — Data Ingestion & Acquisition assignment
# MAGIC
# MAGIC Read `README.md` first. The contract there is what the tests check.
# MAGIC
# MAGIC Produce:
# MAGIC - `workspace.de_prep.pro_s2_scans_bronze` — append-only, every delivered record
# MAGIC - `workspace.de_prep.pro_s2_scans` — one row per scan, latest revision

# COMMAND ----------

from pyspark.sql import Window
from pyspark.sql import functions as F

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")
ROOT = "/Volumes/workspace/de_prep/raw/pro_s2/assess"

display(dbutils.fs.ls(ROOT))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Read each source and look at what you got
# MAGIC
# MAGIC Check the column **order** and the column **types**, not just the names. Two of
# MAGIC these will union together without complaining and still be wrong.

# COMMAND ----------

# TODO: one reader per format


# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Bronze — append everything

# COMMAND ----------

# TODO
# bronze.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable("pro_s2_scans_bronze")


# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Silver — one row per scan
# MAGIC
# MAGIC Some scans were sent twice. Decide which copy wins, and be able to say why.

# COMMAND ----------

# TODO
# silver.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable("pro_s2_scans")


# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Check yourself before you grade
# MAGIC
# MAGIC Three quick ones that catch most of the ways this goes quietly wrong:
# MAGIC
# MAGIC - every `facility` value is a real facility
# MAGIC - no null `scanned_at`
# MAGIC - bronze row count > silver row count, by exactly the number of corrections

# COMMAND ----------

# TODO
