# Databricks notebook source
# MAGIC %md
# MAGIC # Pipeline health and table layout — `ASSOC-S6-O1`, `O2`, `O4`, `O5`

# COMMAND ----------

from pyspark.sql import functions as F

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. A successful run can still be unhealthy
# MAGIC
# MAGIC Run history is where an investigation starts. Comparing a slow run's task
# MAGIC durations against previous runs localises the problem before you open a log — if
# MAGIC one task went from 2 minutes to 70 while the rest held steady, you know where to
# MAGIC look.
# MAGIC
# MAGIC A job that normally takes 20 minutes and took 90 has told you something, even
# MAGIC though it went green. Left alone that becomes a missed SLA or a quota breach.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Delta history is the table's own run log

# COMMAND ----------

display(spark.sql("DESCRIBE HISTORY s6_teach_events").select(
    "version", "timestamp", "operation", "operationMetrics").limit(5))

# COMMAND ----------

# MAGIC %md
# MAGIC `operationMetrics` records rows and files written per version. A version that
# MAGIC wrote far more files than usual for the same row count is a small-file problem
# MAGIC forming; one that wrote far fewer rows than usual is an upstream problem.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Null rate is the signal for *silent* degradation
# MAGIC
# MAGIC The job succeeds, the row count looks right, and the data is quietly wrong. This
# MAGIC is the check worth running as a metric rather than only when something breaks.

# COMMAND ----------

t = spark.table("s6_teach_events")
display(t.select([
    F.round(100.0 * F.sum(F.col(c).isNull().cast("int")) / F.count("*"), 2).alias(f"pct_null_{c}")
    for c in t.columns
]))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Table layout
# MAGIC
# MAGIC **Liquid clustering** is preferred over partitioning for most tables. A partition
# MAGIC column is a decision you are stuck with — changing it means rewriting the table —
# MAGIC and choosing badly gives huge skewed partitions or millions of tiny files.
# MAGIC Clustering keys can be changed with `ALTER TABLE`.

# COMMAND ----------

spark.sql("ALTER TABLE s6_teach_events CLUSTER BY (customer_id, event_date)")
display(spark.sql("DESCRIBE DETAIL s6_teach_events").select(
    "format", "numFiles", "sizeInBytes", "clusteringColumns"))

# COMMAND ----------

# MAGIC %md
# MAGIC Clustering keys can be changed later without rewriting the table, which is
# MAGIC exactly what partitioning cannot do.

# COMMAND ----------

spark.sql("ALTER TABLE s6_teach_events CLUSTER BY (event_date)")
display(spark.sql("DESCRIBE DETAIL s6_teach_events").select("clusteringColumns"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Compute failures — `ASSOC-S6-O5`
# MAGIC
# MAGIC | Failure | Usual cause |
# MAGIC |---|---|
# MAGIC | Cluster will not start | cloud quota, bad init script, unavailable instance type |
# MAGIC | Library conflict | two libraries pinning incompatible versions of a shared dependency |
# MAGIC | Driver OOM | `collect()` or `toPandas()` on a large result |
# MAGIC | Executor OOM | partitions too large, or heavy skew |
# MAGIC
# MAGIC **Driver OOM is not fixed by a bigger cluster.** `collect()` pulls every row into
# MAGIC a single JVM; more executors do not help.
# MAGIC
# MAGIC > On serverless there are no clusters to configure, so these particular failures
# MAGIC > cannot occur — and cannot be practised. This objective is theory on Free
# MAGIC > Edition; see `docs/optional-classic-track.md` for the paid-tier lab.

# COMMAND ----------

# MAGIC %md
# MAGIC ## What to carry forward
# MAGIC
# MAGIC - Start from run history and narrow before opening logs.
# MAGIC - `DESCRIBE HISTORY` is the table's own audit trail.
# MAGIC - Track null rate; it is how silent corruption announces itself.
# MAGIC - Liquid clustering over partitioning; keys can change, partitions cannot.
# MAGIC
# MAGIC Now do the assignment. Its table has **three** problems, and the `GROUP BY` from
# MAGIC lesson 1 finds only one of them.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Next
# MAGIC
# MAGIC When the lessons are done, open the graded assignment: [ASSOC-S6 assignment notebook](../../../assignments/ASSOC-S6/assignment) · [the task](../../../assignments/ASSOC-S6/README.md).
