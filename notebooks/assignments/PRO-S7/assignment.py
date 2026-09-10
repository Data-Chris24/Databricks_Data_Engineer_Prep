# Databricks notebook source
# MAGIC %md
# MAGIC # PRO-S7 assignment — your work goes here
# MAGIC
# MAGIC Read `README.md` in this folder for the task and the output contract.
# MAGIC
# MAGIC **The lesson masked the columns it knew held PII. That leaves this dataset non-compliant in three separate ways: retained subjects, expired records, and PII hiding in free text.**
# MAGIC
# MAGIC When you are done, go back to the study app and press **Grade my assignment**.
# MAGIC Each failing check says what it expected and why.

# COMMAND ----------

from pyspark.sql import functions as F

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")
RECORDS = "pro_s7_assess_records"
ERASURES = "pro_s7_assess_erasure_requests"
TARGET = "pro_s7_compliant_records"
TODAY = "2026-03-31"
SALT = "choose-a-secret"
records = spark.table(RECORDS)
erasures = spark.table(ERASURES)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 0 — look
# MAGIC
# MAGIC What is in `case_note`? Which record types exist, and how old are they?

# COMMAND ----------

# display(records.limit(10)); display(records.groupBy("record_type").count())

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1 — erase the subjects who asked
# MAGIC
# MAGIC Requirement 1: gone, not masked. An anti join, not a filter on a flag.

# COMMAND ----------

# kept = records.join(erasures, "subject_id", "left_anti")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2 — apply retention per record type
# MAGIC
# MAGIC Requirement 2: each type has its own limit, measured from TODAY.

# COMMAND ----------

# limits = {"support_ticket": 365, "marketing_event": 90, "transaction_log": 2555}
# retained = kept.filter(...)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3 — scrub PII out of the free text
# MAGIC
# MAGIC Requirement 3: email addresses and phone numbers must not survive. `regexp_replace` twice.

# COMMAND ----------

# scrubbed = retained.withColumn("case_note", F.regexp_replace("case_note", r"...", "[redacted]"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 4 — hash the subject and drop the identifiers
# MAGIC
# MAGIC Requirement 4: a salted hash keeps records groupable by subject; `subject_id` and `full_name` do not appear. Contracted column order.

# COMMAND ----------

# final = scrubbed.withColumn("subject_hash", F.sha2(F.concat(F.lit(SALT), F.col("subject_id")), 256)) \
#     .select("record_id", "subject_hash", "record_type", "case_note", "created_on")
# final.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(TARGET)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Check yourself before grading

# COMMAND ----------

# t = spark.table(TARGET); print(t.count()); display(t.filter(F.col("case_note").rlike("@")))   # should be empty
