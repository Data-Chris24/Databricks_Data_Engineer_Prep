# Databricks notebook source
# MAGIC %md
# MAGIC # ASSOC-S3 — generate the `teach` and `assess` datasets
# MAGIC
# MAGIC Section 3 is about transformation, so unlike Section 2 these are **tables**,
# MAGIC not files. Ingestion has already happened.
# MAGIC
# MAGIC | | Used by | Shape |
# MAGIC |---|---|---|
# MAGIC | `s3_teach_*` | the worked lessons | retail orders + **clean** dimensions |
# MAGIC | `s3_assess_*` | the graded assignment | billing events + a **slowly-changing** dimension |
# MAGIC
# MAGIC ## What makes the assignment un-copyable
# MAGIC
# MAGIC Section 3 is largely about joins, so the pairing has to make **the join itself
# MAGIC behave differently**. Four differences, each defeating a specific transplant:
# MAGIC
# MAGIC 1. **The teach dimensions have one row per key. The assess dimension does not.**
# MAGIC    `plans` is slowly-changing: the same `plan_id` appears several times with
# MAGIC    different validity windows. A copied equi-join fans out and produces *more*
# MAGIC    rows than it started with — the classic silent duplication bug.
# MAGIC 2. **Referential integrity holds in teach and does not in assess.** Some billing
# MAGIC    events reference a plan that is not in the dimension. An inner join drops them
# MAGIC    without a word; the assignment requires them kept and flagged.
# MAGIC 3. **The correct join is point-in-time**, on `event_date` falling inside the
# MAGIC    plan's validity window — not key equality alone.
# MAGIC 4. **Money arrives as integer minor units** (cents), where the teach data used
# MAGIC    decimals. Summing without converting gives an answer 100x too large, and no
# MAGIC    error.
# MAGIC
# MAGIC Seeded, so every learner gets identical data and the graded answers match.

# COMMAND ----------

import random
from datetime import date, timedelta

CATALOG, SCHEMA = "workspace", "de_prep"
SEED = 20260904

spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## `teach` — retail orders with clean dimensions
# MAGIC
# MAGIC One row per key in each dimension, and every foreign key resolves. The lessons
# MAGIC can join without ceremony, which is the point: they teach the join, not the
# MAGIC pathology.

# COMMAND ----------

rng = random.Random(SEED)

PRODUCTS = [
    ("ESP-100", "Espresso Machine Compact", "machines",   249.00),
    ("ESP-250", "Espresso Machine Pro",     "machines",   749.00),
    ("GRD-010", "Burr Grinder",             "machines",   129.00),
    ("FLT-500", "Filter Papers 500ct",      "consumables",  12.50),
    ("MUG-021", "Ceramic Mug",              "accessories",   8.75),
    ("BNS-900", "Single Origin Beans 1kg",  "consumables",  28.00),
]
STORES = [
    ("boston",  "Northeast", "MA"),
    ("denver",  "Mountain",  "CO"),
    ("seattle", "Northwest", "WA"),
    ("austin",  "South",     "TX"),
]

spark.createDataFrame(
    PRODUCTS, "product_sku STRING, product_name STRING, category STRING, list_price DOUBLE"
).write.mode("overwrite").saveAsTable("s3_teach_products")

spark.createDataFrame(
    STORES, "store STRING, region STRING, state STRING"
).write.mode("overwrite").saveAsTable("s3_teach_stores")

orders = []
base = date(2026, 3, 1)
for i in range(1, 901):
    sku, _, _, price = rng.choice(PRODUCTS)
    orders.append((
        f"ORD-{i:06d}",
        rng.choice(STORES)[0],
        sku,
        rng.randint(1, 6),
        price,
        round(rng.uniform(0, 0.35), 2) if rng.random() > 0.15 else None,
        base + timedelta(days=rng.randint(0, 27)),
    ))

spark.createDataFrame(
    orders,
    "order_id STRING, store STRING, product_sku STRING, quantity INT, "
    "unit_price DOUBLE, discount_pct DOUBLE, ordered_on DATE",
).write.mode("overwrite").saveAsTable("s3_teach_orders")

print("teach:", spark.table("s3_teach_orders").count(), "orders,",
      spark.table("s3_teach_products").count(), "products,",
      spark.table("s3_teach_stores").count(), "stores")

# COMMAND ----------

