# Databricks notebook source
# MAGIC %md
# MAGIC # PRO-S9 — generate the `teach` and `assess` datasets
# MAGIC
# MAGIC Debugging and deploying. The pairing differs in **how a failure presents**.
# MAGIC
# MAGIC ## What makes the assignment un-copyable
# MAGIC
# MAGIC 1. **The teach failure is loud and immediate.** A task raises, the run shows
# MAGIC    FAILED, and the error names the cause. Read the message, fix it.
# MAGIC 2. **The assess failures are silent.** The pipeline reports SUCCESS every time
# MAGIC    while producing wrong output, so there is no error message to read and nothing
# MAGIC    in the run state to notice.
# MAGIC 3. **Diagnosis must come from the table's own history**, not from logs — because
# MAGIC    a successful run writes no error.

# COMMAND ----------

import random
from datetime import date, timedelta

CATALOG, SCHEMA = "workspace", "de_prep"
SEED = 20260904
spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## `teach` — a source whose bad row raises immediately

# COMMAND ----------

rng = random.Random(SEED)
base = date(2026, 3, 1)
rows = [(f"REC-{i:05d}", str(rng.randint(1, 500)),
         (base + timedelta(days=rng.randint(0, 27))).isoformat())
        for i in range(1, 501)]
rows.append(("REC-00501", "not-a-number", "2026-03-15"))     # the loud failure

spark.createDataFrame(
    rows, "record_id STRING, qty STRING, recorded_on STRING"
).write.mode("overwrite").saveAsTable("pro_s9_teach_raw")
print("teach rows:", spark.table("pro_s9_teach_raw").count(), "(one will not cast)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## `assess` — a pipeline output that has been silently wrong for days
# MAGIC
# MAGIC The table is rebuilt daily. Every run succeeded. Partway through, an upstream
# MAGIC change meant one source stopped contributing — the job kept reporting success
# MAGIC while the output quietly lost a third of its rows.

# COMMAND ----------

rng = random.Random(SEED + 23)
SOURCES = ["orders_eu", "orders_us", "orders_apac"]
spark.sql("DROP TABLE IF EXISTS pro_s9_assess_daily")

def make_day(day, sources):
    out = []
    for s in sources:
        for i in range(1, 41):
            out.append((f"{s[-2:].upper()}-{day.isoformat()}-{i:03d}", s,
                        round(rng.uniform(10, 400), 2), day))
    return out

schema = "row_id STRING, source_system STRING, amount DOUBLE, run_date DATE"

# Days 1-6: all three sources. Day 7 onwards: orders_apac silently stops arriving.
first = True
for offset in range(0, 12):
    d = base + timedelta(days=offset)
    srcs = SOURCES if offset < 6 else SOURCES[:2]
    mode = "overwrite" if first else "append"
    spark.createDataFrame(make_day(d, srcs), schema).write.mode(mode).saveAsTable("pro_s9_assess_daily")
    first = False

print("assess rows:", spark.table("pro_s9_assess_daily").count())

# COMMAND ----------

# MAGIC %md
# MAGIC ## Prove the failure is genuinely silent

# COMMAND ----------

from pyspark.sql import functions as F

t = spark.table("pro_s9_assess_daily")
per_day = (t.groupBy("run_date")
           .agg(F.count("*").alias("rows"),
                F.countDistinct("source_system").alias("sources"))
           .orderBy("run_date"))
display(per_day)

healthy = per_day.filter("sources = 3").count()
degraded = per_day.filter("sources < 3").count()
first_bad = per_day.filter("sources < 3").agg(F.min("run_date")).collect()[0][0]
missing = [s for s in SOURCES
           if t.filter(F.col("run_date") >= F.lit(first_bad))
                .filter(F.col("source_system") == s).count() == 0]

print(f"healthy days : {healthy}")
print(f"degraded days: {degraded}, first on {first_bad}")
print(f"source that stopped: {missing}")

hist = spark.sql("DESCRIBE HISTORY pro_s9_assess_daily").collect()
print(f"table versions: {len(hist)} - every one a successful write")

assert degraded > 0, "no degradation - nothing to find"
assert len(missing) == 1, f"expected exactly one missing source, got {missing}"
assert all(h["operation"] in ("WRITE", "CREATE OR REPLACE TABLE AS SELECT",
                              "CREATE TABLE AS SELECT") for h in hist), \
    "history should contain only successful writes - the failure must be silent"
print("\nsilent degradation present; no error anywhere in the history")
