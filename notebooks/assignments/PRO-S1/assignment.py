# Databricks notebook source
# MAGIC %md
# MAGIC # PRO-S1 assignment — your work goes here
# MAGIC
# MAGIC Read `README.md` in this folder for the task and the output contract.
# MAGIC
# MAGIC **The lesson's pipeline reads a snapshot. This source is a change feed: rows are events about rows, out of order, with tombstones.**
# MAGIC
# MAGIC When you are done, go back to the study app and press **Grade my assignment**.
# MAGIC Each failing check says what it expected and why.

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
