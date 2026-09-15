# Databricks notebook source
# MAGIC %md
# MAGIC # PRO-S1 assignment — your work goes here
# MAGIC
# MAGIC The task and the output contract are in the next cell (the same text as `README.md` in the repo).
# MAGIC
# MAGIC **The lesson's pipeline reads a snapshot. This source is a change feed: rows are events about rows, out of order, with tombstones.**
# MAGIC
# MAGIC When you are done, go back to the study app and press **Grade my assignment**.
# MAGIC Each failing check says what it expected and why.

# COMMAND ----------

# MAGIC %md
# MAGIC <!-- task:begin  generated from README.md by tools/sync_assignment_tasks.py; edit the README, then re-run it -->
# MAGIC ## Assignment — `PRO-S1` Developing Code for Data Processing
# MAGIC
# MAGIC **Objectives:** `PRO-S1-O3`, `O4`, `O6`, `O7`, `O8`, `O11`
# MAGIC
# MAGIC ### Before you start
# MAGIC
# MAGIC Work the two lessons in `notebooks/lessons/professional/S1/`, and generate the data
# MAGIC (the study app runs the `generate_datasets_pro_s1` job the first time you open this section; `databricks bundle run generate_datasets_pro_s1 -t free` does the same from a terminal).
# MAGIC
# MAGIC > **The lesson's pipeline reads a snapshot.** This source is a *change feed* — rows
# MAGIC > are events *about* rows. Transform-and-write produces a table of events, not of
# MAGIC > customers.
# MAGIC
# MAGIC ### The task
# MAGIC
# MAGIC `workspace.de_prep.pro_s1_assess_changes` is a change feed with `insert`, `update` and
# MAGIC `delete` operations. Reduce it to **current state**, applying by hand what `AUTO CDC`
# MAGIC would do for you.
# MAGIC
# MAGIC Three things make this harder than a dedup:
# MAGIC
# MAGIC 1. **The feed is out of order.** Row order carries no meaning; `seq_num` does.
# MAGIC 2. **Deletes are tombstones.** A key whose latest event is a delete must be **absent**,
# MAGIC    not present with a flag.
# MAGIC 3. **Some keys were deleted and later updated.** Those must be present, because their
# MAGIC    highest sequence is the update — not the delete.
# MAGIC
# MAGIC ### The output contract
# MAGIC
# MAGIC **`workspace.de_prep.pro_s1_current_customers`**
# MAGIC
# MAGIC | Column | Type | Meaning |
# MAGIC |---|---|---|
# MAGIC | `customer_id` | `STRING` | Unique |
# MAGIC | `tier` | `STRING` | From the winning event |
# MAGIC | `balance` | `DOUBLE` | From the winning event |
# MAGIC | `last_seq` | `INT` | The `seq_num` of the winning event |
# MAGIC | `last_event_ts` | `TIMESTAMP` | Its timestamp |
# MAGIC
# MAGIC #### Requirements
# MAGIC
# MAGIC 1. **One row per surviving key.**
# MAGIC 2. **The winning event is the highest `seq_num`**, not the last row encountered.
# MAGIC 3. **Keys whose latest event is a delete are absent.**
# MAGIC 4. **Keys deleted and later updated are present.**
# MAGIC 5. Column order matters — the tests compare the whole schema.
# MAGIC
# MAGIC ### Grading
# MAGIC
# MAGIC ```bash
# MAGIC databricks bundle run grade_pro_s1 -t free --profile FREE
# MAGIC ```
# MAGIC
# MAGIC ### Hints
# MAGIC
# MAGIC <details><summary>I have 300 rows</summary>
# MAGIC
# MAGIC That is one arbitrary event per key — a plain `dropDuplicates(["customer_id"])`. It
# MAGIC keeps tombstoned keys and ignores sequencing entirely. Requirements 2 and 3.
# MAGIC </details>
# MAGIC
# MAGIC <details><summary>How do I pick the winning event?</summary>
# MAGIC
# MAGIC A window partitioned by the key, ordered by `seq_num` descending, taking row 1.
# MAGIC </details>
# MAGIC
# MAGIC <details><summary>Should a deleted-then-updated key survive?</summary>
# MAGIC
# MAGIC Requirement 4. Ask which event has the higher `seq_num`.
# MAGIC </details>
# MAGIC <!-- task:end -->

# COMMAND ----------

from pyspark.sql import Window
from pyspark.sql import functions as F

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")
SOURCE = "pro_s1_assess_changes"
TARGET = "pro_s1_current_customers"
changes = spark.table(SOURCE)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 0 — look at the feed
# MAGIC
# MAGIC What operations exist, what does `seq_num` do, and are rows in any useful order?

# COMMAND ----------

# display(changes.groupBy("op").count())
# display(changes.orderBy("customer_id", "seq_num").limit(20))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1 — the winning event per key
# MAGIC
# MAGIC Requirement 2: the highest `seq_num` wins, not the last row you happen to read.

# COMMAND ----------

# w = Window.partitionBy("customer_id").orderBy(F.desc("seq_num"))
# winners = changes.withColumn("rn", F.row_number().over(w)).filter("rn = 1")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2 — apply the tombstones
# MAGIC
# MAGIC Requirements 3 and 4: a key whose winner is a delete is absent; a key deleted and later updated is present.

# COMMAND ----------

# current = winners.filter(...)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3 — write the contracted table
# MAGIC
# MAGIC Column order matters; the tests compare the whole schema.

# COMMAND ----------

# current.select("customer_id", "tier", "balance", F.col("seq_num").alias("last_seq"), F.col("event_ts").alias("last_event_ts")) \
#     .write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(TARGET)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Check yourself before grading

# COMMAND ----------

# t = spark.table(TARGET); print(t.count(), t.select("customer_id").distinct().count()); t.printSchema()
