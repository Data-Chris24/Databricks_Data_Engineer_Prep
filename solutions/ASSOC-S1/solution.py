# Databricks notebook source
# MAGIC %md
# MAGIC # ASSOC-S1 assignment — reference solution
# MAGIC
# MAGIC The current version of the table is wrong. The correct data exists only in the
# MAGIC history, which is exactly what Delta's log is for.

# COMMAND ----------

from pyspark.sql import functions as F

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")
SRC = "s1_assess_catalog"
RECOVERED = "s1_recovered_catalog"
REPORT = "s1_incident_report"

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Read the history before touching anything
# MAGIC
# MAGIC `operationMetrics` shows what each version did. A version that wrote far fewer
# MAGIC rows than the one before it, with `mode=Overwrite`, is the shape of a bad load.

# COMMAND ----------

hist = spark.sql(f"DESCRIBE HISTORY {SRC}")
display(hist.select("version", "timestamp", "operation", "operationMetrics"))

versions = sorted(r["version"] for r in hist.select("version").collect())
print("versions available:", versions)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Find the last good version
# MAGIC
# MAGIC Do not assume which one it is — measure. The bad load zeroed every price, so a
# MAGIC version whose prices are all zero is damaged.

# COMMAND ----------

profile = []
for v in versions:
    df = spark.sql(f"SELECT * FROM {SRC} VERSION AS OF {v}")
    rows = df.count()
    zeros = df.filter("price = 0.0").count()
    revenue = df.agg(F.round(F.sum("price"), 2)).collect()[0][0] or 0.0
    profile.append((v, rows, zeros, float(revenue)))
    print(f"v{v}: {rows:>4} rows, {zeros:>4} zero-price, revenue {revenue}")

# The last version where prices are intact.
good_version = max(v for v, rows, zeros, rev in profile if zeros == 0)
print(f"\nlast good version: {good_version}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Recover
# MAGIC
# MAGIC Publish the good version as its own table rather than restoring in place, so the
# MAGIC damaged history is preserved for the incident record.

# COMMAND ----------

recovered = spark.sql(f"SELECT * FROM {SRC} VERSION AS OF {good_version}")
recovered.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(RECOVERED)
print(f"recovered {spark.table(RECOVERED).count()} rows from v{good_version}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. The incident report
# MAGIC
# MAGIC What happened, when, what it cost, and where the good data is.

# COMMAND ----------

cur = spark.table(SRC)
good = spark.table(RECOVERED)

cur_rows, good_rows = cur.count(), good.count()
cur_rev = float(cur.agg(F.round(F.sum("price"), 2)).collect()[0][0] or 0.0)
good_rev = float(good.agg(F.round(F.sum("price"), 2)).collect()[0][0] or 0.0)
bad_version = max(versions)

report = spark.createDataFrame([(
    int(bad_version),
    int(good_version),
    int(good_rows - cur_rows),
    round(good_rev - cur_rev, 2),
    f"v{bad_version} overwrote the table with {cur_rows} rows and zeroed every price; "
    f"v{good_version} holds {good_rows} rows and {good_rev} of value",
)], "bad_version INT, good_version INT, rows_lost INT, value_lost DOUBLE, detail STRING")

report.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(REPORT)
display(spark.table(REPORT))

# COMMAND ----------

import json
print(json.dumps({
    "versions": versions,
    "good_version": int(good_version),
    "bad_version": int(bad_version),
    "current_rows": cur_rows,
    "recovered_rows": good_rows,
    "rows_lost": int(good_rows - cur_rows),
    "value_lost": round(good_rev - cur_rev, 2),
    "recovered_revenue": good_rev,
}, indent=2))
