# Databricks notebook source
# MAGIC %md
# MAGIC # Pipelines, streaming and CDC — `PRO-S1-O4`, `O6`, `O7`, `O8`
# MAGIC
# MAGIC The teach source is a **snapshot**: each row is a fact and the latest load is the
# MAGIC truth, so a transform-and-write pipeline is correct. That is the shape the
# MAGIC assignment breaks.

# COMMAND ----------

from pyspark.sql import functions as F

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Streaming tables vs materialized views — `PRO-S1-O6`
# MAGIC
# MAGIC | | Streaming table | Materialized view |
# MAGIC |---|---|---|
# MAGIC | Processes | each input row **once**, incrementally | the whole query, on refresh |
# MAGIC | Suits | append-only, ever-growing sources | aggregates over data that changes |
# MAGIC | Handles updates to old rows | no — a row already consumed is not revisited | yes, recomputed |
# MAGIC | Cost profile | proportional to new data | proportional to the query |
# MAGIC
# MAGIC The decision rule: **does old data change?** If yes, a streaming table will not
# MAGIC see it, and you want a materialized view. If the source only ever appends, a
# MAGIC streaming table is far cheaper.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Structured Streaming vs Declarative Pipelines — `PRO-S1-O8`
# MAGIC
# MAGIC | | Structured Streaming | Lakeflow Declarative Pipelines |
# MAGIC |---|---|---|
# MAGIC | You write | the how: readStream, checkpoints, triggers | the what: table definitions and dependencies |
# MAGIC | Orchestration | yours | derived from the dependency graph |
# MAGIC | Quality rules | hand-rolled | declarative expectations |
# MAGIC | Best when | you need precise control over state and triggers | you want the platform to manage the DAG |
# MAGIC
# MAGIC Declarative pipelines are not "streaming made easy" — they are a different level
# MAGIC of abstraction. Reach for Structured Streaming when you need to control the
# MAGIC mechanics; reach for a pipeline when the mechanics are incidental.
# MAGIC
# MAGIC > Free Edition allows **one active pipeline per type**, so this notebook explains
# MAGIC > the model and implements CDC with a MERGE rather than deploying a pipeline.
# MAGIC > The semantics below are what `AUTO CDC` applies for you.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. The snapshot pipeline — correct here, wrong later
# MAGIC
# MAGIC Read, transform, write. Nothing about the source requires more.

# COMMAND ----------

accounts = spark.table("pro_s1_teach_accounts")

silver = (accounts
    .withColumn("band", F.when(F.col("balance") >= 3000, "high")
                         .when(F.col("balance") >= 1000, "medium")
                         .otherwise("low"))
    .withColumn("is_active", F.col("balance") > 0))

silver.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable("pro_s1_teach_silver")
print("silver rows:", spark.table("pro_s1_teach_silver").count())
display(spark.table("pro_s1_teach_silver").limit(5))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. What `AUTO CDC` does — `PRO-S1-O7`
# MAGIC
# MAGIC When the source is a **change feed** rather than a snapshot, rows are *events
# MAGIC about* rows. `AUTO CDC` (formerly `APPLY CHANGES`) reduces them to current state,
# MAGIC and the three things it handles are the three things people get wrong by hand:
# MAGIC
# MAGIC 1. **Sequencing** — `SEQUENCE BY` decides which event wins, not arrival order.
# MAGIC 2. **Deletes** — `APPLY AS DELETE WHEN` removes the key rather than storing a row
# MAGIC    that says "deleted".
# MAGIC 3. **Out-of-order arrival** — a late event with a lower sequence is ignored.
# MAGIC
# MAGIC ```sql
# MAGIC CREATE OR REFRESH STREAMING TABLE customers;
# MAGIC
# MAGIC APPLY CHANGES INTO live.customers
# MAGIC FROM STREAM(live.customer_changes)
# MAGIC KEYS (customer_id)
# MAGIC APPLY AS DELETE WHEN op = 'delete'
# MAGIC SEQUENCE BY seq_num
# MAGIC COLUMNS * EXCEPT (op, seq_num);
# MAGIC ```
# MAGIC
# MAGIC The equivalent by hand is a window on the key ordered by the sequence, taking the
# MAGIC latest event and dropping keys whose latest event is a delete. Doing it by hand is
# MAGIC exactly the assignment.

# COMMAND ----------

# MAGIC %md
# MAGIC ## What to carry forward
# MAGIC
# MAGIC - Streaming table = each row once; materialized view = recomputed. Choose by
# MAGIC   whether old data changes.
# MAGIC - Declarative pipelines are a different abstraction level, not easier streaming.
# MAGIC - A change feed is not a snapshot. Reducing one to current state needs
# MAGIC   sequencing and tombstone handling, and this lesson's pipeline does neither.
# MAGIC
# MAGIC The assignment's source is a change feed with out-of-order events, deletes, and
# MAGIC keys that are deleted then resurrected. Section 3 above will not survive it.
