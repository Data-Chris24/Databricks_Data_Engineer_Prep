# Databricks notebook source
# MAGIC %md
# MAGIC # PRO-S5 assignment — reference solution
# MAGIC
# MAGIC The metric has a weekly cycle, so a fixed threshold provably cannot work. The
# MAGIC baseline has to be same-day-of-week.

# COMMAND ----------

from pyspark.sql import functions as F
from pyspark.sql.window import Window

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")
SRC = "pro_s5_assess_metrics"
TARGET = "pro_s5_alert_evaluation"

m = spark.table(SRC)
print("days:", m.count())

# COMMAND ----------

# MAGIC %md
# MAGIC ## Why a fixed threshold cannot work here
# MAGIC
# MAGIC Demonstrate it before designing around it, so the design is justified rather
# MAGIC than asserted.

# COMMAND ----------

wk = m.filter("day_type = 'weekend'").agg(
    F.min("rows_processed").alias("min"), F.max("rows_processed").alias("max")).collect()[0]
wd = m.filter("day_type = 'weekday'").agg(
    F.min("rows_processed").alias("min"), F.max("rows_processed").alias("max")).collect()[0]
print(f"weekend range: {wk['min']} - {wk['max']}")
print(f"weekday range: {wd['min']} - {wd['max']}")
print()
print(f"A threshold above {wk['max']} fires every weekend.")
print(f"A threshold below {wk['min']} never fires, even at full degradation.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. A same-day-of-week baseline
# MAGIC
# MAGIC Compare each day to the previous four of the **same weekday**, so the weekly
# MAGIC cycle cancels out. The window is offset by one so today never contributes to its
# MAGIC own baseline.

# COMMAND ----------

withdow = m.withColumn("dow", F.dayofweek("run_date"))
w = Window.partitionBy("dow").orderBy("run_date").rowsBetween(-4, -1)

scored = (withdow
    .withColumn("baseline", F.avg("rows_processed").over(w))
    .withColumn("pct_of_baseline",
                F.when(F.col("baseline").isNotNull(),
                       F.round(100.0 * F.col("rows_processed") / F.col("baseline"), 1)))
    .filter(F.col("baseline").isNotNull()))

display(scored.select("run_date", "day_type", "rows_processed",
                      F.round("baseline", 1).alias("baseline"), "pct_of_baseline")
        .orderBy(F.desc("run_date")).limit(10))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Direction and persistence
# MAGIC
# MAGIC Alert only on a **drop** — the spike is a campaign, not an incident — and only
# MAGIC when it persists, so a single noisy day does not fire.

# COMMAND ----------

THRESHOLD_PCT = 92.0
PERSISTENCE = 3

flagged = scored.withColumn("is_low", (F.col("pct_of_baseline") < THRESHOLD_PCT).cast("int"))

wrun = Window.orderBy("run_date").rowsBetween(-(PERSISTENCE - 1), 0)
evaluated = (flagged
    .withColumn("low_in_window", F.sum("is_low").over(wrun))
    .withColumn("should_alert", (F.col("low_in_window") == PERSISTENCE))
    .withColumn("is_spike", F.col("pct_of_baseline") > 150))

alert_days = evaluated.filter("should_alert").orderBy("run_date")
first_alert = alert_days.first()
print(f"alerting days       : {alert_days.count()}")
print(f"first alert on      : {first_alert['run_date'] if first_alert else None}")
print(f"spike days flagged  : {evaluated.filter('is_spike').count()}")
print(f"spikes that alerted : {evaluated.filter('is_spike AND should_alert').count()}  <- must be 0")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Publish the evaluation

# COMMAND ----------

final = evaluated.select(
    "run_date", "day_type", "rows_processed",
    F.round("baseline", 1).alias("baseline"),
    "pct_of_baseline",
    F.col("should_alert").alias("should_alert"),
)
final.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(TARGET)
print("rows:", spark.table(TARGET).count())

# COMMAND ----------

import json
t = spark.table(TARGET)
weekend_alerts = t.filter("should_alert AND day_type = 'weekend'").count()
print(json.dumps({
    "evaluated_days": t.count(),
    "alert_days": t.filter("should_alert").count(),
    "first_alert_date": str(first_alert["run_date"]) if first_alert else None,
    "weekend_alerts": weekend_alerts,
    "spike_alerts": evaluated.filter("is_spike AND should_alert").count(),
    "threshold_pct": THRESHOLD_PCT,
    "persistence": PERSISTENCE,
}, indent=2))
