# Databricks notebook source
# MAGIC %md
# MAGIC # PRO-S7 — generate the `teach` and `assess` datasets
# MAGIC
# MAGIC Security and compliance at Professional level: anonymisation techniques and data
# MAGIC purging, not just access control.
# MAGIC
# MAGIC ## What makes the assignment un-copyable
# MAGIC
# MAGIC 1. **The teach table has PII in known columns.** Hash the identifier, mask the
# MAGIC    rest — a column-by-column job.
# MAGIC 2. **The assess table hides PII inside free text.** An email address in a
# MAGIC    comment field is not addressed by masking the columns you know about.
# MAGIC 3. **Some records must be purged entirely**, not masked — an erasure request
# MAGIC    means the row goes, and a masked row is still a retained row.
# MAGIC 4. **Retention differs by record type**, so a single cutoff date is wrong.

# COMMAND ----------

import random
from datetime import date, timedelta

CATALOG, SCHEMA = "workspace", "de_prep"
SEED = 20260904
spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## `teach` — PII in known columns

# COMMAND ----------

rng = random.Random(SEED)
FIRST = ["Ana", "Ben", "Chi", "Dee", "Eli", "Fay", "Gus", "Hana"]
LAST = ["Torres", "Okafor", "Nguyen", "Silva", "Meyer", "Haddad", "Kaur", "Rossi"]
base = date(2026, 1, 1)

rows = []
for i in range(1, 201):
    f, l = rng.choice(FIRST), rng.choice(LAST)
    rows.append((f"SUB-{i:05d}", f"{f} {l}", f"{f.lower()}.{l.lower()}{i}@example.com",
                 f"+44 7700 {rng.randint(100000, 999999)}",
                 base + timedelta(days=rng.randint(0, 300))))

spark.createDataFrame(
    rows, "subject_id STRING, full_name STRING, email STRING, phone STRING, created_on DATE"
).write.mode("overwrite").saveAsTable("pro_s7_teach_subjects")
print("teach rows:", spark.table("pro_s7_teach_subjects").count())

# COMMAND ----------

# MAGIC %md
# MAGIC ## `assess` — PII in free text, erasure requests, and per-type retention

# COMMAND ----------

rng = random.Random(SEED + 29)
TYPES = ["support_ticket", "marketing_event", "transaction_log"]
# Retention differs by type - a single cutoff would over-delete or under-delete.
RETENTION_DAYS = {"support_ticket": 365, "marketing_event": 90, "transaction_log": 2555}

CLEAN_NOTES = [
    "Customer asked about delivery timescales.",
    "Issue resolved on first contact.",
    "Escalated to the billing team.",
    "No further action required.",
]

rows = []
today = date(2026, 3, 31)
pii_in_text = 0

for i in range(1, 601):
    f, l = rng.choice(FIRST), rng.choice(LAST)
    rec_type = rng.choice(TYPES)
    age = rng.randint(0, 900)
    created = today - timedelta(days=age)

    # ~18% of notes contain an email address or phone number in free text.
    if rng.random() < 0.18:
        pii_in_text += 1
        leak = (f"Contact them on {f.lower()}.{l.lower()}{i}@example.com"
                if rng.random() < 0.6 else
                f"Call back on +44 7700 {rng.randint(100000, 999999)}")
        note = f"{rng.choice(CLEAN_NOTES)} {leak}"
    else:
        note = rng.choice(CLEAN_NOTES)

    rows.append((f"REC-{i:05d}", f"SUBJ-{rng.randint(1, 120):05d}", rec_type,
                 f"{f} {l}", note, created))

spark.createDataFrame(
    rows,
    "record_id STRING, subject_id STRING, record_type STRING, full_name STRING, "
    "case_note STRING, created_on DATE",
).write.mode("overwrite").saveAsTable("pro_s7_assess_records")

# Erasure requests: these subjects must be removed entirely, not masked.
erasure = sorted({f"SUBJ-{rng.randint(1, 120):05d}" for _ in range(14)})
spark.createDataFrame(
    [(s, today - timedelta(days=rng.randint(0, 60))) for s in erasure],
    "subject_id STRING, requested_on DATE",
).write.mode("overwrite").saveAsTable("pro_s7_assess_erasure_requests")

print("assess records:", spark.table("pro_s7_assess_records").count())
print("notes containing PII:", pii_in_text)
print("erasure requests:", len(erasure))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Prove the traps are real

# COMMAND ----------

from pyspark.sql import functions as F

t = spark.table("pro_s7_assess_records")
EMAIL = r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
PHONE = r"\+?\d[\d\s]{8,}\d"

leaky = t.filter(F.col("case_note").rlike(EMAIL) | F.col("case_note").rlike(PHONE)).count()
er = spark.table("pro_s7_assess_erasure_requests")
affected = t.join(er, on="subject_id", how="inner").count()

per_type = {r["record_type"]: r["n"] for r in
            t.groupBy("record_type").agg(F.count("*").alias("n")).collect()}

print(f"records with PII in free text: {leaky}")
print(f"records belonging to erasure subjects: {affected}")
print(f"record types: {per_type}")

assert leaky > 0, "no PII hidden in free text - column masking alone would suffice"
assert affected > 0, "no erasure-affected records - purging is not tested"
assert len(per_type) == 3, "need several record types for per-type retention to matter"
print("\ntraps present")
