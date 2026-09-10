# Databricks notebook source
# MAGIC %md
# MAGIC # ASSOC-S4 — generate the `teach` and `assess` datasets
# MAGIC
# MAGIC Section 4 is orchestration, so the datasets are small on purpose — what is being
# MAGIC learned is the job graph, not the transformation.
# MAGIC
# MAGIC ## What makes the assignment un-copyable
# MAGIC
# MAGIC The lesson pipeline is a **clean linear chain**: extract, transform, publish,
# MAGIC each step succeeding. The assignment's source is built to make that chain wrong:
# MAGIC
# MAGIC 1. **A poison batch.** One region's file is malformed. A linear chain fails
# MAGIC    outright; the assignment requires the good regions to publish anyway and the
# MAGIC    bad one to be quarantined.
# MAGIC 2. **Non-idempotent by default.** The assignment is run twice by the grader. An
# MAGIC    append-style task doubles the data; only an idempotent one survives.
# MAGIC 3. **A conditional path.** A late-arriving region must trigger a different branch,
# MAGIC    so a single unconditional flow produces the wrong result.
# MAGIC
# MAGIC Seeded, so the graded answers match everywhere.

# COMMAND ----------

import json, random
from datetime import date, timedelta

CATALOG, SCHEMA = "workspace", "de_prep"
VOL = f"/Volumes/{CATALOG}/{SCHEMA}/raw"
SEED = 20260904

spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")
dbutils.fs.mkdirs(f"{VOL}/s4_teach")
dbutils.fs.mkdirs(f"{VOL}/s4_assess")

# COMMAND ----------

# MAGIC %md
# MAGIC ## `teach` — three clean regional files

# COMMAND ----------

rng = random.Random(SEED)
REGIONS = ["north", "south", "central"]
base = date(2026, 3, 1)

for r in REGIONS:
    rows = ["shipment_id,region,units,shipped_on"]
    for i in range(1, 121):
        rows.append(f"SHP-{r[:1].upper()}{i:05d},{r},{rng.randint(1, 40)},"
                    f"{base + timedelta(days=rng.randint(0, 27))}")
    dbutils.fs.put(f"{VOL}/s4_teach/{r}.csv", "\n".join(rows) + "\n", overwrite=True)

print("teach: 3 regions x 120 shipments")

# COMMAND ----------

# MAGIC %md
# MAGIC ## `assess` — four regions, one of them poisoned
# MAGIC
# MAGIC `west.csv` has a non-numeric `units` value partway through. Reading it with a
# MAGIC declared schema fails the task; the good regions must still publish.

# COMMAND ----------

rng = random.Random(SEED + 11)
A_REGIONS = ["east", "west", "midwest", "pacific"]

for r in A_REGIONS:
    rows = ["order_id,region,units,ordered_on"]
    for i in range(1, 91):
        units = rng.randint(1, 25)
        # west carries the poison: a value that will not cast to INT.
        if r == "west" and i == 47:
            units = "twelve"
        rows.append(f"ORD-{r[:2].upper()}{i:05d},{r},{units},"
                    f"{base + timedelta(days=rng.randint(0, 27))}")
    dbutils.fs.put(f"{VOL}/s4_assess/{r}.csv", "\n".join(rows) + "\n", overwrite=True)

# The late region arrives separately - its presence must trigger a different branch.
late = ["order_id,region,units,ordered_on"]
for i in range(1, 31):
    late.append(f"ORD-LT{i:05d},late_arrivals,{rng.randint(1, 25)},"
                f"{base + timedelta(days=rng.randint(0, 27))}")
dbutils.fs.put(f"{VOL}/s4_assess/_late/late_arrivals.csv", "\n".join(late) + "\n", overwrite=True)

print("assess: 4 regions x 90 orders + 30 late arrivals; west row 47 is poisoned")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Prove the traps are real

# COMMAND ----------

# try_cast, not cast. Under ANSI semantics cast() raises on a bad value rather than
# returning null, so it cannot be used to *find* bad values - which is exactly the
# distinction the assignment's poison row is there to teach.
good = 0
bad = []
for r in A_REGIONS:
    stats = spark.sql(f"""
        SELECT count(*) AS rows,
               sum(CASE WHEN try_cast(units AS INT) IS NULL THEN 1 ELSE 0 END) AS bad
        FROM read_files('{VOL}/s4_assess/{r}.csv', format => 'csv', header => true)
    """).collect()[0]
    if stats["bad"]:
        bad.append((r, int(stats["bad"])))
    else:
        good += int(stats["rows"])

print(f"clean regions total rows : {good}")
print(f"regions with bad rows    : {bad}")
print(f"late-arrival rows        : {spark.read.option('header','true').csv(f'{VOL}/s4_assess/_late').count()}")

assert bad, "no poisoned region - a linear chain would succeed and the assignment is trivial"
assert len(bad) == 1, f"expected exactly one poisoned region, got {bad}"
print("\ntraps present")
