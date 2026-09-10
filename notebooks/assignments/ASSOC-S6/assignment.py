# Databricks notebook source
# MAGIC %md
# MAGIC # ASSOC-S6 assignment — your work goes here
# MAGIC
# MAGIC Read `README.md` in this folder for the task and the output contract.
# MAGIC
# MAGIC **The lesson's GROUP BY finds one of three problems here. Two of them leave the row count and the distinct-key count looking perfectly normal.**
# MAGIC
# MAGIC When you are done, go back to the study app and press **Grade my assignment**.
# MAGIC Each failing check says what it expected and why.

# COMMAND ----------

from pyspark.sql import functions as F

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")
SOURCE = "s6_assess_orders"           # do not clean it; the state is the evidence
REPORT = "s6_health_report"
orders = spark.table(SOURCE)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 0 — look
# MAGIC
# MAGIC Row count, distinct keys, null counts per column, the biggest groups. Which numbers look normal but are not?

# COMMAND ----------

# print(orders.count(), orders.select("order_id").distinct().count())
# display(orders.describe())

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1 — duplicate_keys
# MAGIC
# MAGIC How many rows are redeliveries, i.e. rows beyond the first for a key?

# COMMAND ----------

# dup_rows = orders.count() - orders.select(<key>).distinct().count()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2 — null_regression
# MAGIC
# MAGIC A column that was fine and then started arriving null. Find when it begins and count the nulls after that point.

# COMMAND ----------

# by_day = orders.groupBy(<date col>).agg(F.sum(F.col(<col>).isNull().cast("int")).alias("nulls")).orderBy(<date col>)
# display(by_day)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3 — skew
# MAGIC
# MAGIC The largest group's share of all rows, as a percentage. Which column is skewed?

# COMMAND ----------

# shares = orders.groupBy(<col>).count().withColumn("pct", F.col("count") * 100.0 / orders.count()).orderBy(F.desc("pct"))
# display(shares)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 4 — write the report
# MAGIC
# MAGIC One row per finding, naming the column, with a `detail` a colleague could act on. Column order matters.

# COMMAND ----------

# rows = [("duplicate_keys", <column>, float(<metric>), "..."),
#         ("null_regression", <column>, float(<metric>), "..."),
#         ("skew", <column>, float(<metric>), "...")]
# spark.createDataFrame(rows, "finding STRING, column_name STRING, metric DOUBLE, detail STRING") \
#     .write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(REPORT)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Check yourself before grading

# COMMAND ----------

# display(spark.table(REPORT))
