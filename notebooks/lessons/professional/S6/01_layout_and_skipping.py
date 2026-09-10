# Databricks notebook source
# MAGIC %md
# MAGIC # Layout, data skipping and clustering — `PRO-S6-O2`, `PRO-S6-O3`
# MAGIC
# MAGIC Teach table: `pro_s6_teach_events`, slow for exactly one reason — no clustering.

# COMMAND ----------

from pyspark.sql import functions as F

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")
T = "pro_s6_teach_events"

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. What the table looks like before anything
# MAGIC
# MAGIC `DESCRIBE DETAIL` is the first thing to run when a table is slow. File count and
# MAGIC average file size tell you more than a query plan will.

# COMMAND ----------

def profile(table):
    d = spark.sql(f"DESCRIBE DETAIL {table}").collect()[0]
    mb = (d["sizeInBytes"] / max(d["numFiles"], 1)) / (1024 * 1024)
    print(f"{table}: {d['numFiles']} files, {d['sizeInBytes']/1048576:.1f} MB total, "
          f"{mb:.2f} MB avg/file, clustering={d['clusteringColumns']}")
    return d

profile(T)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Data skipping needs statistics *and* locality
# MAGIC
# MAGIC Delta records min/max per column per file. A filter can skip a file whose range
# MAGIC excludes the value — but only if the values are **clustered**. Scatter every
# MAGIC region across every file and no file can be skipped.

# COMMAND ----------

plan = "\n".join(r[0] for r in spark.sql(f"""
    EXPLAIN SELECT count(*) FROM {T} WHERE region = 'emea'
""").collect())
print("scan appears in plan:", "Scan" in plan or "FileScan" in plan)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Liquid clustering
# MAGIC
# MAGIC Clustering keys can be **changed later** with `ALTER TABLE`; a partition column
# MAGIC cannot without rewriting the table. That is the main reason to prefer it.

# COMMAND ----------

spark.sql(f"ALTER TABLE {T} CLUSTER BY (region, event_date)")
spark.sql(f"OPTIMIZE {T}")
profile(T)

# COMMAND ----------

# MAGIC %md
# MAGIC ### Choosing keys
# MAGIC
# MAGIC | Candidate | Good key? | Why |
# MAGIC |---|---|---|
# MAGIC | Frequently filtered, low-to-moderate cardinality | **yes** | files can be skipped |
# MAGIC | Nearly unique (an id) | **no** | every file holds a distinct range; nothing clusters |
# MAGIC | Never filtered | no | the layout does no work |
# MAGIC
# MAGIC Clustering on a near-unique column is a common and expensive mistake: it costs a
# MAGIC rewrite and buys nothing.

# COMMAND ----------

for c in ["region", "event_date", "event_id"]:
    n = spark.table(T).select(c).distinct().count()
    total = spark.table(T).count()
    verdict = "poor - near unique" if n / total > 0.5 else "reasonable"
    print(f"{c:12} {n:>6} distinct of {total}  ({n/total:.0%})  {verdict}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Deletion vectors
# MAGIC
# MAGIC A delete marks rows rather than rewriting files, which makes deletes and updates
# MAGIC far cheaper. The marked rows are cleaned up later during maintenance.

# COMMAND ----------

display(spark.sql(f"DESCRIBE DETAIL {T}").select("numFiles", "sizeInBytes", "clusteringColumns"))
before = profile(T)
spark.sql(f"DELETE FROM {T} WHERE amount < 5")
after = profile(T)
print(f"\nfiles before {before['numFiles']} -> after {after['numFiles']}: a delete need not rewrite everything")

# COMMAND ----------

# MAGIC %md
# MAGIC ## What to carry forward
# MAGIC
# MAGIC - `DESCRIBE DETAIL` first: file count and average size localise most problems.
# MAGIC - Skipping needs statistics **and** locality; clustering provides the locality.
# MAGIC - Clustering keys can change; partition columns cannot.
# MAGIC - Never cluster on a near-unique column.
# MAGIC
# MAGIC The assignment's table is slow for **three** unrelated reasons, and clustering
# MAGIC fixes one of them.
