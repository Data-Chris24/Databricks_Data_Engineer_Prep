# Databricks notebook source
# MAGIC %md
# MAGIC # PRO-S3 assignment — reference solution
# MAGIC
# MAGIC Every row is individually valid. All three defects exist only between rows, so
# MAGIC every check here is a window.

# COMMAND ----------

from pyspark.sql import functions as F
from pyspark.sql.window import Window

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")
SRC = "pro_s3_assess_meter_readings"
TARGET = "pro_s3_quality_findings"

t = spark.table(SRC)
print("rows:", t.count())

# COMMAND ----------

# MAGIC %md
# MAGIC ## The row-level check finds nothing
# MAGIC
# MAGIC Establish that first, so the window work is justified rather than assumed.

# COMMAND ----------

row_level = t.filter(
    F.col("meter_total").isNull() | (F.col("meter_total") < 0) | F.col("read_at").isNull()).count()
print(f"rows failing a row-level check: {row_level}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Finding 1 — the meter ran backwards
# MAGIC
# MAGIC A cumulative meter only increases. A reading lower than its predecessor is
# MAGIC impossible, and only visible relative to that predecessor.

# COMMAND ----------

w = Window.partitionBy("device_id").orderBy("read_at")
withprev = t.withColumn("prev_total", F.lag("meter_total").over(w))

backwards = withprev.filter(F.col("meter_total") < F.col("prev_total"))
n_backwards = backwards.count()
devices_backwards = sorted({r["device_id"] for r in backwards.select("device_id").collect()})
print(f"backwards readings: {n_backwards} across {devices_backwards}")
print()
print("Note: this count exceeds the number of deliberately-reversed readings, because")
print("a duplicate timestamp with a higher value also makes the NEXT reading look like")
print("a decrease. One defect manufacturing another is realistic, and a reason to")
print("investigate findings together rather than in isolation.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Finding 2 — gaps in the sequence
# MAGIC
# MAGIC Readings arrive every 15 minutes. A larger interval means readings are missing —
# MAGIC and missing rows cannot be found by inspecting rows.

# COMMAND ----------

EXPECTED_MIN = 15
gaps = (t.withColumn("prev_ts", F.lag("read_at").over(w))
    .withColumn("gap_min",
                (F.col("read_at").cast("long") - F.col("prev_ts").cast("long")) / 60)
    .filter(F.col("gap_min") > EXPECTED_MIN))

n_gaps = gaps.count()
devices_gaps = sorted({r["device_id"] for r in gaps.select("device_id").collect()})
max_gap = gaps.agg(F.max("gap_min")).collect()[0][0] or 0
print(f"gaps: {n_gaps} across {devices_gaps}, longest {max_gap:.0f} minutes")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Finding 3 — duplicate timestamps with different values
# MAGIC
# MAGIC Two readings for one device at one instant. Neither is invalid; together they
# MAGIC are a contradiction.

# COMMAND ----------

dupes = (t.groupBy("device_id", "read_at")
    .agg(F.count("*").alias("n"), F.countDistinct("meter_total").alias("distinct_values"))
    .filter("n > 1"))
n_dupes = dupes.count()
devices_dupes = sorted({r["device_id"] for r in dupes.select("device_id").collect()})
conflicting = dupes.filter("distinct_values > 1").count()
print(f"duplicate timestamps: {n_dupes} across {devices_dupes}, {conflicting} with conflicting values")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Publish the findings

# COMMAND ----------

findings = spark.createDataFrame([
    ("meter_backwards", float(n_backwards), ",".join(devices_backwards),
     f"{n_backwards} readings lower than their predecessor across {len(devices_backwards)} "
     f"devices; a cumulative meter cannot decrease"),
    ("sequence_gap", float(n_gaps), ",".join(devices_gaps),
     f"{n_gaps} intervals longer than {EXPECTED_MIN} minutes, longest {max_gap:.0f}; "
     f"readings are missing for {len(devices_gaps)} devices"),
    ("duplicate_timestamp", float(n_dupes), ",".join(devices_dupes),
     f"{n_dupes} device-timestamp pairs with more than one reading, {conflicting} of them "
     f"with conflicting values"),
], "finding STRING, affected_rows DOUBLE, affected_devices STRING, detail STRING")

findings.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(TARGET)
display(spark.table(TARGET).orderBy("finding"))

# COMMAND ----------

import json
print(json.dumps({
    "total_rows": t.count(),
    "row_level_failures": row_level,
    "backwards": n_backwards, "backwards_devices": devices_backwards,
    "gaps": n_gaps, "gap_devices": devices_gaps,
    "duplicates": n_dupes, "duplicate_devices": devices_dupes,
    "findings": 3,
}, indent=2))
