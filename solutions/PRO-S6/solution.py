# Databricks notebook source
# MAGIC %md
# MAGIC # PRO-S6 assignment — reference solution
# MAGIC
# MAGIC Three unrelated causes. Clustering fixes one; recommending it for all three
# MAGIC would be the expensive mistake.

# COMMAND ----------

from pyspark.sql import functions as F

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")
SRC = "pro_s6_assess_orders"
REPORT = "pro_s6_optimization_report"

t = spark.table(SRC)
detail = spark.sql(f"DESCRIBE DETAIL {SRC}").collect()[0]
rows = t.count()
print(f"rows {rows}, files {detail['numFiles']}, columns {len(t.columns)}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Finding 1 — small files
# MAGIC
# MAGIC Twenty-four small appends left many tiny files. Every query pays per-file
# MAGIC overhead before it reads a byte of data.

# COMMAND ----------

n_files = int(detail["numFiles"])
size_bytes = int(detail["sizeInBytes"])
avg_mb = round((size_bytes / n_files) / (1024 * 1024), 3)
print(f"{n_files} files, average {avg_mb} MB")
print("target is a few hundred MB per file; OPTIMIZE or predictive optimization compacts them")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Finding 2 — a wide table read in full
# MAGIC
# MAGIC Twenty-five columns, of which a typical query needs three. `SELECT *` reads them
# MAGIC all. This is a projection problem, and no amount of clustering helps it.

# COMMAND ----------

n_cols = len(t.columns)
needed = ["order_id", "region", "amount"]
wasted_pct = round(100.0 * (n_cols - len(needed)) / n_cols, 1)
print(f"{n_cols} columns; a typical query needs {len(needed)} - {wasted_pct}% read and discarded")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Finding 3 — a clustering candidate that would make things worse
# MAGIC
# MAGIC `customer_id` is nearly unique. Clustering on it costs a full rewrite and buys
# MAGIC nothing, because no file can be skipped when every file holds a distinct range.
# MAGIC `region` is the column worth clustering on.

# COMMAND ----------

card = {}
for c in ["customer_id", "region", "order_date"]:
    n = t.select(c).distinct().count()
    card[c] = n
    print(f"{c:12} {n:>6} distinct of {rows}  ({n/rows:.0%})")

bad_key = "customer_id"
good_key = "region"
bad_card_pct = round(100.0 * card[bad_key] / rows, 1)

# COMMAND ----------

# MAGIC %md
# MAGIC ## The report

# COMMAND ----------

report = spark.createDataFrame([
    ("small_files", "OPTIMIZE", float(n_files),
     f"{n_files} files averaging {avg_mb} MB; compaction removes per-file overhead"),
    ("wide_projection", "SELECT only required columns", float(n_cols),
     f"{n_cols} columns but a typical query needs 3; {wasted_pct}% of bytes are read and discarded"),
    ("bad_cluster_key", bad_key, float(bad_card_pct),
     f"{bad_key} is {bad_card_pct}% unique so clustering on it buys nothing; "
     f"cluster on {good_key} instead"),
], "finding STRING, recommendation STRING, metric DOUBLE, detail STRING")

report.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(REPORT)
display(spark.table(REPORT).orderBy("finding"))

# COMMAND ----------

import json
print(json.dumps({
    "rows": rows, "n_files": n_files, "avg_file_mb": avg_mb,
    "n_columns": n_cols, "wasted_pct": wasted_pct,
    "bad_key": bad_key, "bad_card_pct": bad_card_pct, "good_key": good_key,
    "findings": 3,
}, indent=2))
