# Databricks notebook source
# MAGIC %md
# MAGIC # PRO-S7 assignment — reference solution
# MAGIC
# MAGIC Three requirements the lesson's column-by-column approach does not meet: PII
# MAGIC inside free text, subjects who must be purged rather than masked, and retention
# MAGIC that differs by record type.

# COMMAND ----------

from pyspark.sql import functions as F
from datetime import date

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")
SRC = "pro_s7_assess_records"
ERASURE = "pro_s7_assess_erasure_requests"
TARGET = "pro_s7_compliant_records"
TODAY = date(2026, 3, 31)
SALT = "per-dataset-salt-kept-in-a-secret-scope"

records = spark.table(SRC)
erasure = spark.table(ERASURE)
print("records:", records.count(), " erasure requests:", erasure.count())

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Purge erasure subjects — before anything else
# MAGIC
# MAGIC Order matters. Masking first and purging second wastes work; worse, it invites
# MAGIC the mistake of masking an erasure subject and calling it done. A masked row is a
# MAGIC retained row.

# COMMAND ----------

purged = records.join(erasure.select("subject_id"), on="subject_id", how="left_anti")
purged_count = records.count() - purged.count()
print(f"purged {purged_count} records belonging to {erasure.count()} erasure subjects")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Apply per-type retention
# MAGIC
# MAGIC One cutoff for everything would either keep marketing data too long or delete
# MAGIC transaction logs that must be retained.

# COMMAND ----------

policy = spark.createDataFrame(
    [("support_ticket", 365), ("marketing_event", 90), ("transaction_log", 2555)],
    "record_type STRING, retain_days INT")

with_policy = (purged.join(policy, on="record_type", how="left")
    .withColumn("cutoff", F.date_sub(F.lit(TODAY), F.col("retain_days"))))

retained = with_policy.filter(F.col("created_on") >= F.col("cutoff"))
expired = with_policy.count() - retained.count()
print(f"expired {expired} records under per-type retention")
display(with_policy.groupBy("record_type")
        .agg(F.count("*").alias("total"),
             F.sum((F.col("created_on") < F.col("cutoff")).cast("int")).alias("expired"))
        .orderBy("record_type"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Scrub PII from free text
# MAGIC
# MAGIC The part a column-by-column approach misses entirely. `case_note` is prose, and
# MAGIC some of it contains email addresses and phone numbers.

# COMMAND ----------

EMAIL = r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
PHONE = r"\+?\d[\d\s]{8,}\d"

leaky_before = retained.filter(
    F.col("case_note").rlike(EMAIL) | F.col("case_note").rlike(PHONE)).count()
print("notes containing PII before scrubbing:", leaky_before)

scrubbed = (retained
    .withColumn("case_note", F.regexp_replace("case_note", EMAIL, "[EMAIL REDACTED]"))
    .withColumn("case_note", F.regexp_replace("case_note", PHONE, "[PHONE REDACTED]")))

leaky_after = scrubbed.filter(
    F.col("case_note").rlike(EMAIL) | F.col("case_note").rlike(PHONE)).count()
print("notes containing PII after scrubbing :", leaky_after)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. De-identify the known columns and publish

# COMMAND ----------

final = (scrubbed
    .withColumn("subject_hash", F.sha2(F.concat(F.lit(SALT), F.col("subject_id")), 256))
    .select("record_id", "subject_hash", "record_type", "case_note", "created_on"))

final.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(TARGET)
print("published rows:", spark.table(TARGET).count())
spark.table(TARGET).printSchema()

# COMMAND ----------

import json
t = spark.table(TARGET)
print(json.dumps({
    "source_rows": records.count(),
    "purged_rows": purged_count,
    "expired_rows": expired,
    "published_rows": t.count(),
    "leaky_before": leaky_before,
    "leaky_after": leaky_after,
    "redacted_notes": t.filter(F.col("case_note").rlike(r"\[(EMAIL|PHONE) REDACTED\]")).count(),
    "hash_length": len(t.select("subject_hash").first()[0]),
}, indent=2))
