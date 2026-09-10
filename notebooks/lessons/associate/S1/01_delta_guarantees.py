# Databricks notebook source
# MAGIC %md
# MAGIC # Delta Lake's guarantees — `ASSOC-S1-O1`
# MAGIC
# MAGIC Delta is Parquet **plus an ordered transaction log**. Parquet gives columnar
# MAGIC storage and compression; the log gives everything that matters for reliability.

# COMMAND ----------

from pyspark.sql import functions as F

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")
print("rows:", spark.table("s1_teach_catalog").count())

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. The log is the table's history
# MAGIC
# MAGIC Every write is a numbered version. This is not a feature you enable — it is what
# MAGIC a Delta table *is*.

# COMMAND ----------

display(spark.sql("DESCRIBE HISTORY s1_teach_catalog").select(
    "version", "timestamp", "operation", "operationMetrics"))

# COMMAND ----------

# MAGIC %md
# MAGIC `operationMetrics` records rows and files written per version — the table's own
# MAGIC audit trail, useful long before anything goes wrong.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Time travel
# MAGIC
# MAGIC Any earlier version is queryable by number or by timestamp.

# COMMAND ----------

for v in (0, 1):
    n = spark.sql(f"SELECT count(*) AS n FROM s1_teach_catalog VERSION AS OF {v}").collect()[0]["n"]
    print(f"version {v}: {n} rows")
print("current  :", spark.table("s1_teach_catalog").count(), "rows")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Schema enforcement
# MAGIC
# MAGIC A write that does not fit is **rejected**, rather than silently reshaping the
# MAGIC table. That refusal is a feature: it is what stops a broken upstream job quietly
# MAGIC changing your schema.

# COMMAND ----------

wrong = spark.createDataFrame([("SKU-99999", "machines")], "sku STRING, category STRING")
try:
    wrong.write.mode("append").saveAsTable("s1_teach_catalog")
    print("UNEXPECTED: the mismatched write was accepted")
except Exception as e:
    print(f"rejected as designed: {type(e).__name__}")
    print("A write missing columns cannot append without an explicit schema change.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. ACID means readers never see a half-finished write
# MAGIC
# MAGIC A reader sees version N or version N+1, never a directory mid-update. This is
# MAGIC what plain Parquet in object storage cannot offer, and it is why "just write
# MAGIC Parquet files" fails as soon as anything reads while you write.

# COMMAND ----------

before = spark.table("s1_teach_catalog").count()
spark.createDataFrame(
    [("SKU-90001", "accessories", 19.99, "2026-03-28")],
    "sku STRING, category STRING, price DOUBLE, listed_on STRING"
).withColumn("listed_on", F.col("listed_on").cast("date")) \
 .write.mode("append").saveAsTable("s1_teach_catalog")

after = spark.table("s1_teach_catalog").count()
print(f"{before} -> {after}; the intermediate state was never visible to a reader")

# COMMAND ----------

# MAGIC %md
# MAGIC ## What to carry forward
# MAGIC
# MAGIC | Guarantee | Comes from |
# MAGIC |---|---|
# MAGIC | ACID transactions | the ordered log |
# MAGIC | Time travel | every version being retained |
# MAGIC | Schema enforcement | the log recording the schema |
# MAGIC | Columnar storage, compression | Parquet underneath |
# MAGIC
# MAGIC When a question asks for reliable rollback, an audit trail, and one governed copy
# MAGIC for AI and BI, the answer is Delta Lake for the guarantees and Unity Catalog for
# MAGIC the governance.
