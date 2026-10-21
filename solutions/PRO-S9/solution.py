# Databricks notebook source
# MAGIC %md
# MAGIC # PRO-S9 assignment — reference solution
# MAGIC
# MAGIC No exception was ever raised. Every run succeeded. The diagnosis has to come from
# MAGIC comparing runs against each other.

# COMMAND ----------

from pyspark.sql import functions as F
from pyspark.sql.window import Window

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")
SRC = "pro_s9_assess_daily"
REPORT = "pro_s9_incident_report"

t = spark.table(SRC)
print("rows:", t.count())

# COMMAND ----------

# MAGIC %md
# MAGIC ## There is nothing in the history to find
# MAGIC
# MAGIC Confirm that first, because it rules out the whole of lesson 1.

# COMMAND ----------

hist = spark.sql(f"DESCRIBE HISTORY {SRC}")
ops = [r["operation"] for r in hist.collect()]
print("operations in history:", sorted(set(ops)))
print("failed operations   :", [o for o in ops if "FAIL" in o.upper()] or "none")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Compare each day against the days before it
# MAGIC
# MAGIC A single day tells you nothing. The signal is the **change**.

# COMMAND ----------

per_day = (t.groupBy("run_date")
    .agg(F.count("*").alias("rows"),
         F.countDistinct("source_system").alias("sources"),
         F.round(F.sum("amount"), 2).alias("amount"))
    .orderBy("run_date"))

w = Window.orderBy("run_date")
trend = (per_day
    .withColumn("prev_rows", F.lag("rows").over(w))
    .withColumn("prev_sources", F.lag("sources").over(w))
    .withColumn("rows_delta", F.col("rows") - F.col("prev_rows")))
display(trend)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Locate the first degraded day
# MAGIC
# MAGIC The day the source count dropped and never recovered.

# COMMAND ----------

healthy_sources = per_day.agg(F.max("sources")).collect()[0][0]
degraded = per_day.filter(F.col("sources") < healthy_sources).orderBy("run_date")
first_bad = degraded.first()["run_date"]
degraded_days = degraded.count()

print(f"healthy source count: {healthy_sources}")
print(f"first degraded day  : {first_bad}")
print(f"degraded days       : {degraded_days}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Identify which source stopped
# MAGIC
# MAGIC Present before the regression, absent after it.

# COMMAND ----------

before = {r["source_system"] for r in
          t.filter(F.col("run_date") < F.lit(first_bad)).select("source_system").distinct().collect()}
after = {r["source_system"] for r in
         t.filter(F.col("run_date") >= F.lit(first_bad)).select("source_system").distinct().collect()}
missing = sorted(before - after)
print("before:", sorted(before))
print("after :", sorted(after))
print("stopped:", missing)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Quantify what was lost
# MAGIC
# MAGIC The daily average from the healthy period, multiplied by the degraded days.

# COMMAND ----------

healthy_daily = (per_day.filter(F.col("sources") == healthy_sources)
                 .agg(F.avg("rows")).collect()[0][0])
degraded_daily = (per_day.filter(F.col("sources") < healthy_sources)
                  .agg(F.avg("rows")).collect()[0][0])
rows_lost = int(round((healthy_daily - degraded_daily) * degraded_days))

print(f"healthy day average : {healthy_daily:.1f} rows")
print(f"degraded day average: {degraded_daily:.1f} rows")
print(f"estimated rows lost : {rows_lost}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. The incident report

# COMMAND ----------

report = spark.createDataFrame([(
    str(first_bad),
    missing[0],
    int(degraded_days),
    int(rows_lost),
    f"{missing[0]} stopped contributing on {first_bad}; {degraded_days} runs since then "
    f"succeeded while producing about {rows_lost} fewer rows in total",
)], "first_bad_date STRING, missing_source STRING, degraded_days INT, rows_lost INT, detail STRING")

report.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(REPORT)
display(spark.table(REPORT))

# COMMAND ----------

import json
print(json.dumps({
    "first_bad_date": str(first_bad),
    "missing_source": missing[0],
    "degraded_days": int(degraded_days),
    "rows_lost": int(rows_lost),
    "healthy_sources": int(healthy_sources),
    "total_rows": t.count(),
}, indent=2))
