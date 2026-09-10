# Databricks notebook source
# MAGIC %md
# MAGIC # ASSOC-S5 — generate the `teach` and `assess` datasets
# MAGIC
# MAGIC CI/CD is about **configuration**, so what differs between teach and assess is the
# MAGIC shape of the deployment, not the data. Both sides get a small identical dataset
# MAGIC in two schemas standing in for two environments.
# MAGIC
# MAGIC ## What makes the assignment un-copyable
# MAGIC
# MAGIC 1. **The lesson deploys one target.** The assignment needs two, promoting the
# MAGIC    same definition rather than duplicating it.
# MAGIC 2. **The lesson hardcodes its catalog and schema.** The assignment must drive
# MAGIC    them from a bundle variable **overridden per target**, so the same job writes
# MAGIC    to a different place in each environment. Copying the lesson gives you one
# MAGIC    hardcoded destination and no override.
# MAGIC 3. **The assignment is graded on the difference between the environments** —
# MAGIC    identical row counts, different locations. A single hardcoded target cannot
# MAGIC    produce that.

# COMMAND ----------

import random
from datetime import date, timedelta

CATALOG = "workspace"
SEED = 20260904

# Two schemas standing in for two environments on one Free Edition workspace.
for schema in ("de_prep", "de_prep_staging"):
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{schema}")
print("schemas ready: de_prep (prod-like), de_prep_staging")

# COMMAND ----------

rng = random.Random(SEED)
base = date(2026, 3, 1)
rows = []
for i in range(1, 241):
    rows.append((
        f"TXN-{i:06d}",
        rng.choice(["web", "mobile", "store"]),
        round(rng.uniform(5, 500), 2),
        base + timedelta(days=rng.randint(0, 27)),
    ))

df = spark.createDataFrame(
    rows, "txn_id STRING, channel STRING, amount DOUBLE, txn_date DATE")

# The source lives in one place; only the *destination* differs per environment.
df.write.mode("overwrite").saveAsTable(f"{CATALOG}.de_prep.s5_source_transactions")
print("source rows:", spark.table(f"{CATALOG}.de_prep.s5_source_transactions").count())

# COMMAND ----------

# MAGIC %md
# MAGIC ## Prove the environments are distinguishable

# COMMAND ----------

schemas = [r["databaseName"] for r in spark.sql(f"SHOW SCHEMAS IN {CATALOG}").collect()]
print("schemas present:", [s for s in schemas if s.startswith("de_prep")])

assert "de_prep" in schemas and "de_prep_staging" in schemas, \
    "two schemas are needed to stand in for two environments"
print("\nready - the assignment must publish to BOTH, from one definition")
