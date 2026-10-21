# Databricks notebook source
# MAGIC %md
# MAGIC # ASSOC-S4 assignment — reference solution
# MAGIC
# MAGIC The lesson's linear chain fails here: one region's file is poisoned, and a chain
# MAGIC that reads everything at once dies with it. The requirement is that good regions
# MAGIC publish anyway and the bad rows are quarantined rather than lost.

# COMMAND ----------

from pyspark.sql import functions as F

CATALOG, SCHEMA = "workspace", "de_prep"
SRC = f"/Volumes/{CATALOG}/{SCHEMA}/raw/s4_assess"
spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")

PUBLISHED = "s4_gold_regional_orders"
QUARANTINE = "s4_quarantine_orders"

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Read everything as text, then separate good from bad
# MAGIC
# MAGIC The trap is reading with a declared INT schema, which fails the whole load
# MAGIC because of one row. Read as text and use `try_cast` to *find* the bad rows
# MAGIC instead of being stopped by them.

# COMMAND ----------

raw = (spark.read.format("csv").option("header", "true")
       .load(f"{SRC}/*.csv")
       .withColumn("source_file", F.col("_metadata.file_path")))

typed = (raw
    .withColumn("units_int", F.expr("try_cast(units AS INT)"))
    .withColumn("ordered_on_date", F.expr("try_cast(ordered_on AS DATE)")))

good = typed.filter("units_int IS NOT NULL AND ordered_on_date IS NOT NULL")
bad = typed.filter("units_int IS NULL OR ordered_on_date IS NULL")

print(f"good rows: {good.count()}   quarantined rows: {bad.count()}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Include the late arrivals
# MAGIC
# MAGIC They live in a separate directory. A run that ignores them publishes an
# MAGIC incomplete result — this is the conditional branch the assignment asks for.

# COMMAND ----------

late_path = f"{SRC}/_late"
try:
    late = (spark.read.format("csv").option("header", "true").load(late_path)
            .withColumn("source_file", F.col("_metadata.file_path"))
            .withColumn("units_int", F.expr("try_cast(units AS INT)"))
            .withColumn("ordered_on_date", F.expr("try_cast(ordered_on AS DATE)")))
    late_count = late.count()
except Exception:
    late, late_count = None, 0

print(f"late arrivals present: {late_count > 0} ({late_count} rows)")
if late is not None and late_count:
    good = good.unionByName(late.filter("units_int IS NOT NULL AND ordered_on_date IS NOT NULL"))
print("good rows including late arrivals:", good.count())

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Publish idempotently
# MAGIC
# MAGIC The grader runs this twice. `overwrite` means the second run produces the same
# MAGIC table; an append would double it.

# COMMAND ----------

published = (good
    .select(
        F.col("order_id"),
        F.col("region"),
        F.col("units_int").alias("units"),
        F.col("ordered_on_date").alias("ordered_on"),
    ))

published.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(PUBLISHED)

quarantined = bad.select(
    F.col("order_id"), F.col("region"), F.col("units").alias("raw_units"),
    F.col("ordered_on").alias("raw_ordered_on"), F.col("source_file"))
quarantined.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(QUARANTINE)

print(f"published : {spark.table(PUBLISHED).count()}")
print(f"quarantined: {spark.table(QUARANTINE).count()}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Fixtures

# COMMAND ----------

import json
p, q = spark.table(PUBLISHED), spark.table(QUARANTINE)
by_region = {r["region"]: r["n"] for r in
             p.groupBy("region").agg(F.count("*").alias("n")).collect()}
fixtures = {
    "published_rows": p.count(),
    "quarantined_rows": q.count(),
    "regions": sorted(by_region),
    "rows_by_region": {k: int(v) for k, v in sorted(by_region.items())},
    "total_units": int(p.agg(F.sum("units")).collect()[0][0]),
    "quarantined_region": q.select("region").distinct().collect()[0]["region"],
}
print(json.dumps(fixtures, indent=2))
