# Databricks notebook source
# MAGIC %md
# MAGIC # Retention and purging — `PRO-S7-O4`, `PRO-S7-O5`

# COMMAND ----------

from pyspark.sql import functions as F
from datetime import date

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")
TODAY = date(2026, 3, 31)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Masking is not deletion
# MAGIC
# MAGIC A masked row is still a retained row. If a policy says data must be *deleted*
# MAGIC after a period, or a subject has asked for erasure, masking does not satisfy it —
# MAGIC the record still exists, and a mask can be dropped by anyone who can alter the
# MAGIC table.
# MAGIC
# MAGIC | Requirement | Satisfied by |
# MAGIC |---|---|
# MAGIC | "Analysts must not see this" | a mask or a filter |
# MAGIC | "We must not hold this after N days" | deletion |
# MAGIC | "This person asked to be forgotten" | deletion |

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Deleting from a Delta table
# MAGIC
# MAGIC A `DELETE` removes rows from the current version — but **earlier versions still
# MAGIC contain them**, which is exactly what time travel is for. That is a feature for
# MAGIC recovery and a problem for erasure.

# COMMAND ----------

src = spark.table("pro_s7_teach_subjects")
src.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable("pro_s7_teach_retention_demo")

before = spark.table("pro_s7_teach_retention_demo").count()
spark.sql("DELETE FROM pro_s7_teach_retention_demo WHERE created_on < DATE'2026-02-01'")
after = spark.table("pro_s7_teach_retention_demo").count()
print(f"rows {before} -> {after}")

v0 = spark.sql("SELECT count(*) AS n FROM pro_s7_teach_retention_demo VERSION AS OF 0").collect()[0]["n"]
print(f"version 0 still holds {v0} rows - the deleted data is recoverable")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Completing an erasure
# MAGIC
# MAGIC To make deletion final, the history has to be expired too:
# MAGIC
# MAGIC ```sql
# MAGIC ALTER TABLE t SET TBLPROPERTIES (delta.deletedFileRetentionDuration = 'interval 0 days');
# MAGIC VACUUM t RETAIN 0 HOURS;
# MAGIC ```
# MAGIC
# MAGIC `VACUUM` removes files no longer referenced by the retained history. Until it
# MAGIC runs, "deleted" means "not in the current version" — which is not what a
# MAGIC regulator means by deleted.
# MAGIC
# MAGIC > Retaining zero hours breaks time travel and can disrupt concurrent readers.
# MAGIC > It is the right call for an erasure request and the wrong default for a table.

# COMMAND ----------

display(spark.sql("DESCRIBE HISTORY pro_s7_teach_retention_demo").select(
    "version", "operation", "operationMetrics"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. A retention policy is a cutoff per category
# MAGIC
# MAGIC One cutoff for everything is almost always wrong: it either keeps marketing data
# MAGIC too long or deletes transaction logs a regulator requires you to hold.

# COMMAND ----------

policy = spark.createDataFrame(
    [("support_ticket", 365), ("marketing_event", 90), ("transaction_log", 2555)],
    "record_type STRING, retain_days INT")
display(policy.withColumn(
    "cutoff", F.date_sub(F.lit(TODAY), F.col("retain_days"))))

# COMMAND ----------

# MAGIC %md
# MAGIC ## What to carry forward
# MAGIC
# MAGIC - Masking hides; only deletion deletes.
# MAGIC - A Delta `DELETE` leaves the rows in history until `VACUUM` expires them.
# MAGIC - Retention is per category, and a single cutoff is a bug in both directions.
# MAGIC
# MAGIC The assignment combines all three: PII hidden in free text, subjects who have
# MAGIC asked for erasure, and three record types with three retention periods.
