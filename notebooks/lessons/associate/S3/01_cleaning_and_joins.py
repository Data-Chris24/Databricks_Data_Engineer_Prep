# Databricks notebook source
# MAGIC %md
# MAGIC # Cleaning and joins — `ASSOC-S3-O1`, `ASSOC-S3-O2`
# MAGIC
# MAGIC Teach dataset: `s3_teach_orders` with clean `s3_teach_products` and
# MAGIC `s3_teach_stores` dimensions — one row per key, every foreign key resolves.
# MAGIC Run `notebooks/datasets/generate_ASSOC-S3.py` first.
# MAGIC
# MAGIC The dimensions are clean on purpose: this lesson teaches the join. The
# MAGIC assignment gives you a dimension that is not.

# COMMAND ----------

from pyspark.sql import functions as F

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")

orders = spark.table("s3_teach_orders")
products = spark.table("s3_teach_products")
stores = spark.table("s3_teach_stores")
print(f"{orders.count()} orders, {products.count()} products, {stores.count()} stores")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Cleaning: nulls carry meaning
# MAGIC
# MAGIC `discount_pct` is null on ~15% of rows. The business says that means *no
# MAGIC discount* — a known value, not an unknown — so filling it with 0.0 records the
# MAGIC meaning rather than losing it.
# MAGIC
# MAGIC Had it meant *unknown*, filling it would invent data. Same operation, opposite
# MAGIC verdict, decided by meaning.

# COMMAND ----------

display(orders.select(
    F.count("*").alias("rows"),
    F.sum(F.col("discount_pct").isNull().cast("int")).alias("null_discount"),
    F.round(F.avg("discount_pct"), 4).alias("avg_ignoring_nulls"),
    F.round(F.avg(F.coalesce("discount_pct", F.lit(0.0))), 4).alias("avg_treating_null_as_zero"),
))

# COMMAND ----------

# MAGIC %md
# MAGIC Note the two averages differ. `avg()` skips nulls, so it divides by the non-null
# MAGIC count — if a null really meant zero, the average comes out too high. That is a
# MAGIC silent wrong answer, not an error.

# COMMAND ----------

clean = (orders
    .withColumn("discount_pct", F.coalesce("discount_pct", F.lit(0.0)))
    .withColumn("net_amount",
                F.round(F.col("quantity") * F.col("unit_price") * (1 - F.col("discount_pct")), 2)))

display(clean.limit(5))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Joining to clean dimensions
# MAGIC
# MAGIC Both dimensions have one row per key, so the row count is preserved. **Always
# MAGIC check that.** It is the cheapest possible guard against fan-out.

# COMMAND ----------

enriched = (clean
    .join(products, on="product_sku", how="left")
    .join(stores, on="store", how="left"))

print("orders in :", clean.count())
print("orders out:", enriched.count(), "  <- must match, or the join changed the grain")
display(enriched.select("order_id", "store", "region", "product_sku", "category", "net_amount").limit(5))

# COMMAND ----------

# MAGIC %md
# MAGIC ### Why `left` and not `inner`
# MAGIC
# MAGIC An inner join silently drops any order whose product is missing from the
# MAGIC dimension. With clean data the result is identical — but the *risk profile* is
# MAGIC not. A left join fails loudly later (nulls you can count) rather than quietly now
# MAGIC (rows that vanished).

# COMMAND ----------

inner_count = clean.join(products, on="product_sku", how="inner").count()
print(f"inner: {inner_count}   left: {clean.join(products, on='product_sku', how='left').count()}")
print("identical here because referential integrity holds - do not rely on that")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Broadcast joins
# MAGIC
# MAGIC A normal join shuffles both sides so matching keys meet on the same executor.
# MAGIC When one side is tiny, broadcasting it to every executor avoids moving the large
# MAGIC side at all. Spark does this automatically below
# MAGIC `spark.sql.autoBroadcastJoinThreshold` (10 MB); these dimensions are far under it.
# MAGIC
# MAGIC > Read the plan with SQL `EXPLAIN`. Many examples online reach into
# MAGIC > `df._jdf.queryExecution()`, which **serverless blocks** — private JVM access is
# MAGIC > not permitted there. `EXPLAIN` works on both serverless and classic.

# COMMAND ----------

# Read the plan through SQL EXPLAIN. Serverless blocks the private _jdf attribute
# that older examples use to reach the JVM query execution, so this is the portable
# way - and it works identically on classic compute.
plan = "\n".join(r[0] for r in spark.sql("""
    EXPLAIN
    SELECT o.order_id, p.category
    FROM s3_teach_orders o
    LEFT JOIN s3_teach_products p ON o.product_sku = p.product_sku
""").collect())

print("broadcast join chosen:", "BroadcastHashJoin" in plan or "BroadcastNestedLoop" in plan)

# Serverless manages this and refuses to report it (CONFIG_NOT_AVAILABLE). Know the
# default - 10 MB - and what it does; you will be asked to reason about it, not read it.
try:
    print("threshold:", spark.conf.get("spark.sql.autoBroadcastJoinThreshold"))
except Exception as e:
    print(f"threshold not readable on serverless ({type(e).__name__}); default is 10 MB")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. `UNION` vs `UNION ALL`
# MAGIC
# MAGIC `UNION` deduplicates, which means a shuffle. `UNION ALL` concatenates. Prefer
# MAGIC `UNION ALL` and deduplicate deliberately when you actually need to.

# COMMAND ----------

a = orders.limit(10)
print("union all:", a.unionAll(a).count(), " (20 - keeps both copies)")
print("union    :", a.union(a).distinct().count(), " (10 - deduplicated)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## What to carry forward
# MAGIC
# MAGIC - A null is either *unknown* or *a value*. Decide which before filling it.
# MAGIC - Check the row count across a join meant to enrich. It should not change.
# MAGIC - `left` when nothing may be lost; `inner` only when dropping is intended.
# MAGIC - Broadcasting avoids shuffling the big side; it is automatic under the threshold.
# MAGIC
# MAGIC Next: `02_reshaping_and_aggregates.py`.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Next
# MAGIC
# MAGIC Continue with the next lesson notebook: [02_reshaping_and_aggregates](./02_reshaping_and_aggregates).
# MAGIC
# MAGIC When the lessons are done, open the graded assignment: [ASSOC-S3 assignment notebook](../../../assignments/ASSOC-S3/assignment) · [the task](../../../assignments/ASSOC-S3/README.md).
