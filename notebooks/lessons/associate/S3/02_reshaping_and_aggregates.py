# Databricks notebook source
# MAGIC %md
# MAGIC # Reshaping, dedup and aggregates — `ASSOC-S3-O3`, `ASSOC-S3-O4`, `ASSOC-S3-O5`

# COMMAND ----------

from pyspark.sql import functions as F

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")
orders = spark.table("s3_teach_orders")
products = spark.table("s3_teach_products")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Column and row manipulation
# MAGIC
# MAGIC DataFrames are **immutable** — every operation returns a new one. Forgetting to
# MAGIC reassign is the most common "my change did nothing".

# COMMAND ----------

df = (orders
      .withColumn("order_year", F.year("ordered_on"))
      .withColumnRenamed("store", "store_code")
      .drop("discount_pct")
      .filter(F.col("quantity") >= 2))

print("original columns:", orders.columns)
print("derived  columns:", df.columns)
print("original row count unchanged:", orders.count())

# COMMAND ----------

# MAGIC %md
# MAGIC ### Splitting a string column
# MAGIC
# MAGIC `split()` returns an **array**; index it for the parts. Spark SQL arrays are
# MAGIC **0-based** — a slip if you come from a 1-based dialect.
# MAGIC
# MAGIC **A value missing the separator produces a shorter array, and indexing past the
# MAGIC end raises `INVALID_ARRAY_INDEX`** — it does not quietly return null. Under ANSI
# MAGIC semantics (the default on modern Databricks) this fails the whole job, so a
# MAGIC single malformed row takes the batch down.
# MAGIC
# MAGIC Use `get()` when a missing part is expected and should be null instead. The
# MAGIC error message tells you this, which is worth reading rather than reaching
# MAGIC straight for a try/except.

# COMMAND ----------

demo = spark.createDataFrame(
    [("Boston, MA",), ("Denver, CO",), ("Austin",)], "full_location STRING")
# getItem() raises on a short array under ANSI semantics.
try:
    demo.select(F.split("full_location", ", ").getItem(1).alias("state")).collect()
    print("UNEXPECTED: getItem tolerated the short array")
except Exception as e:
    print(f"getItem(1) on 'Austin' raised {type(e).__name__} - the whole batch would fail")

# get() returns NULL instead, which is what you usually want for messy input.
display(demo.select(
    "full_location",
    F.split("full_location", ", ").getItem(0).alias("city"),
    F.get(F.split("full_location", ", "), F.lit(1)).alias("state"),   # NULL for "Austin"
))

# COMMAND ----------

# MAGIC %md
# MAGIC ### `explode` changes grain
# MAGIC
# MAGIC One row per array element, carrying the parent columns. This is the operation
# MAGIC that turns one-row-per-container into one-row-per-item — and no amount of
# MAGIC `COPY INTO` will do it for you.

# COMMAND ----------

nested = spark.createDataFrame(
    [("ORD-1", ["ESP-100", "MUG-021"]), ("ORD-2", ["BNS-900"]), ("ORD-3", [])],
    "order_id STRING, skus ARRAY<STRING>")

print("explode      (empty arrays vanish):", nested.select("order_id", F.explode("skus")).count())
print("explode_outer(empty arrays kept) :", nested.select("order_id", F.explode_outer("skus")).count())

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Deduplication on the business key
# MAGIC
# MAGIC `dropDuplicates()` with no arguments compares **entire rows**. Two versions of a
# MAGIC record that differ anywhere are both kept — so it does nothing about a
# MAGIC redelivered row whose timestamp was corrected.

# COMMAND ----------

dupes = spark.createDataFrame(
    [("EVT-1", 10, "2026-03-01"), ("EVT-1", 10, "2026-03-01"), ("EVT-1", 10, "2026-03-02")],
    "event_id STRING, value INT, ingested STRING")

print("raw                        :", dupes.count())
print("dropDuplicates()           :", dupes.dropDuplicates().count(), " <- the corrected row survives")
print("dropDuplicates(['event_id']):", dupes.dropDuplicates(["event_id"]).count(), " <- one per key")

# COMMAND ----------

# MAGIC %md
# MAGIC When versions genuinely differ, do not let Spark pick. Order by an ingestion
# MAGIC timestamp and keep the newest.

# COMMAND ----------

from pyspark.sql.window import Window
w = Window.partitionBy("event_id").orderBy(F.col("ingested").desc())
display(dupes.withColumn("rn", F.row_number().over(w)).filter("rn = 1").drop("rn"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Aggregates and nulls

# COMMAND ----------

display(spark.sql("""
    SELECT
      count(*)                AS count_star,
      count(discount_pct)     AS count_col,
      round(avg(discount_pct), 4) AS avg_col
    FROM s3_teach_orders
"""))

# COMMAND ----------

# MAGIC %md
# MAGIC `count(*)` counts rows, `count(col)` counts non-nulls, and `avg()` divides by
# MAGIC the non-null count. Three different denominators from one column.
# MAGIC
# MAGIC ### Exact vs approximate distinct
# MAGIC
# MAGIC An exact distinct must shuffle every value to compare it.
# MAGIC `approx_count_distinct()` uses HyperLogLog for a bounded error (~5% default) at a
# MAGIC fraction of the cost. When the business has agreed a tolerance, paying for
# MAGIC exactness is choosing to be slower for nothing.

# COMMAND ----------

display(spark.sql("""
    SELECT
      count(DISTINCT order_id)        AS exact_distinct,
      approx_count_distinct(order_id) AS approx_distinct
    FROM s3_teach_orders
"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Tuning that actually matters — `ASSOC-S3-O5`

# COMMAND ----------

for k in ["spark.sql.shuffle.partitions", "spark.sql.autoBroadcastJoinThreshold"]:
    try:
        print(f"{k:45} = {spark.conf.get(k)}")
    except Exception as e:
        print(f"{k:45} = <not readable here: {type(e).__name__}>")

# COMMAND ----------

# MAGIC %md
# MAGIC | Setting | Symptom it fixes |
# MAGIC |---|---|
# MAGIC | `spark.sql.shuffle.partitions` | hundreds of sub-second tasks = too many; long spilling tasks = too few |
# MAGIC | `spark.sql.autoBroadcastJoinThreshold` | unnecessary shuffles; `-1` disables auto-broadcast |
# MAGIC | `spark.driver.memory` | **not** the fix for `collect()` on a large result |
# MAGIC | `spark.executor.memory` | spill and GC pressure |
# MAGIC
# MAGIC `collect()` pulls every row into the driver's single JVM. Cluster size is
# MAGIC irrelevant. Write the result to a table; `collect()` is for a handful of rows.
# MAGIC
# MAGIC > On serverless, many of these are managed for you and some are not readable or
# MAGIC > settable. Know what they do and when they apply — that is what the exam asks.
# MAGIC
# MAGIC Next: `03_gold_and_quality.py`.
