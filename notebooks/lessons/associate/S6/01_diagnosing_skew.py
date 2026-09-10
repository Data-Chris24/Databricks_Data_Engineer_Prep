# Databricks notebook source
# MAGIC %md
# MAGIC # Diagnosing skew and reading a plan — `ASSOC-S6-O3`
# MAGIC
# MAGIC Teach data: `s6_teach_events`, where one customer id dominates.

# COMMAND ----------

from pyspark.sql import functions as F

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")
events = spark.table("s6_teach_events")
print("rows:", events.count())

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Skew is a distribution problem, and a `GROUP BY` shows it
# MAGIC
# MAGIC Before opening the Spark UI, ask the data. If one key holds most of the rows,
# MAGIC any shuffle on that key sends most of the work to one task.

# COMMAND ----------

dist = (events.groupBy("customer_id").count()
        .orderBy(F.desc("count")))
display(dist.limit(5))

top = dist.first()
share = top["count"] / events.count()
print(f"largest key: {top['customer_id']} holds {share:.0%} of all rows")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. What that looks like in the Spark UI
# MAGIC
# MAGIC | What you see | Means |
# MAGIC |---|---|
# MAGIC | One task far slower than the rest | skew |
# MAGIC | Max shuffle read >> median shuffle read | skew, quantified |
# MAGIC | "spill (disk)" on a stage | working set exceeded memory |
# MAGIC | Hundreds of sub-second tasks | over-partitioned |
# MAGIC
# MAGIC The tell for skew is the **ratio**, not the absolute time. A stage whose max
# MAGIC shuffle read is 12x its median has one task doing 12x the work, and the stage
# MAGIC cannot finish until that task does.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Adaptive Query Execution handles it
# MAGIC
# MAGIC AQE can split an oversized partition at runtime, which fixes the cause with no
# MAGIC code change. Reach for that before hand-salting keys.

# COMMAND ----------

for k in ["spark.sql.adaptive.enabled", "spark.sql.adaptive.skewJoin.enabled"]:
    try:
        print(f"{k:45} = {spark.conf.get(k)}")
    except Exception as e:
        print(f"{k:45} = <not readable on serverless: {type(e).__name__}>")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Reading the query plan
# MAGIC
# MAGIC `EXPLAIN` shows the strategy Spark chose. Use SQL `EXPLAIN` rather than reaching
# MAGIC into `df._jdf` — serverless blocks private JVM access, and `EXPLAIN` works
# MAGIC everywhere.

# COMMAND ----------

plan = "\n".join(r[0] for r in spark.sql("""
    EXPLAIN
    SELECT customer_id, count(*) AS n, sum(amount) AS total
    FROM s6_teach_events GROUP BY customer_id
""").collect())

for marker in ["AdaptiveSparkPlan", "HashAggregate", "Exchange", "BroadcastHashJoin"]:
    print(f"{marker:22} present: {marker in plan}")

# COMMAND ----------

# MAGIC %md
# MAGIC `Exchange` is a shuffle. `AdaptiveSparkPlan` means AQE is free to re-plan once it
# MAGIC has seen real statistics — which is what lets it notice the skew.

# COMMAND ----------

# MAGIC %md
# MAGIC ## What to carry forward
# MAGIC
# MAGIC - Ask the data first: a `GROUP BY` on the join key finds skew in one query.
# MAGIC - In the UI, the tell is max-vs-median, not absolute duration.
# MAGIC - AQE fixes skew at runtime; salting is the fallback, not the first move.
# MAGIC - Read plans with SQL `EXPLAIN`.
