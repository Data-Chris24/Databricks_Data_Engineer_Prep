# Databricks notebook source
# MAGIC %md
# MAGIC # Window functions and quarantining — `PRO-S3-O1`, `PRO-S3-O2`
# MAGIC
# MAGIC Teach data: `pro_s3_teach_readings`, where one value will not cast.

# COMMAND ----------

from pyspark.sql import functions as F
from pyspark.sql.window import Window

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")
raw = spark.table("pro_s3_teach_readings")
print("rows:", raw.count())

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Quarantine rather than filter
# MAGIC
# MAGIC Filtering bad rows away loses the evidence. Quarantining keeps it somewhere a
# MAGIC human can look, and lets the good data flow on — neither blocks the other.

# COMMAND ----------

typed = (raw
    .withColumn("value_num", F.expr("try_cast(value AS DOUBLE)"))
    .withColumn("read_ts", F.expr("try_cast(read_at AS TIMESTAMP)")))

good = typed.filter("value_num IS NOT NULL AND read_ts IS NOT NULL")
bad = typed.filter("value_num IS NULL OR read_ts IS NULL")

print(f"good: {good.count()}   quarantined: {bad.count()}")
display(bad.select("reading_id", "device_id", "value", "read_at"))

# COMMAND ----------

# MAGIC %md
# MAGIC The quarantine keeps the **raw** values, not the coerced ones. A quarantine row
# MAGIC that has already been through the transformation you are debugging is not
# MAGIC evidence.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Window functions
# MAGIC
# MAGIC A window computes across rows **without collapsing them**, which is what
# MAGIC separates it from a `groupBy`.

# COMMAND ----------

w = Window.partitionBy("device_id").orderBy("read_ts")

analysed = (good
    .withColumn("prev_value", F.lag("value_num").over(w))
    .withColumn("delta", F.round(F.col("value_num") - F.col("prev_value"), 2))
    .withColumn("running_avg", F.round(F.avg("value_num").over(w.rowsBetween(-4, 0)), 2))
    .withColumn("seq", F.row_number().over(w)))

display(analysed.select("device_id", "read_ts", "value_num", "prev_value",
                        "delta", "running_avg", "seq")
        .orderBy("device_id", "read_ts").limit(8))

# COMMAND ----------

# MAGIC %md
# MAGIC | Function | Gives you |
# MAGIC |---|---|
# MAGIC | `lag` / `lead` | the neighbouring row's value |
# MAGIC | `row_number` | position in the ordered partition |
# MAGIC | `rank` / `dense_rank` | position with ties handled differently |
# MAGIC | aggregate `over` a frame | a rolling calculation |
# MAGIC
# MAGIC ### Frames
# MAGIC
# MAGIC `rowsBetween` counts **rows**; `rangeBetween` counts **values of the ordering
# MAGIC column**. On an irregular time series those differ sharply — five rows back is
# MAGIC not the same as five minutes back, and choosing the wrong one is a quiet bug.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Expectations as a quality gate
# MAGIC
# MAGIC In a declarative pipeline these are `EXPECT` clauses. By hand, the same idea:
# MAGIC name the rule, count the violations, decide what to do about them.

# COMMAND ----------

rules = {
    "value_present": F.col("value_num").isNotNull(),
    "value_in_range": F.col("value_num").between(0, 200),
    "timestamp_present": F.col("read_ts").isNotNull(),
}
for name, rule in rules.items():
    violations = good.filter(~rule).count()
    print(f"{name:20} violations: {violations}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## What to carry forward
# MAGIC
# MAGIC - Quarantine, do not filter, and keep the raw values.
# MAGIC - Windows compute across rows without collapsing them.
# MAGIC - `rowsBetween` and `rangeBetween` are not interchangeable.
# MAGIC
# MAGIC **Every rule above is a row-level rule.** The assignment's data passes all of
# MAGIC them: every row is individually valid, and everything wrong with it exists only
# MAGIC between rows.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Next
# MAGIC
# MAGIC When the lessons are done, open the graded assignment: [PRO-S3 assignment notebook](../../../assignments/PRO-S3/assignment) · [the task](../../../assignments/PRO-S3/README.md).
