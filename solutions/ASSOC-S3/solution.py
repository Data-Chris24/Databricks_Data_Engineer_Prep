# Databricks notebook source
# MAGIC %md
# MAGIC # ASSOC-S3 assignment — reference solution
# MAGIC
# MAGIC Read this after you have a passing suite, or when genuinely stuck. It also emits
# MAGIC the fixtures the tests assert against.

# COMMAND ----------

from pyspark.sql import functions as F

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")
TARGET = "s3_gold_billing_enriched"

events = spark.table("s3_assess_billing_events")
plans = spark.table("s3_assess_plans")
print("events:", events.count(), " plan versions:", plans.count())

# COMMAND ----------

# MAGIC %md
# MAGIC ## The trap: a naive equi-join fans out
# MAGIC
# MAGIC `plan_id` is not unique in the dimension — it is slowly-changing, so each plan
# MAGIC has several versions. Joining on the key alone multiplies every matching event.

# COMMAND ----------

naive = events.join(plans, on="plan_id", how="inner").count()
print(f"naive equi-join: {naive} rows from {events.count()} events  <- fan-out")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Point-in-time join
# MAGIC
# MAGIC Put the validity window in the join condition so exactly one version matches.
# MAGIC Asymmetric bounds (`>=` and `<`) stop a boundary date matching two versions.
# MAGIC
# MAGIC A **left** join, because no billing event may be lost — including the ones whose
# MAGIC plan is missing from the dimension entirely.

# COMMAND ----------

cond = ((events.plan_id == plans.plan_id)
        & (events.event_date >= plans.valid_from)
        & (events.event_date < plans.valid_to))

joined = (events.alias("e").join(plans.alias("p"), cond, "left")
          .select(
              F.col("e.billing_id"), F.col("e.account_id"), F.col("e.plan_id"),
              F.col("e.event_date"), F.col("e.amount_cents"), F.col("e.event_type"),
              F.col("p.plan_name"), F.col("p.tier"), F.col("p.monthly_price_cents"),
          ))
print("after point-in-time left join:", joined.count(), " <- grain preserved")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Money: integer minor units
# MAGIC
# MAGIC `amount_cents` is an integer in cents. Summing it without converting gives an
# MAGIC answer 100x too large, and raises nothing.

# COMMAND ----------

final = (joined
    .withColumn("amount", F.round(F.col("amount_cents") / 100.0, 2))
    .withColumn("plan_missing", F.col("plan_name").isNull())
    .withColumn("signed_amount",
                F.when(F.col("event_type") == "refund", -F.col("amount"))
                 .otherwise(F.col("amount")))
    .select("billing_id", "account_id", "plan_id", "event_date", "event_type",
            "amount", "signed_amount", "plan_name", "tier", "plan_missing"))

final.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(TARGET)
print(f"wrote {spark.table(TARGET).count()} rows")
spark.table(TARGET).printSchema()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Fixtures for the graded suite

# COMMAND ----------

import json
t = spark.table(TARGET)
probes = {
    r["billing_id"]: {
        "plan_id": r["plan_id"], "plan_name": r["plan_name"],
        "amount": r["amount"], "signed_amount": r["signed_amount"],
        "plan_missing": r["plan_missing"],
    }
    for r in t.filter(F.col("billing_id").isin(["BILL-000001", "BILL-000300", "BILL-000600"])).collect()
}
fixtures = {
    "row_count": t.count(),
    "distinct_billing_ids": t.select("billing_id").distinct().count(),
    "orphan_rows": t.filter("plan_missing").count(),
    "matched_rows": t.filter("plan_missing = false").count(),
    "total_amount": float(t.agg(F.round(F.sum("amount"), 2)).collect()[0][0]),
    "total_signed": float(t.agg(F.round(F.sum("signed_amount"), 2)).collect()[0][0]),
    "naive_join_rows": naive,
    "probes": probes,
}
print(json.dumps(fixtures, indent=2, default=str))
