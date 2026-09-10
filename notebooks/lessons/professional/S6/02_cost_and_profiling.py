# Databricks notebook source
# MAGIC %md
# MAGIC # Cost, managed tables and query profiling — `PRO-S6-O1`, `PRO-S6-O4`, `PRO-S6-O5`

# COMMAND ----------

from pyspark.sql import functions as F

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Managed tables reduce operational work — `PRO-S6-O1`
# MAGIC
# MAGIC When Unity Catalog owns the layout it can run maintenance for you: compaction,
# MAGIC clustering, vacuum. On an external table that work is yours to schedule, and the
# MAGIC usual failure is that nobody does it until a query gets slow.

# COMMAND ----------

display(spark.sql("DESCRIBE EXTENDED pro_s6_teach_events").filter(
    "col_name IN ('Type', 'Provider', 'Catalog')"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Reading a query profile — `PRO-S6-O5`
# MAGIC
# MAGIC The numbers worth finding first, in order:
# MAGIC
# MAGIC | Metric | Means |
# MAGIC |---|---|
# MAGIC | **Files pruned vs read** | whether data skipping worked at all |
# MAGIC | **Bytes read** vs bytes returned | whether you are reading columns you discard |
# MAGIC | Spill | working set exceeded memory |
# MAGIC | Shuffle bytes | how much moved between stages |
# MAGIC
# MAGIC A query that reads every file for a filtered column has a **layout** problem. A
# MAGIC query that reads far more bytes than it returns has a **projection** problem —
# MAGIC usually `SELECT *` on a wide table.

# COMMAND ----------

# Column pruning is visible in the plan: only requested columns appear.
narrow = "\n".join(r[0] for r in spark.sql("""
    EXPLAIN SELECT region, amount FROM pro_s6_teach_events WHERE region = 'emea'
""").collect())
wide = "\n".join(r[0] for r in spark.sql("""
    EXPLAIN SELECT * FROM pro_s6_teach_events WHERE region = 'emea'
""").collect())
print("narrow plan mentions event_id:", "event_id" in narrow)
print("wide   plan mentions event_id:", "event_id" in wide)
print("\nOn a wide table that difference is most of the query cost.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Change Data Feed — `PRO-S6-O4`
# MAGIC
# MAGIC CDF records the row-level changes a table underwent, so a downstream consumer can
# MAGIC read *what changed* instead of rescanning. It addresses the case a streaming
# MAGIC table cannot handle: updates and deletes to rows already consumed.

# COMMAND ----------

spark.sql("ALTER TABLE pro_s6_teach_events SET TBLPROPERTIES (delta.enableChangeDataFeed = true)")
spark.sql("UPDATE pro_s6_teach_events SET amount = amount * 1.10 WHERE region = 'emea'")

version = spark.sql("DESCRIBE HISTORY pro_s6_teach_events").select("version").first()["version"]
try:
    changes = spark.read.format("delta") \
        .option("readChangeFeed", "true") \
        .option("startingVersion", version) \
        .table("pro_s6_teach_events")
    display(changes.groupBy("_change_type").count())
except Exception as e:
    print(f"CDF read unavailable here ({type(e).__name__}) - the concept still applies:")
    print("  update_preimage / update_postimage / insert / delete rows are exposed,")
    print("  so a consumer processes the delta rather than the whole table.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Where cost actually goes
# MAGIC
# MAGIC | Symptom | Usual cause | Fix |
# MAGIC |---|---|---|
# MAGIC | Reads every file for a filter | no clustering on the filtered column | cluster |
# MAGIC | Thousands of tiny files | frequent small appends | `OPTIMIZE`, or let predictive optimization run |
# MAGIC | Reads far more bytes than returned | `SELECT *` on a wide table | project only what you need |
# MAGIC | Idle compute | always-on cluster for periodic work | job compute, or serverless |
# MAGIC
# MAGIC Most optimisation questions are really "which of these is happening?", and the
# MAGIC answer comes from `DESCRIBE DETAIL` and the query profile rather than intuition.
# MAGIC
# MAGIC The assignment's table has three of these at once.
