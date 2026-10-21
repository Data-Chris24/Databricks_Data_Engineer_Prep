# Databricks notebook source
# MAGIC %md
# MAGIC # ASSOC-S1 — generate the `teach` and `assess` datasets
# MAGIC
# MAGIC Section 1 is about the platform itself — Delta Lake's guarantees and Unity
# MAGIC Catalog's structure — so the datasets differ in **table history**, which is the
# MAGIC thing those guarantees produce.
# MAGIC
# MAGIC ## What makes the assignment un-copyable
# MAGIC
# MAGIC 1. **The teach table has a clean linear history.** Reading its latest version is
# MAGIC    always correct, so the lesson never needs time travel to answer anything.
# MAGIC 2. **The assess table was corrupted by a bad load** partway through its history.
# MAGIC    The latest version is wrong, and the correct answer only exists in an earlier
# MAGIC    one — so a query against the current state cannot produce it.
# MAGIC 3. **The damage is a partial overwrite**, not a deletion, so the row count alone
# MAGIC    does not reveal which version is good.

# COMMAND ----------

import random
from datetime import date, timedelta

CATALOG, SCHEMA = "workspace", "de_prep"
SEED = 20260904
spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## `teach` — a clean, linear history

# COMMAND ----------

rng = random.Random(SEED)
base = date(2026, 3, 1)

def batch(start, n, seed_offset=0):
    r = random.Random(SEED + seed_offset)
    return [(f"SKU-{i:05d}",
             r.choice(["machines", "consumables", "accessories"]),
             round(r.uniform(5, 900), 2),
             base + timedelta(days=r.randint(0, 27)))
            for i in range(start, start + n)]

schema = "sku STRING, category STRING, price DOUBLE, listed_on DATE"
spark.createDataFrame(batch(1, 200), schema).write.mode("overwrite").saveAsTable("s1_teach_catalog")
spark.createDataFrame(batch(201, 100, 1), schema).write.mode("append").saveAsTable("s1_teach_catalog")

print("teach rows:", spark.table("s1_teach_catalog").count())
display(spark.sql("DESCRIBE HISTORY s1_teach_catalog").select("version", "operation"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## `assess` — a history containing a bad load
# MAGIC
# MAGIC Version 0 and 1 build the table correctly. Version 2 is a **partial overwrite**
# MAGIC from a broken upstream job: it replaced the table with only a subset, and with
# MAGIC every price zeroed. Nothing errored, and the table still looks plausible.

# COMMAND ----------

spark.sql("DROP TABLE IF EXISTS s1_assess_catalog")

good = batch(1, 300, 7)
spark.createDataFrame(good, schema).write.mode("overwrite").saveAsTable("s1_assess_catalog")   # v0
spark.createDataFrame(batch(301, 120, 8), schema).write.mode("append").saveAsTable("s1_assess_catalog")  # v1

# v2 - the bad load. Fewer rows, prices destroyed.
broken = [(s, c, 0.0, d) for (s, c, p, d) in batch(1, 180, 7)]
spark.createDataFrame(broken, schema).write.mode("overwrite").option(
    "overwriteSchema", "true").saveAsTable("s1_assess_catalog")   # v2

print("current rows:", spark.table("s1_assess_catalog").count())
display(spark.sql("DESCRIBE HISTORY s1_assess_catalog").select(
    "version", "timestamp", "operation", "operationMetrics"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Prove the corruption is real and recoverable

# COMMAND ----------

from pyspark.sql import functions as F

cur = spark.table("s1_assess_catalog")
v1 = spark.sql("SELECT * FROM s1_assess_catalog VERSION AS OF 1")

cur_rows, v1_rows = cur.count(), v1.count()
cur_zero = cur.filter("price = 0.0").count()
v1_zero = v1.filter("price = 0.0").count()

print(f"current version : {cur_rows} rows, {cur_zero} with price 0.0")
print(f"version 1       : {v1_rows} rows, {v1_zero} with price 0.0")
print(f"revenue current : {cur.agg(F.round(F.sum('price'),2)).collect()[0][0]}")
print(f"revenue v1      : {v1.agg(F.round(F.sum('price'),2)).collect()[0][0]}")

assert cur_zero == cur_rows, "the bad load should have zeroed every price"
assert v1_zero == 0, "version 1 must be clean, or there is nothing to recover"
assert cur_rows != v1_rows, "the row count must differ, or the damage is invisible"
print("\ncorruption present and recoverable from history")
