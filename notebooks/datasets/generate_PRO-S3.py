# Databricks notebook source
# MAGIC %md
# MAGIC # PRO-S3 — generate the `teach` and `assess` datasets
# MAGIC
# MAGIC Advanced transformation and quality: window functions and quarantining.
# MAGIC
# MAGIC ## What makes the assignment un-copyable
# MAGIC
# MAGIC 1. **The teach data is invalid in one obvious way** — a malformed value that will
# MAGIC    not cast. Filter it out and quarantine it.
# MAGIC 2. **The assess data is mostly *individually* valid.** Every row casts cleanly.
# MAGIC    What is wrong only exists **between** rows:
# MAGIC    - a reading that is impossible given the one before it (a meter running backwards)
# MAGIC    - a gap where readings stop for a period and resume
# MAGIC    - a duplicate reading at the same timestamp with a different value
# MAGIC 3. **So a row-at-a-time validator finds nothing.** Detecting any of it requires a
# MAGIC    window over the ordered sequence per device.

# COMMAND ----------

import random
from datetime import datetime, timedelta

CATALOG, SCHEMA = "workspace", "de_prep"
SEED = 20260904
spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## `teach` — one row-level defect

# COMMAND ----------

rng = random.Random(SEED)
base = datetime(2026, 3, 1)
rows = []
for i in range(1, 301):
    rows.append((f"R-{i:05d}", f"dev-{rng.randint(1,5):02d}",
                 str(round(rng.uniform(10, 90), 2)),
                 (base + timedelta(minutes=15 * i)).isoformat()))
rows.append(("R-00301", "dev-01", "n/a", (base + timedelta(minutes=15 * 301)).isoformat()))

spark.createDataFrame(
    rows, "reading_id STRING, device_id STRING, value STRING, read_at STRING"
).write.mode("overwrite").saveAsTable("pro_s3_teach_readings")
print("teach rows:", spark.table("pro_s3_teach_readings").count(), "(one will not cast)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## `assess` — every row valid on its own
# MAGIC
# MAGIC A cumulative meter per device. Individually each reading is a plausible number;
# MAGIC the defects only exist relative to neighbours.

# COMMAND ----------

rng = random.Random(SEED + 37)
DEVICES = [f"meter-{i:02d}" for i in range(1, 9)]
rows = []
rid = 0

expected_backwards = 0
expected_gaps = 0
expected_dupes = 0

for dev in DEVICES:
    total = round(rng.uniform(100, 500), 2)
    ts = base
    n = 90
    # One device gets a backwards reading, one gets a gap, one gets a duplicate.
    backwards_at = 40 if dev in DEVICES[:3] else None
    gap_at = 55 if dev in DEVICES[2:5] else None
    dupe_at = 70 if dev in DEVICES[4:6] else None

    for k in range(n):
        ts = ts + timedelta(minutes=15)

        if gap_at is not None and gap_at <= k < gap_at + 6:
            continue                                    # readings simply stop

        total += round(rng.uniform(0.5, 4.0), 2)        # a meter only goes up

        if backwards_at is not None and k == backwards_at:
            total = round(total * 0.6, 2)               # impossible: it went down
            expected_backwards += 1

        rid += 1
        rows.append((f"M-{rid:06d}", dev, round(total, 2), ts))

        if dupe_at is not None and k == dupe_at:
            rid += 1
            rows.append((f"M-{rid:06d}", dev, round(total + 7.5, 2), ts))  # same ts, different value
            expected_dupes += 1

    if gap_at is not None:
        expected_gaps += 1

spark.createDataFrame(
    rows, "reading_id STRING, device_id STRING, meter_total DOUBLE, read_at TIMESTAMP"
).write.mode("overwrite").saveAsTable("pro_s3_assess_meter_readings")

print("assess rows:", spark.table("pro_s3_assess_meter_readings").count())
print(f"expected: {expected_backwards} backwards, {expected_gaps} gaps, {expected_dupes} duplicates")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Prove the defects are invisible row-by-row

# COMMAND ----------

from pyspark.sql import functions as F
from pyspark.sql.window import Window

t = spark.table("pro_s3_assess_meter_readings")

# A row-at-a-time validator: does every value parse and look sane on its own?
row_level_bad = t.filter(
    F.col("meter_total").isNull() | (F.col("meter_total") < 0) | F.col("read_at").isNull()
).count()
print(f"rows failing any row-level check: {row_level_bad}")

w = Window.partitionBy("device_id").orderBy("read_at")
withprev = t.withColumn("prev", F.lag("meter_total").over(w))
backwards = withprev.filter(F.col("meter_total") < F.col("prev")).count()

dupes = (t.groupBy("device_id", "read_at").count().filter("count > 1").count())

gaps = (t.withColumn("prev_ts", F.lag("read_at").over(w))
        .withColumn("gap_min", (F.col("read_at").cast("long") - F.col("prev_ts").cast("long")) / 60)
        .filter("gap_min > 15").count())

print(f"backwards readings (needs a window): {backwards}")
print(f"duplicate timestamps               : {dupes}")
print(f"gaps in the sequence               : {gaps}")

assert row_level_bad == 0, "a row-level check finds defects; the trap is missing"
assert backwards > 0 and dupes > 0 and gaps > 0, "not all three sequence defects present"
print("\nevery row is individually valid; all defects are between rows")
