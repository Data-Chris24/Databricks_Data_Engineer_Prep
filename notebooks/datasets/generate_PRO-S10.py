# Databricks notebook source
# MAGIC %md
# MAGIC # PRO-S10 — generate the `teach` and `assess` datasets
# MAGIC
# MAGIC Dimensional modelling. The pairing differs in whether dimension attributes
# MAGIC **change over time**, which is what decides the whole design.
# MAGIC
# MAGIC ## What makes the assignment un-copyable
# MAGIC
# MAGIC 1. **The teach dimension is static.** A customer's attributes never change, so a
# MAGIC    plain star schema with a natural key is correct.
# MAGIC 2. **The assess dimension changes.** Customers move between segments and regions
# MAGIC    over time, so a fact must join to the version of the dimension that was
# MAGIC    **current when the fact happened** — a Type 2 slowly-changing dimension with
# MAGIC    surrogate keys.
# MAGIC 3. **A natural-key join gives a plausible wrong answer**: every fact gets today's
# MAGIC    attributes, so historical revenue is silently re-attributed to whichever
# MAGIC    segment a customer happens to be in now.

# COMMAND ----------

import random
from datetime import date, timedelta

CATALOG, SCHEMA = "workspace", "de_prep"
SEED = 20260904
spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## `teach` — a static dimension and a fact table

# COMMAND ----------

rng = random.Random(SEED)
SEGMENTS = ["smb", "mid_market", "enterprise"]
REGIONS = ["emea", "amer", "apac"]
base = date(2026, 1, 1)

customers = [(f"C-{i:04d}", rng.choice(SEGMENTS), rng.choice(REGIONS))
             for i in range(1, 61)]
spark.createDataFrame(
    customers, "customer_id STRING, segment STRING, region STRING"
).write.mode("overwrite").saveAsTable("pro_s10_teach_customers")

sales = []
for i in range(1, 601):
    c = rng.choice(customers)[0]
    sales.append((f"S-{i:05d}", c, round(rng.uniform(50, 5000), 2),
                  base + timedelta(days=rng.randint(0, 200))))
spark.createDataFrame(
    sales, "sale_id STRING, customer_id STRING, amount DOUBLE, sold_on DATE"
).write.mode("overwrite").saveAsTable("pro_s10_teach_sales")

print("teach:", len(customers), "customers,", len(sales), "sales")

# COMMAND ----------

# MAGIC %md
# MAGIC ## `assess` — a dimension whose attributes change over time
# MAGIC
# MAGIC Each customer has one or more versions with a validity window. A fact must join
# MAGIC to the version in effect on its own date.

# COMMAND ----------

rng = random.Random(SEED + 41)
CUSTOMERS = [f"K-{i:04d}" for i in range(1, 81)]
START = date(2025, 1, 1)
END = date(2099, 1, 1)

versions = []
changed_customers = set()

for c in CUSTOMERS:
    seg = rng.choice(SEGMENTS)
    reg = rng.choice(REGIONS)
    valid_from = START
    # 45% of customers change segment partway through 2026.
    if rng.random() < 0.45:
        changed_customers.add(c)
        change_on = date(2026, rng.randint(3, 8), 1)
        versions.append((c, seg, reg, valid_from, change_on, False))
        new_seg = rng.choice([s for s in SEGMENTS if s != seg])
        versions.append((c, new_seg, reg, change_on, END, True))
    else:
        versions.append((c, seg, reg, valid_from, END, True))

spark.createDataFrame(
    versions,
    "customer_id STRING, segment STRING, region STRING, valid_from DATE, valid_to DATE, is_current BOOLEAN",
).write.mode("overwrite").saveAsTable("pro_s10_assess_customer_versions")

orders = []
for i in range(1, 901):
    c = rng.choice(CUSTOMERS)
    # Orders spread across 2026, so many fall before a customer's change date.
    d = date(2026, 1, 1) + timedelta(days=rng.randint(0, 330))
    orders.append((f"O-{i:05d}", c, round(rng.uniform(100, 9000), 2), d))

spark.createDataFrame(
    orders, "order_id STRING, customer_id STRING, amount DOUBLE, ordered_on DATE"
).write.mode("overwrite").saveAsTable("pro_s10_assess_orders")

print("assess:", len(CUSTOMERS), "customers,", len(versions), "versions,",
      len(orders), "orders;", len(changed_customers), "customers changed segment")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Prove a natural-key join misattributes revenue

# COMMAND ----------

from pyspark.sql import functions as F

o = spark.table("pro_s10_assess_orders")
v = spark.table("pro_s10_assess_customer_versions")

# The naive model: join to the CURRENT version of each customer.
current = v.filter("is_current")
naive = (o.join(current, on="customer_id", how="left")
         .groupBy("segment").agg(F.round(F.sum("amount"), 2).alias("revenue")))

# The correct model: join to the version in effect on the order date.
cond = ((o.customer_id == v.customer_id) &
        (o.ordered_on >= v.valid_from) & (o.ordered_on < v.valid_to))
correct = (o.alias("o").join(v.alias("v"), cond, "left")
           .groupBy("v.segment").agg(F.round(F.sum("o.amount"), 2).alias("revenue")))

naive_map = {r["segment"]: r["revenue"] for r in naive.collect()}
correct_map = {r["segment"]: r["revenue"] for r in correct.collect()}

print("revenue by segment")
print(f"{'segment':14} {'naive (current)':>18} {'correct (as-of)':>18} {'difference':>14}")
for s in sorted(set(naive_map) | set(correct_map)):
    n, c = naive_map.get(s, 0), correct_map.get(s, 0)
    print(f"{str(s):14} {n:>18,.2f} {c:>18,.2f} {n - c:>14,.2f}")

assert naive.count() == correct.count(), "segment sets differ unexpectedly"
assert naive_map != correct_map, "the two models agree - the trap is missing"
assert o.count() == (o.alias("o").join(v.alias("v"), cond, "left").count()), \
    "the as-of join changed the row count; validity windows must not overlap"
print("\nthe two models disagree, and both look plausible")
