# Databricks notebook source
# MAGIC %md
# MAGIC # ASSOC-S6 assignment — reference solution
# MAGIC
# MAGIC Three pathologies, only one of which the lesson's `GROUP BY` finds.

# COMMAND ----------

from pyspark.sql import functions as F

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")
SRC = "s6_assess_orders"
REPORT = "s6_health_report"

t = spark.table(SRC)
total = t.count()
print("rows:", total)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Finding 1 — duplicate business keys
# MAGIC
# MAGIC The row count alone says nothing; comparing it to the **distinct key count** is
# MAGIC what exposes this. Redelivered rows inflate every sum while leaving the number of
# MAGIC distinct orders untouched.

# COMMAND ----------

distinct_ids = t.select("order_id").distinct().count()
duplicate_rows = total - distinct_ids
print(f"distinct order_id: {distinct_ids}   duplicate rows: {duplicate_rows}")

# What the duplication costs in money terms.
true_revenue = (t.dropDuplicates(["order_id"])
                .agg(F.round(F.sum("amount"), 2)).collect()[0][0])
observed_revenue = t.agg(F.round(F.sum("amount"), 2)).collect()[0][0]
print(f"revenue as stored: {observed_revenue}   deduplicated: {true_revenue}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Finding 2 — a null-rate regression after a cutover date
# MAGIC
# MAGIC Invisible to a row count: nothing is missing, a column simply stopped arriving.
# MAGIC Comparing the null rate *over time* is what surfaces it.

# COMMAND ----------

by_day = (t.groupBy("ordered_on")
    .agg(F.count("*").alias("rows"),
         F.sum(F.col("channel").isNull().cast("int")).alias("null_channel"))
    .withColumn("pct_null", F.round(100.0 * F.col("null_channel") / F.col("rows"), 1))
    .orderBy("ordered_on"))
display(by_day)

# The first day on which the null rate jumps is the regression date.
regression = (by_day.filter("pct_null > 20").agg(F.min("ordered_on")).collect()[0][0])
print("null-rate regression begins:", regression)

null_before = t.filter(F.col("ordered_on") < F.lit(regression)).filter("channel IS NULL").count()
null_after = t.filter(F.col("ordered_on") >= F.lit(regression)).filter("channel IS NULL").count()
print(f"channel nulls before: {null_before}   after: {null_after}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Finding 3 — skew
# MAGIC
# MAGIC The one the lesson's query does find, on a different column than the lesson used.

# COMMAND ----------

dist = t.groupBy("region").count().orderBy(F.desc("count"))
display(dist)
top = dist.first()
skew_pct = round(100.0 * top["count"] / total, 1)
print(f"largest region: {top['region']} at {skew_pct}%")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Publish the report
# MAGIC
# MAGIC One row per finding, so the diagnosis is data rather than prose.

# COMMAND ----------

findings = spark.createDataFrame([
    ("duplicate_keys", "order_id", float(duplicate_rows),
     f"{duplicate_rows} redelivered rows inflate every sum; distinct order_id is {distinct_ids}"),
    ("null_regression", "channel", float(null_after),
     f"channel null rate jumps from {null_before} to {null_after} on {regression}"),
    ("skew", "region", float(skew_pct),
     f"{top['region']} holds {skew_pct}% of rows, so any shuffle on region is unbalanced"),
], "finding STRING, column_name STRING, metric DOUBLE, detail STRING")

findings.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(REPORT)
display(spark.table(REPORT).orderBy("finding"))

# COMMAND ----------

import json
print(json.dumps({
    "total_rows": total,
    "distinct_order_ids": distinct_ids,
    "duplicate_rows": duplicate_rows,
    "observed_revenue": float(observed_revenue),
    "deduplicated_revenue": float(true_revenue),
    "regression_date": str(regression),
    "null_channel_before": null_before,
    "null_channel_after": null_after,
    "skew_region": top["region"],
    "skew_pct": skew_pct,
    "findings": 3,
}, indent=2))
