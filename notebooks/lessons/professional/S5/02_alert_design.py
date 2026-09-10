# Databricks notebook source
# MAGIC %md
# MAGIC # Designing an alert that is worth keeping — `PRO-S5-O5`, `PRO-S5-O6`

# COMMAND ----------

from pyspark.sql import functions as F
from pyspark.sql.window import Window

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. The cost of a bad alert
# MAGIC
# MAGIC | Failure | Consequence |
# MAGIC |---|---|
# MAGIC | Fires too often | ignored within a fortnight; the real one is ignored too |
# MAGIC | Never fires | indistinguishable from no alert at all |
# MAGIC | Fires on a benign change | trains people that alerts mean nothing |
# MAGIC
# MAGIC An alert nobody trusts is worse than none, because it costs attention and buys
# MAGIC false confidence.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Compare like with like
# MAGIC
# MAGIC When a metric has a cycle, the comparison must respect the cycle. Comparing a
# MAGIC Saturday to the previous day is comparing a weekend to a weekday.

# COMMAND ----------

m = spark.table("pro_s5_teach_metrics")

w7 = Window.orderBy("run_date").rowsBetween(-7, -1)
trend = (m
    .withColumn("prev_7d_avg", F.round(F.avg("rows_processed").over(w7), 1))
    .withColumn("pct_of_baseline",
                F.round(100.0 * F.col("rows_processed") / F.col("prev_7d_avg"), 1)))
display(trend.orderBy(F.desc("run_date")).limit(10))

# COMMAND ----------

# MAGIC %md
# MAGIC A rolling baseline moves with the metric, so it survives a level shift that a
# MAGIC fixed threshold would either miss or scream about. On a seasonal metric you go
# MAGIC one step further and compare **same day of week**.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Direction matters
# MAGIC
# MAGIC "Unusual" is not a useful alert condition. A metric doubling because a campaign
# MAGIC launched is not an incident; the same deviation downward usually is. Alert on the
# MAGIC direction that means something.

# COMMAND ----------

alerts = trend.filter(F.col("pct_of_baseline") < 90)
print("days more than 10% below the rolling baseline:", alerts.count())
print("(none expected - the teach metric is stable)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Persistence beats a single reading
# MAGIC
# MAGIC One low day is noise. Several consecutive low days is a trend. Requiring
# MAGIC persistence is the cheapest way to cut false positives without losing real
# MAGIC incidents — you trade a day of detection latency for an alert people believe.

# COMMAND ----------

# MAGIC %md
# MAGIC ```sql
# MAGIC -- fire only when the last 3 days are all below baseline
# MAGIC SELECT count(*) AS consecutive_low
# MAGIC FROM (
# MAGIC   SELECT run_date, rows_processed,
# MAGIC          avg(rows_processed) OVER (
# MAGIC            ORDER BY run_date ROWS BETWEEN 14 PRECEDING AND 8 PRECEDING
# MAGIC          ) AS baseline
# MAGIC   FROM metrics
# MAGIC )
# MAGIC WHERE run_date >= current_date() - 2
# MAGIC   AND rows_processed < baseline * 0.9;
# MAGIC ```
# MAGIC
# MAGIC Fire when `consecutive_low = 3`.

# COMMAND ----------

# MAGIC %md
# MAGIC ## What to carry forward
# MAGIC
# MAGIC - Compare like with like: same day of week when the metric is seasonal.
# MAGIC - Alert on **direction**, not on deviation.
# MAGIC - Require persistence; trade a day of latency for an alert people trust.
# MAGIC - Notify a channel, not a person.
# MAGIC
# MAGIC The assignment applies all four to a metric where the naive threshold provably
# MAGIC cannot work.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Next
# MAGIC
# MAGIC When the lessons are done, open the graded assignment: [PRO-S5 assignment notebook](../../../assignments/PRO-S5/assignment) · [the task](../../../assignments/PRO-S5/README.md).
