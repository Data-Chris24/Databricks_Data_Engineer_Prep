# Databricks notebook source
# MAGIC %md
# MAGIC # ASSOC-S2 assignment — reference solution
# MAGIC
# MAGIC **Learners: this is the answer.** Nothing stops you reading it, but the
# MAGIC assignment is the only part that teaches anything. Read it after you have a
# MAGIC passing suite, or after you are genuinely stuck.
# MAGIC
# MAGIC Its other job is to generate the expected-value fixtures the test suite
# MAGIC asserts against, so the tests never need this notebook present.

# COMMAND ----------

from pyspark.sql import functions as F

CATALOG, SCHEMA = "workspace", "de_prep"
RAW = f"/Volumes/{CATALOG}/{SCHEMA}/raw/s2_assess"
TARGET = "silver_sensor_readings"

spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Read, merging schemas across batches
# MAGIC
# MAGIC `battery_pct` only exists in the third file. Without `mergeSchema`, Spark
# MAGIC infers from a sample of files and the column may vanish silently — the exact
# MAGIC failure the assignment is testing for.

# COMMAND ----------

raw = (spark.read
       .option("mergeSchema", "true")
       .option("multiLine", "false")
       .json(RAW))

raw.printSchema()
print("device documents:", raw.count())

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Explode to one row per reading
# MAGIC
# MAGIC The grain the contract asks for does not exist in the source: each document
# MAGIC holds an array. This is the step no amount of `COPY INTO` will do for you.

# COMMAND ----------

exploded = (raw
    .select("device_id", "site", "firmware", F.explode("readings").alias("r"))
    .select(
        F.col("r.event_id").alias("event_id"),
        "device_id", "site", "firmware",
        F.col("r.recorded_at_ms").alias("recorded_at_ms"),
        F.col("r.temperature_c").cast("double").alias("temperature_c"),
        F.col("r.humidity_pct").cast("double").alias("humidity_pct"),
        F.col("r.battery_pct").cast("double").alias("battery_pct"),
    ))

print("readings before dedup:", exploded.count())

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Epoch milliseconds to a real timestamp
# MAGIC
# MAGIC `recorded_at_ms` is a bigint. Casting it straight to `TIMESTAMP` treats it as
# MAGIC *seconds* and lands you in the year 58000 — wrong, but not an error, which is
# MAGIC the dangerous kind of wrong. Divide by 1000 first.

# COMMAND ----------

typed = exploded.withColumn(
    "recorded_at", (F.col("recorded_at_ms") / 1000).cast("timestamp")
).drop("recorded_at_ms")

display(typed.select("event_id", "recorded_at").orderBy("event_id").limit(3))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Deduplicate on the business key
# MAGIC
# MAGIC The third batch replays some of the second batch's readings. `event_id` is the
# MAGIC business key, so keep one row per id. The replays are byte-identical here, so
# MAGIC any deterministic choice works; when they are not, you would order by an
# MAGIC ingestion timestamp and keep the newest.

# COMMAND ----------

deduped = typed.dropDuplicates(["event_id"])
print("readings after dedup:", deduped.count())

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Write to the contracted schema, in the contracted column order

# COMMAND ----------

final = deduped.select(
    "event_id", "device_id", "site", "firmware",
    "recorded_at", "temperature_c", "humidity_pct", "battery_pct",
)

final.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(TARGET)
print(f"wrote {spark.table(TARGET).count()} rows to {TARGET}")
spark.table(TARGET).printSchema()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Emit the fixtures the tests assert against
# MAGIC
# MAGIC Committed to `solutions/ASSOC-S2/expected.json`, so the suite can check
# MAGIC known answers without this notebook existing.

# COMMAND ----------

import json

t = spark.table(TARGET)
probe_ids = ["EVT-0000001", "EVT-0000050", "EVT-0000137"]
probes = {
    r["event_id"]: {
        "temperature_c": r["temperature_c"],
        "humidity_pct": r["humidity_pct"],
        "recorded_at": r["recorded_at"].isoformat(),
        "device_id": r["device_id"],
    }
    for r in t.filter(F.col("event_id").isin(probe_ids)).collect()
}

fixtures = {
    "row_count": t.count(),
    "distinct_event_ids": t.select("event_id").distinct().count(),
    "rows_with_battery": t.filter(F.col("battery_pct").isNotNull()).count(),
    "distinct_devices": t.select("device_id").distinct().count(),
    "min_recorded_at": t.agg(F.min("recorded_at")).collect()[0][0].isoformat(),
    "max_recorded_at": t.agg(F.max("recorded_at")).collect()[0][0].isoformat(),
    "probes": probes,
}
print(json.dumps(fixtures, indent=2))
