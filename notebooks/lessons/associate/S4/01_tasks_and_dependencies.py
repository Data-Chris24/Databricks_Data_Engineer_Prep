# Databricks notebook source
# MAGIC %md
# MAGIC # Tasks, dependencies and task values — `ASSOC-S4-O1`, `ASSOC-S4-O2`
# MAGIC
# MAGIC This notebook is one **task** in a job. Open the job's run page while it runs to
# MAGIC see it as a node in a graph — that view is what the exam asks you to reason about.
# MAGIC
# MAGIC Teach data: three clean regional files in `/Volumes/workspace/de_prep/raw/s4_teach`.

# COMMAND ----------

from pyspark.sql import functions as F

CATALOG, SCHEMA = "workspace", "de_prep"
SRC = f"/Volumes/{CATALOG}/{SCHEMA}/raw/s4_teach"
spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Extract
# MAGIC
# MAGIC A linear chain: this task extracts, the next transforms, the last publishes. Each
# MAGIC depends on the one before, so a failure stops everything downstream.

# COMMAND ----------

raw = (spark.read.format("csv").option("header", "true").load(f"{SRC}/*.csv"))
raw.write.mode("overwrite").saveAsTable("s4_bronze_shipments")
n = spark.table("s4_bronze_shipments").count()
print(f"extracted {n} shipment rows")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Task values — passing a result to the next task
# MAGIC
# MAGIC Task values are small pieces of data handed downstream, and they appear in the
# MAGIC run history so you can see what was passed. They are also what a conditional task
# MAGIC branches on.

# COMMAND ----------

dbutils.jobs.taskValues.set(key="row_count", value=n)
dbutils.jobs.taskValues.set(key="regions", value=[r["region"] for r in
                                                  raw.select("region").distinct().collect()])
print("set task values: row_count, regions")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Idempotence is what makes a retry safe
# MAGIC
# MAGIC **A retry reruns this task from the beginning.** If it appended, a retry would
# MAGIC append again and duplicate the data. `mode("overwrite")` above means running it
# MAGIC twice produces the same table — which is why the row count below does not move.
# MAGIC
# MAGIC Delta gives ACID guarantees per *write*, never across a task or a job. Nothing
# MAGIC rolls back for you.

# COMMAND ----------

raw.write.mode("overwrite").saveAsTable("s4_bronze_shipments")
print("after a second run:", spark.table("s4_bronze_shipments").count(), "- unchanged")

appended = spark.table("s4_bronze_shipments").count()
raw.write.mode("append").saveAsTable("s4_bronze_shipments")
print("after an append   :", spark.table("s4_bronze_shipments").count(),
      f"- doubled from {appended}; this is what a retry would do")

# Put it back.
raw.write.mode("overwrite").saveAsTable("s4_bronze_shipments")
print("restored          :", spark.table("s4_bronze_shipments").count())

# COMMAND ----------

# MAGIC %md
# MAGIC ## What to carry forward
# MAGIC
# MAGIC - A task's dependencies control **ordering**, not atomicity.
# MAGIC - A retry reruns the whole task. Design for that, or do not enable retries.
# MAGIC - Task values pass small results and are visible in the run history.
