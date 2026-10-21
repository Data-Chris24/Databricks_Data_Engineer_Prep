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
# MAGIC the record still exists, and the table's owner (or anyone with `MANAGE` on it)
# MAGIC can drop the mask.
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
# MAGIC To make deletion final, the history has to be expired too. New tables have
# MAGIC **deletion vectors** on by default, so a `DELETE` does not rewrite the file: it
# MAGIC marks the row as deleted and leaves it in a file the *current* version still
# MAGIC references. `VACUUM` alone therefore never removes it. Purge first:
# MAGIC
# MAGIC ```sql
# MAGIC DELETE FROM t WHERE subject_id = '...';
# MAGIC REORG TABLE t APPLY (PURGE);   -- rewrite files that carry deletion vectors
# MAGIC ALTER TABLE t SET TBLPROPERTIES (delta.deletedFileRetentionDuration = 'interval 0 hours');
# MAGIC VACUUM t RETAIN 0 HOURS;       -- refused unless the property was lowered first
# MAGIC ALTER TABLE t SET TBLPROPERTIES (delta.deletedFileRetentionDuration = 'interval 7 days');
# MAGIC ```
# MAGIC
# MAGIC `VACUUM` removes files no longer referenced by the retained history. Until the
# MAGIC purge and the vacuum have both run, "deleted" means "not in the current version",
# MAGIC which is not what a regulator means by deleted. The last step puts the default
# MAGIC back so the table keeps normal time travel afterwards.
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
# MAGIC - A Delta `DELETE` leaves the rows in history, and with deletion vectors in the current files too, until `REORG ... APPLY (PURGE)` and `VACUUM` remove them.
# MAGIC - Retention is per category, and a single cutoff is a bug in both directions.
# MAGIC
# MAGIC The assignment combines all three: PII hidden in free text, subjects who have
# MAGIC asked for erasure, and three record types with three retention periods.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Next
# MAGIC
# MAGIC When the lessons are done, open the graded assignment: [PRO-S7 assignment notebook](../../../assignments/PRO-S7/assignment) · [the task](../../../assignments/PRO-S7/README.md).
