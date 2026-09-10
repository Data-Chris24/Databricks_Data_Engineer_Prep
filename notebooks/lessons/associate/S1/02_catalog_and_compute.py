# Databricks notebook source
# MAGIC %md
# MAGIC # Unity Catalog and compute — `ASSOC-S1-O1`, `ASSOC-S1-O2`

# COMMAND ----------

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. The three-level namespace
# MAGIC
# MAGIC `catalog.schema.object` — one model for tables, views, volumes, functions and
# MAGIC models, governed the same way.

# COMMAND ----------

display(spark.sql("SHOW CATALOGS"))

# COMMAND ----------

display(spark.sql("SHOW SCHEMAS IN workspace"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Managed tables and what they buy
# MAGIC
# MAGIC When Unity Catalog owns the storage layout, it can maintain the table for you —
# MAGIC compaction, clustering, vacuum. That is the operational work you would otherwise
# MAGIC carry yourself.

# COMMAND ----------

display(spark.sql("DESCRIBE EXTENDED s1_teach_catalog").filter(
    "col_name IN ('Type', 'Catalog', 'Database', 'Provider')"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Lineage and audit come from the catalog, not the table
# MAGIC
# MAGIC System tables record who read what and how objects relate. Availability varies by
# MAGIC tier, so this checks rather than assumes.

# COMMAND ----------

for t in ["system.information_schema.tables", "system.access.audit"]:
    try:
        n = spark.sql(f"SELECT count(*) AS n FROM {t} LIMIT 1").collect()[0]["n"]
        print(f"{t:42} readable ({n} rows visible)")
    except Exception as e:
        print(f"{t:42} not available here ({type(e).__name__})")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Compute — `ASSOC-S1-O2`
# MAGIC
# MAGIC | Type | Lives | Suits | Billed |
# MAGIC |---|---|---|---|
# MAGIC | Job compute | per run, terminates after | scheduled ETL | lower DBU rate |
# MAGIC | All-purpose | until stopped | interactive development | higher DBU rate |
# MAGIC | SQL warehouse | until idle timeout | BI and ad-hoc SQL | its own rate |
# MAGIC | Serverless | managed by Databricks | fast start, no configuration | per use |
# MAGIC
# MAGIC **The cost question is nearly always about idle time.** A 12-minute nightly job
# MAGIC on job compute costs 12 minutes; the same job on an all-purpose cluster left
# MAGIC running costs 24 hours at a higher rate.
# MAGIC
# MAGIC For many concurrent analysts, high concurrency with autoscaling beats a
# MAGIC fixed-size cluster — which is either wasteful when idle or a bottleneck at peak.

# COMMAND ----------

print("This notebook is running on serverless compute.")
print()
print("Free Edition is serverless-only, so compute *selection* cannot be practised")
print("here - there is nothing to choose between. Learn the trade-offs; the exam asks")
print("you to reason about them rather than configure them.")
print()
print("See docs/optional-classic-track.md for the paid-tier lab that does.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## What to carry forward
# MAGIC
# MAGIC - `catalog.schema.object`, one governance model across object types.
# MAGIC - Managed tables let Unity Catalog maintain the layout for you.
# MAGIC - Compute questions are usually cost questions, and cost is usually idle time.
# MAGIC
# MAGIC Now do the assignment. Its table was corrupted by a bad load, and the correct
# MAGIC answer exists only in an earlier version — a query against the current state
# MAGIC cannot produce it.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Next
# MAGIC
# MAGIC When the lessons are done, open the graded assignment: [ASSOC-S1 assignment notebook](../../../assignments/ASSOC-S1/assignment) · [the task](../../../assignments/ASSOC-S1/README.md).
