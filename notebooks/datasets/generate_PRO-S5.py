# Databricks notebook source
# MAGIC %md
# MAGIC # PRO-S5 — generate the `teach` and `assess` datasets
# MAGIC
# MAGIC Monitoring and alerting. The pairing differs in **what a useful alert looks
# MAGIC like**, because the naive threshold is the whole trap.
# MAGIC
# MAGIC ## What makes the assignment un-copyable
# MAGIC
# MAGIC 1. **The teach metric is stable**, so a fixed threshold works: pick a number,
# MAGIC    alert when it is crossed.
# MAGIC 2. **The assess metric has a weekly cycle.** Weekends are legitimately quiet, so
# MAGIC    any fixed threshold either fires every weekend or never fires at all.
# MAGIC 3. **The real incident hides inside normal range.** A gradual degradation stays
# MAGIC    above the weekend floor throughout, so absolute thresholds cannot see it.
# MAGIC 4. **One day is a genuine spike** that must NOT alert — a legitimate campaign,
# MAGIC    so an alert on "unusual" without direction is a false positive.

# COMMAND ----------

import math, random
from datetime import date, timedelta

CATALOG, SCHEMA = "workspace", "de_prep"
SEED = 20260904
spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## `teach` — a stable daily metric

# COMMAND ----------

rng = random.Random(SEED)
base = date(2026, 1, 1)
rows = []
for d in range(90):
    day = base + timedelta(days=d)
    rows.append((day, 1000 + rng.randint(-40, 40), round(rng.uniform(2.0, 4.0), 2)))

spark.createDataFrame(
    rows, "run_date DATE, rows_processed INT, runtime_minutes DOUBLE"
).write.mode("overwrite").saveAsTable("pro_s5_teach_metrics")
print("teach days:", spark.table("pro_s5_teach_metrics").count())

# COMMAND ----------

# MAGIC %md
# MAGIC ## `assess` — weekly seasonality, a hidden degradation, and a benign spike

# COMMAND ----------

rng = random.Random(SEED + 31)
rows = []
DEGRADE_FROM = 60          # day index where a slow leak begins
SPIKE_DAY = 40             # a legitimate campaign - must not alert

for d in range(90):
    day = base + timedelta(days=d)
    dow = day.weekday()                       # 0 = Monday

    # Weekly cycle: weekends run at ~45% of a weekday.
    seasonal = 0.45 if dow >= 5 else 1.0
    volume = 2000 * seasonal

    # A gradual degradation from day 60 - about 1.2% lost per day, and it never
    # falls below the weekend floor, so no absolute threshold catches it.
    if d >= DEGRADE_FROM:
        volume *= (1 - 0.012 * (d - DEGRADE_FROM))

    if d == SPIKE_DAY:
        volume *= 2.4                          # benign campaign spike

    rows.append((day, int(volume + rng.randint(-30, 30)),
                 round(3.0 + rng.uniform(-0.4, 0.4), 2),
                 "weekend" if dow >= 5 else "weekday"))

spark.createDataFrame(
    rows, "run_date DATE, rows_processed INT, runtime_minutes DOUBLE, day_type STRING"
).write.mode("overwrite").saveAsTable("pro_s5_assess_metrics")
print("assess days:", spark.table("pro_s5_assess_metrics").count())

# COMMAND ----------

# MAGIC %md
# MAGIC ## Prove the trap: no fixed threshold separates the incident from the weekend

# COMMAND ----------

from pyspark.sql import functions as F

t = spark.table("pro_s5_assess_metrics")
rowsd = {r["run_date"]: r["rows_processed"] for r in t.collect()}
days = sorted(rowsd)

weekend_min = min(rowsd[d] for d in days if d.weekday() >= 5)
weekend_max = max(rowsd[d] for d in days if d.weekday() >= 5)
degraded_days = days[DEGRADE_FROM:]
degraded_weekday_min = min(rowsd[d] for d in degraded_days if d.weekday() < 5)
healthy_weekday_min = min(rowsd[d] for d in days[:DEGRADE_FROM] if d.weekday() < 5)

print(f"weekend range              : {weekend_min} - {weekend_max}")
print(f"healthy weekday minimum    : {healthy_weekday_min}")
print(f"degraded weekday minimum   : {degraded_weekday_min}")
print(f"spike day ({days[SPIKE_DAY]}): {rowsd[days[SPIKE_DAY]]}")

# A threshold above the weekend maximum fires every weekend.
# A threshold below the weekend minimum never fires, even at full degradation.
assert degraded_weekday_min > weekend_max, (
    "the degradation dips below the weekend range, so a fixed threshold could "
    "separate them and the trap is missing")
assert rowsd[days[SPIKE_DAY]] > healthy_weekday_min * 1.5, "the benign spike is not distinctive"
print("\nno fixed threshold separates the incident from normal weekend behaviour")
