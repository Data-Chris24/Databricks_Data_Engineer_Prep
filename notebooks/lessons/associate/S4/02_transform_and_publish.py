# Databricks notebook source
# MAGIC %md
# MAGIC # Downstream tasks and conditional flow — `ASSOC-S4-O1`, `ASSOC-S4-O2`
# MAGIC
# MAGIC This task depends on `01_tasks_and_dependencies`. It reads the task value that
# MAGIC one set, which only works because the dependency guarantees ordering.

# COMMAND ----------

from pyspark.sql import functions as F

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Reading a task value from an upstream task

# COMMAND ----------

try:
    upstream_rows = dbutils.jobs.taskValues.get(
        taskKey="extract", key="row_count", default=None, debugValue=360)
    print("upstream reported row_count =", upstream_rows)
except Exception as e:
    upstream_rows = None
    print(f"task value unavailable ({type(e).__name__}) - running outside the job?")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Transform
# MAGIC
# MAGIC Bronze is text, as CSV always is. Cast here, and count what will not cast rather
# MAGIC than letting it fail the batch.

# COMMAND ----------

bronze = spark.table("s4_bronze_shipments")

silver = (bronze
    .withColumn("units", F.expr("try_cast(units AS INT)"))
    .withColumn("shipped_on", F.expr("try_cast(shipped_on AS DATE)")))

bad = silver.filter("units IS NULL OR shipped_on IS NULL").count()
print(f"rows that would not cast: {bad}")
silver.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable("s4_silver_shipments")
print("silver rows:", spark.table("s4_silver_shipments").count())

# COMMAND ----------

# MAGIC %md
# MAGIC `try_cast` returns null on a bad value; plain `cast` **raises** under ANSI
# MAGIC semantics and fails the whole task. Use `try_cast` when you want to *find* bad
# MAGIC values rather than be stopped by them.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Publish, and hand a decision downstream
# MAGIC
# MAGIC A conditional task branches on a task value. Setting one here lets the job decide
# MAGIC whether a follow-up step is needed — and the run graph records which way it went,
# MAGIC which an `if` inside a notebook would not.

# COMMAND ----------

gold = (spark.table("s4_silver_shipments")
        .groupBy("region")
        .agg(F.count("*").alias("shipments"), F.sum("units").alias("total_units")))

gold.write.mode("overwrite").saveAsTable("s4_gold_region_summary")
display(spark.table("s4_gold_region_summary").orderBy("region"))

dbutils.jobs.taskValues.set(key="needs_review", value="true" if bad else "false")
print(f"set needs_review = {'true' if bad else 'false'}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## What to carry forward
# MAGIC
# MAGIC - Dependencies are what make an upstream task value readable here.
# MAGIC - `try_cast` finds bad values; `cast` stops on them.
# MAGIC - Branch in the **job graph**, not inside a notebook, so the run history shows
# MAGIC   which path a run took.
# MAGIC
# MAGIC Now do the assignment. Its source has a poisoned region, and this linear chain
# MAGIC will not survive it.
