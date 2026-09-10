# Databricks notebook source
# MAGIC %md
# MAGIC # ASSOC-S5 assignment — reference solution
# MAGIC
# MAGIC One definition, two destinations. The destination is never written down here —
# MAGIC it arrives as a parameter, which is what makes the same notebook promotable.

# COMMAND ----------

dbutils.widgets.text("target_catalog", "")
dbutils.widgets.text("target_schema", "")
target_catalog = dbutils.widgets.get("target_catalog")
target_schema = dbutils.widgets.get("target_schema")

if not target_catalog or not target_schema:
    raise ValueError("target_catalog and target_schema must be supplied by the job")
print(f"publishing to {target_catalog}.{target_schema}")

# COMMAND ----------

from pyspark.sql import functions as F

SOURCE = "workspace.de_prep.s5_source_transactions"
TARGET = f"{target_catalog}.{target_schema}.s5_channel_summary"

summary = (spark.table(SOURCE)
    .groupBy("channel")
    .agg(F.count("*").alias("txns"),
         F.round(F.sum("amount"), 2).alias("revenue"))
    # Recording where a row was written makes the promotion visible in the data,
    # and is what lets the grader tell the two environments apart.
    .withColumn("environment", F.lit(target_schema)))

summary.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(TARGET)
print(f"wrote {spark.table(TARGET).count()} rows to {TARGET}")
display(spark.table(TARGET).orderBy("channel"))