# MAGIC %md
# MAGIC ## `assess` — billing events against a slowly-changing plan dimension
# MAGIC
# MAGIC Same *kind* of problem as the lessons — join a fact to a dimension, aggregate,
# MAGIC check quality — with every convenience removed.

# COMMAND ----------

rng = random.Random(SEED + 7)

# Each plan_id appears MORE THAN ONCE, with non-overlapping validity windows.
# The teach dimensions have one row per key; this one does not. An equi-join on
# plan_id alone multiplies every matching event by the number of versions.
PLAN_VERSIONS = [
    # plan_id, plan_name, tier, monthly_price_cents, valid_from, valid_to
    ("PLAN-BASIC", "Basic",      "entry",   900,  date(2025, 1, 1), date(2026, 2, 1)),
    ("PLAN-BASIC", "Basic",      "entry",  1100,  date(2026, 2, 1), date(2099, 1, 1)),
    ("PLAN-TEAM",  "Team",       "mid",    4900,  date(2025, 1, 1), date(2026, 3, 15)),
    ("PLAN-TEAM",  "Team",       "mid",    5400,  date(2026, 3, 15), date(2099, 1, 1)),
    ("PLAN-SCALE", "Scale",      "high",  12900,  date(2025, 6, 1), date(2099, 1, 1)),
    ("PLAN-TRIAL", "Free Trial", "entry",     0,  date(2025, 1, 1), date(2099, 1, 1)),
]

spark.createDataFrame(
    PLAN_VERSIONS,
    "plan_id STRING, plan_name STRING, tier STRING, monthly_price_cents INT, "
    "valid_from DATE, valid_to DATE",
).write.mode("overwrite").saveAsTable("s3_assess_plans")

# COMMAND ----------

KNOWN_PLANS = ["PLAN-BASIC", "PLAN-TEAM", "PLAN-SCALE", "PLAN-TRIAL"]
# Referenced by events but absent from the dimension. An inner join drops these
# silently; the assignment requires them kept and flagged.
ORPHAN_PLANS = ["PLAN-LEGACY", "PLAN-ENTERPRISE"]

ACCOUNTS = [f"ACC-{i:04d}" for i in range(1, 61)]
events = []
event_base = date(2026, 3, 1)

for i in range(1, 601):
    # ~4% of events point at a plan that does not exist in the dimension.
    plan = rng.choice(ORPHAN_PLANS) if rng.random() < 0.04 else rng.choice(KNOWN_PLANS)
    events.append((
        f"BILL-{i:06d}",
        rng.choice(ACCOUNTS),
        plan,
        event_base + timedelta(days=rng.randint(0, 27)),
        # MINOR UNITS. The teach data used decimal currency; this is integer cents.
        rng.choice([900, 1100, 4900, 5400, 12900, 0]),
        rng.choice(["charge", "charge", "charge", "refund"]),
    ))

spark.createDataFrame(
    events,
    "billing_id STRING, account_id STRING, plan_id STRING, event_date DATE, "
    "amount_cents INT, event_type STRING",
).write.mode("overwrite").saveAsTable("s3_assess_billing_events")

print("assess:", spark.table("s3_assess_billing_events").count(), "billing events,",
      spark.table("s3_assess_plans").count(), "plan versions")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Prove the traps are real
# MAGIC
# MAGIC Not "designed in" — measured. If these numbers ever come out equal, the pairing
# MAGIC has stopped working and the assignment became copy-pasteable.

# COMMAND ----------

ev = spark.table("s3_assess_billing_events")
pl = spark.table("s3_assess_plans")

naive = ev.join(pl, on="plan_id", how="inner").count()          # the transplant
correct = ev.count()                                            # target grain

print(f"billing events                     : {ev.count()}")
print(f"rows after a naive equi-join       : {naive}   <- fan-out")
print(f"rows a correct point-in-time join  : {correct}")
print()

orphans = ev.join(pl.select("plan_id").distinct(), on="plan_id", how="left_anti").count()
print(f"events whose plan is missing       : {orphans}  <- an inner join drops these")

dupe_keys = pl.groupBy("plan_id").count().filter("count > 1").count()
print(f"plan_ids with more than one version: {dupe_keys}")

assert naive != correct, "no fan-out - the dimension is not slowly-changing enough"
assert orphans > 0, "no orphan foreign keys - an inner join would be safe"
assert dupe_keys > 0, "dimension keys are unique - equi-join would be correct"
print("\nall three traps present")
