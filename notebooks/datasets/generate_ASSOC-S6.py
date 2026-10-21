# Databricks notebook source
# MAGIC %md
# MAGIC # ASSOC-S6 — generate the `teach` and `assess` datasets
# MAGIC
# MAGIC Troubleshooting needs something actually wrong to find, so these datasets are
# MAGIC built around **pathologies rather than shapes**.
# MAGIC
# MAGIC ## What makes the assignment un-copyable
# MAGIC
# MAGIC 1. **The teach data has one obvious problem** — a single skewed key, visible from
# MAGIC    a `GROUP BY`. The lesson diagnoses it with one query.
# MAGIC 2. **The assess data has three problems of different kinds**, and two of them are
# MAGIC    invisible to that query: a null-rate regression that leaves the row count
# MAGIC    unchanged, and a duplicate-key problem that inflates aggregates without
# MAGIC    changing the number of distinct keys.
# MAGIC 3. **The assignment is graded on the diagnosis**, not on a fix. Copying the
# MAGIC    lesson's single query finds one of three.

# COMMAND ----------

import random
from datetime import date, timedelta

CATALOG, SCHEMA = "workspace", "de_prep"
SEED = 20260904
spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## `teach` — one skewed key
# MAGIC
# MAGIC 70% of rows carry a single customer id. That is enough to make skew visible in a
# MAGIC `GROUP BY` and to make a join on it slow.

# COMMAND ----------

rng = random.Random(SEED)
base = date(2026, 3, 1)
rows = []
for i in range(1, 4001):
    cust = "CUST-00001" if rng.random() < 0.70 else f"CUST-{rng.randint(2, 400):05d}"
    rows.append((f"EVT-{i:06d}", cust, round(rng.uniform(1, 200), 2),
                 base + timedelta(days=rng.randint(0, 27))))

spark.createDataFrame(
    rows, "event_id STRING, customer_id STRING, amount DOUBLE, event_date DATE"
).write.mode("overwrite").saveAsTable("s6_teach_events")

print("teach rows:", spark.table("s6_teach_events").count())

# COMMAND ----------

# MAGIC %md
# MAGIC ## `assess` — three pathologies, two of them invisible to a row count
# MAGIC
# MAGIC | Problem | Visible as | Row count changes? |
# MAGIC |---|---|---|
# MAGIC | Skew | one key dominating | no |
# MAGIC | Null-rate regression | a column half-empty after a given date | **no** |
# MAGIC | Duplicate business keys | totals inflated | yes, but distinct keys do not |

# COMMAND ----------

rng = random.Random(SEED + 5)
CUTOVER = date(2026, 3, 15)
rows = []

for i in range(1, 6001):
    # Problem 1: skew, but on a different key than the lesson's.
    region = "emea" if rng.random() < 0.62 else rng.choice(["amer", "apac", "latam"])
    d = base + timedelta(days=rng.randint(0, 27))

    # Problem 2: after the cutover, an upstream change means channel is often absent.
    if d >= CUTOVER and rng.random() < 0.55:
        channel = None
    else:
        channel = rng.choice(["web", "mobile", "store"])

    rows.append((f"ORD-{i:06d}", region, channel,
                 round(rng.uniform(5, 900), 2), d))

# Problem 3: 240 orders are redelivered verbatim, inflating revenue but not the
# number of distinct order ids.
dupes = [rows[i] for i in range(0, 1200, 5)]
rows.extend(dupes)

spark.createDataFrame(
    rows, "order_id STRING, region STRING, channel STRING, amount DOUBLE, ordered_on DATE"
).write.mode("overwrite").saveAsTable("s6_assess_orders")

print("assess rows:", spark.table("s6_assess_orders").count(),
      f"(including {len(dupes)} redeliveries)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Prove all three pathologies are real

# COMMAND ----------

from pyspark.sql import functions as F

t = spark.table("s6_assess_orders")
total = t.count()
distinct_ids = t.select("order_id").distinct().count()

top_region = (t.groupBy("region").count().orderBy(F.desc("count")).first())
skew_share = top_region["count"] / total

null_before = t.filter(f"ordered_on < DATE'{CUTOVER}'").filter("channel IS NULL").count()
null_after = t.filter(f"ordered_on >= DATE'{CUTOVER}'").filter("channel IS NULL").count()
rows_after = t.filter(f"ordered_on >= DATE'{CUTOVER}'").count()

print(f"rows                     : {total}")
print(f"distinct order_id        : {distinct_ids}   duplicates: {total - distinct_ids}")
print(f"largest region share     : {top_region['region']} {skew_share:.0%}")
print(f"channel nulls before {CUTOVER}: {null_before}")
print(f"channel nulls after      : {null_after} of {rows_after} ({null_after/rows_after:.0%})")

assert total != distinct_ids, "no duplicate keys - the inflation trap is missing"
assert skew_share > 0.5, "no meaningful skew"
assert null_after / max(rows_after, 1) > 0.3, "null-rate regression too small to detect"
assert null_before == 0, "nulls before the cutover would blur the regression"
print("\nall three pathologies present")
