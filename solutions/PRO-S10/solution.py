# Databricks notebook source
# MAGIC %md
# MAGIC # PRO-S10 assignment — reference solution
# MAGIC
# MAGIC The dimension changes over time, so a fact must join to the version that was
# MAGIC current when the fact happened. That means surrogate keys and an as-of join.

# COMMAND ----------

from pyspark.sql import functions as F

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")
DIM = "pro_s10_dim_customer"
FACT = "pro_s10_fact_orders"

orders = spark.table("pro_s10_assess_orders")
versions = spark.table("pro_s10_assess_customer_versions")
print(f"{orders.count()} orders, {versions.count()} customer versions")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Why the natural key is not enough here

# COMMAND ----------

multi = versions.groupBy("customer_id").count().filter("count > 1").count()
print(f"customers with more than one version: {multi}")
print("so customer_id alone does not identify a row in this dimension")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Build the dimension with surrogate keys
# MAGIC
# MAGIC A surrogate key identifies **one version** of a customer. It is deterministic
# MAGIC here — derived from the natural key plus the validity start — so rebuilding the
# MAGIC dimension does not renumber it, which a monotonically increasing id would.

# COMMAND ----------

dim = (versions
    .withColumn("customer_sk",
                F.sha2(F.concat_ws("|", F.col("customer_id"), F.col("valid_from")), 256))
    .select("customer_sk", "customer_id", "segment", "region",
            "valid_from", "valid_to", "is_current"))

dim.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(DIM)
print("dimension rows:", spark.table(DIM).count())
print("distinct surrogate keys:", spark.table(DIM).select("customer_sk").distinct().count())

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Join the fact as of its own date
# MAGIC
# MAGIC The validity window goes in the join condition, so exactly one version matches
# MAGIC and the fact's grain is preserved. Asymmetric bounds stop a boundary date
# MAGIC matching two versions.

# COMMAND ----------

d = spark.table(DIM)
cond = ((orders.customer_id == d.customer_id) &
        (orders.ordered_on >= d.valid_from) &
        (orders.ordered_on < d.valid_to))

fact = (orders.alias("o").join(d.alias("d"), cond, "left")
    .select(
        F.col("o.order_id"),
        F.col("d.customer_sk"),
        F.col("o.customer_id"),
        F.col("d.segment").alias("segment_at_order"),
        F.col("d.region").alias("region_at_order"),
        F.col("o.amount"),
        F.col("o.ordered_on"),
    ))

print("fact rows in :", orders.count())
print("fact rows out:", fact.count(), " <- must match")

fact.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(FACT)
spark.sql(f"ALTER TABLE {FACT} CLUSTER BY (ordered_on, segment_at_order)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. What the naive model would have said
# MAGIC
# MAGIC Joining to the current version re-attributes historical revenue to whichever
# MAGIC segment a customer is in **now**. Both answers look reasonable; only one is true.

# COMMAND ----------

naive = (orders.join(d.filter("is_current"), on="customer_id", how="left")
         .groupBy("segment").agg(F.round(F.sum("amount"), 2).alias("naive_revenue")))
correct = (spark.table(FACT).groupBy("segment_at_order")
           .agg(F.round(F.sum("amount"), 2).alias("correct_revenue"))
           .withColumnRenamed("segment_at_order", "segment"))

display(naive.join(correct, on="segment", how="full_outer")
        .withColumn("difference", F.round(F.col("naive_revenue") - F.col("correct_revenue"), 2))
        .orderBy("segment"))

# COMMAND ----------

import json
f = spark.table(FACT)
misattributed = f.join(d.filter("is_current").select(
    F.col("customer_id"), F.col("segment").alias("current_segment")), on="customer_id") \
    .filter(F.col("segment_at_order") != F.col("current_segment")).count()

print(json.dumps({
    "dim_rows": spark.table(DIM).count(),
    "distinct_sks": spark.table(DIM).select("customer_sk").distinct().count(),
    "fact_rows": f.count(),
    "source_orders": orders.count(),
    "orders_misattributed_by_naive_join": misattributed,
    "customers_with_multiple_versions": multi,
}, indent=2))
