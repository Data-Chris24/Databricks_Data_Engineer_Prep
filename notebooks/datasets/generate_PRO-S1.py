# Databricks notebook source
# MAGIC %md
# MAGIC # PRO-S1 — generate the `teach` and `assess` datasets
# MAGIC
# MAGIC ## What makes the assignment un-copyable
# MAGIC
# MAGIC 1. **The teach source is a snapshot.** Each row is a fact; the latest load is the
# MAGIC    truth. A transform-and-write pipeline is correct.
# MAGIC 2. **The assess source is a change feed.** Rows are *events about* rows — inserts,
# MAGIC    updates and deletes for the same keys — so the current state has to be derived,
# MAGIC    not read.
# MAGIC 3. **The events arrive out of order** and carry a sequence number. Keeping "the
# MAGIC    last row seen" is wrong; you must keep the highest sequence per key.
# MAGIC 4. **Deletes are tombstones, not absences.** A key with a delete as its latest
# MAGIC    event must be gone from the result — a naive dedup keeps it.

# COMMAND ----------

import random
from datetime import date, datetime, timedelta

CATALOG, SCHEMA = "workspace", "de_prep"
SEED = 20260904
spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## `teach` — a snapshot of accounts

# COMMAND ----------

rng = random.Random(SEED)
TIERS = ["bronze", "silver", "gold"]
rows = [(f"ACC-{i:05d}", rng.choice(TIERS), round(rng.uniform(0, 5000), 2),
         date(2026, 3, 1) + timedelta(days=rng.randint(0, 27)))
        for i in range(1, 401)]

spark.createDataFrame(
    rows, "account_id STRING, tier STRING, balance DOUBLE, as_of DATE"
).write.mode("overwrite").saveAsTable("pro_s1_teach_accounts")
print("teach rows:", spark.table("pro_s1_teach_accounts").count())

# COMMAND ----------

# MAGIC %md
# MAGIC ## `assess` — a change feed with out-of-order events and tombstones

# COMMAND ----------

rng = random.Random(SEED + 13)
KEYS = [f"CUST-{i:05d}" for i in range(1, 301)]
base_ts = datetime(2026, 3, 1, 0, 0, 0)

events = []
seq = 0

# Every key gets an initial insert.
for k in KEYS:
    seq += 1
    events.append((k, "insert", rng.choice(TIERS), round(rng.uniform(0, 900), 2),
                   seq, base_ts + timedelta(minutes=seq)))

# 40% of keys get one or more updates, with a later sequence number.
updated = rng.sample(KEYS, int(len(KEYS) * 0.40))
for k in updated:
    for _ in range(rng.randint(1, 3)):
        seq += 1
        events.append((k, "update", rng.choice(TIERS), round(rng.uniform(0, 900), 2),
                       seq, base_ts + timedelta(minutes=seq)))

# 12% get a delete as their FINAL event - these must not survive.
deleted = rng.sample([k for k in KEYS if k not in set(updated[:20])], int(len(KEYS) * 0.12))
for k in deleted:
    seq += 1
    events.append((k, "delete", None, None, seq, base_ts + timedelta(minutes=seq)))

# A few keys are updated again AFTER their delete - a resurrection, which must survive.
resurrected = rng.sample(deleted, 8)
for k in resurrected:
    seq += 1
    events.append((k, "update", rng.choice(TIERS), round(rng.uniform(0, 900), 2),
                   seq, base_ts + timedelta(minutes=seq)))

# Shuffle: the feed arrives out of order, so row order carries no meaning.
rng.shuffle(events)

spark.createDataFrame(
    events,
    "customer_id STRING, op STRING, tier STRING, balance DOUBLE, seq_num INT, event_ts TIMESTAMP",
).write.mode("overwrite").saveAsTable("pro_s1_assess_changes")

print("assess events:", spark.table("pro_s1_assess_changes").count())
print(f"  keys: {len(KEYS)}, updated: {len(updated)}, deleted: {len(deleted)}, "
      f"resurrected: {len(resurrected)}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Prove the traps are real

# COMMAND ----------

from pyspark.sql import functions as F
from pyspark.sql.window import Window

t = spark.table("pro_s1_assess_changes")
total = t.count()
keys = t.select("customer_id").distinct().count()

w = Window.partitionBy("customer_id").orderBy(F.desc("seq_num"))
latest = t.withColumn("rn", F.row_number().over(w)).filter("rn = 1")
surviving = latest.filter("op != 'delete'").count()
tombstoned = latest.filter("op = 'delete'").count()

# What a lesson-style naive dedup (arbitrary row per key) would produce.
naive = t.dropDuplicates(["customer_id"]).count()

print(f"events                     : {total}")
print(f"distinct keys              : {keys}")
print(f"correct surviving rows     : {surviving}")
print(f"keys whose last op is delete: {tombstoned}")
print(f"naive dedup would give     : {naive}  <- keeps tombstoned keys")

assert total > keys, "no multi-event keys - there is nothing to reduce"
assert tombstoned > 0, "no tombstones - deletes are not being tested"
assert naive != surviving, "naive dedup gives the right count - the trap is missing"
assert surviving == keys - tombstoned
print("\ntraps present")
