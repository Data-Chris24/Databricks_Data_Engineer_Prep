# Databricks notebook source
# MAGIC %md
# MAGIC # Gold objects and quality — `ASSOC-S3-O6`, `ASSOC-S3-O7`

# COMMAND ----------

from pyspark.sql import functions as F

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")

# Rebuild the silver table this lesson depends on, so it runs standalone.
spark.sql("""
    CREATE OR REPLACE TABLE s3_silver_orders AS
    SELECT o.order_id, o.store, s.region, o.product_sku, p.category,
           o.quantity, o.unit_price,
           COALESCE(o.discount_pct, 0.0) AS discount_pct,
           ROUND(o.quantity * o.unit_price * (1 - COALESCE(o.discount_pct, 0.0)), 2) AS net_amount,
           o.ordered_on
    FROM s3_teach_orders o
    LEFT JOIN s3_teach_products p ON o.product_sku = p.product_sku
    LEFT JOIN s3_teach_stores   s ON o.store = s.store
""")
print("silver rows:", spark.table("s3_silver_orders").count())

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. A view — computed every time it is queried
# MAGIC
# MAGIC No stored data, always current. Also the simplest governance boundary: expose
# MAGIC the permitted columns, grant on the view, withhold on the table.

# COMMAND ----------

spark.sql("""
    CREATE OR REPLACE VIEW s3_gold_sales_by_region_v AS
    SELECT region, category,
           count(*)                  AS orders,
           round(sum(net_amount), 2) AS net_revenue
    FROM s3_silver_orders
    GROUP BY region, category
""")
display(spark.sql("SELECT * FROM s3_gold_sales_by_region_v ORDER BY net_revenue DESC LIMIT 8"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. A materialized view — computed on refresh
# MAGIC
# MAGIC Stores the result. Right when reads far outnumber writes: recomputing a nightly
# MAGIC aggregate on every one of hundreds of dashboard queries wastes the same work
# MAGIC hundreds of times.

# COMMAND ----------

try:
    spark.sql("""
        CREATE OR REPLACE MATERIALIZED VIEW s3_gold_sales_by_region_mv AS
        SELECT region, category,
               count(*)                  AS orders,
               round(sum(net_amount), 2) AS net_revenue
        FROM s3_silver_orders
        GROUP BY region, category
    """)
    print("materialized view created")
    display(spark.sql("SELECT * FROM s3_gold_sales_by_region_mv ORDER BY net_revenue DESC LIMIT 5"))
except Exception as e:
    print(f"Materialized view not available here ({type(e).__name__}).")
    print("Free Edition allows one active pipeline per type, and an MV is backed by one.")
    print("The distinction still matters for the exam:")
    print("  view      -> recomputed per query, always current, no storage")
    print("  MV        -> stored result, refreshed on a schedule, cheap to read")
    print("  streaming -> incremental, each source row processed once")

# COMMAND ----------

# MAGIC %md
# MAGIC | Object | Computed | Choose when |
# MAGIC |---|---|---|
# MAGIC | View | every query | source changes about as often as it is read |
# MAGIC | Materialized view | on refresh | read far more often than written |
# MAGIC | Streaming table | incrementally, once per row | append-oriented, continuously arriving |
# MAGIC
# MAGIC Match the object to the read/write ratio — that single question answers most
# MAGIC exam items on this objective.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Quality checks that run
# MAGIC
# MAGIC ### A CHECK constraint is enforced on write
# MAGIC
# MAGIC A violating row fails the transaction rather than landing and being cleaned up
# MAGIC later. That is the difference between a table that *cannot* hold bad data and one
# MAGIC that usually does not.

# COMMAND ----------

spark.sql("ALTER TABLE s3_silver_orders ADD CONSTRAINT positive_qty CHECK (quantity >= 1)")
print("constraint added - it validated every existing row to get here")

try:
    spark.sql("INSERT INTO s3_silver_orders VALUES ('BAD-1','boston','Northeast','ESP-100','machines',0,10.0,0.0,0.0,DATE'2026-03-01')")
    print("UNEXPECTED: the bad row was accepted")
except Exception as e:
    print(f"rejected as designed: {type(e).__name__}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### The row-count invariant
# MAGIC
# MAGIC When a join is meant to enrich without changing grain, the row count is the
# MAGIC invariant. One cheap assertion catches both fan-out (too many) and unintended
# MAGIC inner-join drops (too few).

# COMMAND ----------

src = spark.table("s3_teach_orders").count()
out = spark.table("s3_silver_orders").count()
assert src == out, f"grain changed: {src} in, {out} out"
print(f"grain preserved: {src} in, {out} out")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Null rate is the signal for *silent* degradation

# COMMAND ----------

display(spark.sql("""
    SELECT
      round(100.0 * sum(CASE WHEN region   IS NULL THEN 1 ELSE 0 END) / count(*), 2) AS pct_null_region,
      round(100.0 * sum(CASE WHEN category IS NULL THEN 1 ELSE 0 END) / count(*), 2) AS pct_null_category
    FROM s3_silver_orders
"""))

# COMMAND ----------

# MAGIC %md
# MAGIC Both are 0% because referential integrity holds. A jump here would mean a cast
# MAGIC started failing or a key stopped matching — the job still succeeds, the row count
# MAGIC still looks right, and the data is quietly wrong. Track it as a metric rather than
# MAGIC checking it only when something breaks.
# MAGIC
# MAGIC ## Now do the assignment
# MAGIC
# MAGIC `notebooks/assignments/ASSOC-S3/` uses a different source: billing events against
# MAGIC a **slowly-changing** plan dimension. The joins in this lesson will not survive
# MAGIC contact with it, and that is the point.
