# Databricks notebook source
# MAGIC %md
# MAGIC # PRO-S7 assignment — your work goes here
# MAGIC
# MAGIC The task and the output contract are in the next cell (the same text as `README.md` in the repo).
# MAGIC
# MAGIC **The lesson masked the columns it knew held PII. That leaves this dataset non-compliant in three separate ways: retained subjects, expired records, and PII hiding in free text.**
# MAGIC
# MAGIC When you are done, go back to the study app and press **Grade my assignment**.
# MAGIC Each failing check says what it expected and why.

# COMMAND ----------

# MAGIC %md
# MAGIC <!-- task:begin  generated from README.md by tools/sync_assignment_tasks.py; edit the README, then re-run it -->
# MAGIC ## Assignment — `PRO-S7` Data Security and Compliance
# MAGIC
# MAGIC **Objectives:** `PRO-S7-O3`, `O4`, `O5`
# MAGIC
# MAGIC ### Before you start
# MAGIC
# MAGIC Work the two lessons in `notebooks/lessons/professional/S7/`, and generate the data
# MAGIC (the study app runs the `generate_datasets_pro_s7` job the first time you open this section; `databricks bundle run generate_datasets_pro_s7 -t free` does the same from a terminal).
# MAGIC
# MAGIC > **The lesson masked the columns it knew held PII.** That approach leaves this
# MAGIC > dataset non-compliant in three separate ways.
# MAGIC
# MAGIC ### The task
# MAGIC
# MAGIC Publish a compliant version of `workspace.de_prep.pro_s7_assess_records`.
# MAGIC
# MAGIC Today's date, for retention purposes, is **2026-03-31**.
# MAGIC
# MAGIC ### The output contract
# MAGIC
# MAGIC **`workspace.de_prep.pro_s7_compliant_records`**
# MAGIC
# MAGIC | Column | Type |
# MAGIC |---|---|
# MAGIC | `record_id` | `STRING` |
# MAGIC | `subject_hash` | `STRING` |
# MAGIC | `record_type` | `STRING` |
# MAGIC | `case_note` | `STRING` |
# MAGIC | `created_on` | `DATE` |
# MAGIC
# MAGIC #### Requirements
# MAGIC
# MAGIC 1. **Subjects in `pro_s7_assess_erasure_requests` must be gone**, not masked. A
# MAGIC    masked row is a retained row.
# MAGIC 2. **Retention differs by `record_type`** — expire anything older than its own limit:
# MAGIC
# MAGIC    | `record_type` | Retain for |
# MAGIC    |---|---|
# MAGIC    | `support_ticket` | 365 days |
# MAGIC    | `marketing_event` | 90 days |
# MAGIC    | `transaction_log` | 2555 days |
# MAGIC
# MAGIC 3. **`case_note` is free text and some of it contains PII** — email addresses and
# MAGIC    phone numbers. It must not survive.
# MAGIC 4. **`subject_id` and `full_name` must not appear.** Publish a salted hash of the
# MAGIC    subject instead, so records remain groupable by subject.
# MAGIC 5. Column order matters — the tests compare the whole schema.
# MAGIC
# MAGIC ### Grading
# MAGIC
# MAGIC ```bash
# MAGIC databricks bundle run grade_pro_s7 -t free --profile FREE
# MAGIC ```
# MAGIC
# MAGIC ### Hints
# MAGIC
# MAGIC <details><summary>Does order matter?</summary>
# MAGIC
# MAGIC Yes. Purge erasure subjects first — masking them and then deleting is wasted work,
# MAGIC and masking them *instead* of deleting is the mistake requirement 1 is testing.
# MAGIC </details>
# MAGIC
# MAGIC <details><summary>How do I find PII inside prose?</summary>
# MAGIC
# MAGIC Pattern matching. `rlike` finds it; `regexp_replace` removes it. Test that none
# MAGIC survives rather than assuming your pattern caught everything.
# MAGIC </details>
# MAGIC
# MAGIC <details><summary>Why hash the subject rather than drop it?</summary>
# MAGIC
# MAGIC Requirement 4 — records must stay groupable by subject. Suppression would destroy
# MAGIC that; a deterministic hash preserves it.
# MAGIC </details>
# MAGIC <!-- task:end -->

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
