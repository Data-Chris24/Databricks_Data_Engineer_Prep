# Databricks notebook source
# MAGIC %md
# MAGIC # PRO-S6 — generate the `teach` and `assess` datasets
# MAGIC
# MAGIC Cost and performance optimization. The pairing differs in **why** a table is
# MAGIC slow, because the right fix depends on the cause and the wrong fix is expensive.
# MAGIC
# MAGIC ## What makes the assignment un-copyable
# MAGIC
# MAGIC 1. **The teach table is slow because it is unclustered.** Clustering on the
# MAGIC    filtered column fixes it, and the lesson does exactly that.
# MAGIC 2. **The assess table is slow for three unrelated reasons**, and clustering fixes
# MAGIC    only one of them:
# MAGIC    - a **small-file problem** — many tiny files from frequent appends
# MAGIC    - a **wide table** where queries read far more bytes than they need
# MAGIC    - a **high-cardinality clustering candidate** that would make things worse
# MAGIC 3. **The assignment is graded on the analysis**, so applying the lesson's single
# MAGIC    `ALTER TABLE ... CLUSTER BY` addresses a third of it.

# COMMAND ----------

import random
from datetime import date, timedelta

CATALOG, SCHEMA = "workspace", "de_prep"
SEED = 20260904
spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## `teach` — one clean cause: no clustering

# COMMAND ----------

rng = random.Random(SEED)
base = date(2026, 1, 1)
rows = [(f"EVT-{i:07d}",
         rng.choice(["emea", "amer", "apac"]),
         base + timedelta(days=rng.randint(0, 364)),
         round(rng.uniform(1, 500), 2))
        for i in range(1, 40001)]

spark.createDataFrame(
    rows, "event_id STRING, region STRING, event_date DATE, amount DOUBLE"
).write.mode("overwrite").saveAsTable("pro_s6_teach_events")
print("teach rows:", spark.table("pro_s6_teach_events").count())

# COMMAND ----------

# MAGIC %md
# MAGIC ## `assess` — three unrelated causes
# MAGIC
# MAGIC Built with many small appends so the file count is genuinely pathological, and
# MAGIC deliberately wide so a `SELECT` of two columns still reads everything.

# COMMAND ----------

rng = random.Random(SEED + 17)
spark.sql("DROP TABLE IF EXISTS pro_s6_assess_orders")

WIDE = [f"attr_{i:02d}" for i in range(1, 21)]
schema = ("order_id STRING, customer_id STRING, region STRING, order_date DATE, "
          "amount DOUBLE, " + ", ".join(f"{c} STRING" for c in WIDE))

# 24 separate appends, each small - this is what produces the small-file problem.
oid = 0
for batch_no in range(24):
    batch = []
    for _ in range(500):
        oid += 1
        batch.append((
            f"ORD-{oid:07d}",
            # High cardinality: nearly unique. Clustering on this would be a mistake.
            f"CUST-{oid:07d}",
            rng.choice(["emea", "amer", "apac", "latam"]),
            base + timedelta(days=rng.randint(0, 364)),
            round(rng.uniform(1, 900), 2),
            *[f"v{rng.randint(1000, 9999)}" * 4 for _ in WIDE],
        ))
    mode = "overwrite" if batch_no == 0 else "append"
    spark.createDataFrame(batch, schema).write.mode(mode).saveAsTable("pro_s6_assess_orders")

print("assess rows:", spark.table("pro_s6_assess_orders").count())

# COMMAND ----------

# MAGIC %md
# MAGIC ## Prove all three causes are real

# COMMAND ----------

from pyspark.sql import functions as F

detail = spark.sql("DESCRIBE DETAIL pro_s6_assess_orders").collect()[0]
n_files = detail["numFiles"]
size = detail["sizeInBytes"]
rows = spark.table("pro_s6_assess_orders").count()

cust_card = spark.table("pro_s6_assess_orders").select("customer_id").distinct().count()
region_card = spark.table("pro_s6_assess_orders").select("region").distinct().count()
n_cols = len(spark.table("pro_s6_assess_orders").columns)

avg_file_mb = (size / n_files) / (1024 * 1024)
print(f"rows              : {rows}")
print(f"files             : {n_files}   avg {avg_file_mb:.2f} MB per file")
print(f"columns           : {n_cols}")
print(f"customer_id distinct: {cust_card} of {rows}  (cardinality {cust_card/rows:.0%})")
print(f"region distinct     : {region_card}")

assert n_files >= 10, f"only {n_files} files - no small-file problem to find"
assert avg_file_mb < 32, "files are already large enough; the trap is missing"
assert n_cols >= 20, "table is not wide enough for column pruning to matter"
assert cust_card / rows > 0.9, "customer_id is not high-cardinality enough to be a trap"
assert region_card <= 6, "region should be a sensible clustering candidate"
print("\nall three causes present")
