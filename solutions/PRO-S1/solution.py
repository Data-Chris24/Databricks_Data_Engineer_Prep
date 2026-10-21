# Databricks notebook source
# MAGIC %md
# MAGIC # PRO-S1 assignment — reference solution
# MAGIC
# MAGIC Reduce a change feed to current state, applying by hand what `AUTO CDC` does for
# MAGIC you: sequence, delete, and ignore late events.

# COMMAND ----------

from pyspark.sql import functions as F
from pyspark.sql.window import Window

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")
SRC = "pro_s1_assess_changes"
TARGET = "pro_s1_current_customers"

changes = spark.table(SRC)
print("events:", changes.count(), " distinct keys:", changes.select("customer_id").distinct().count())

# COMMAND ----------

# MAGIC %md
# MAGIC ## The trap: order of arrival is not order of events
# MAGIC
# MAGIC The feed is shuffled, so "the last row for this key" is meaningless. Only
# MAGIC `seq_num` says which event happened last.

# COMMAND ----------

naive = changes.dropDuplicates(["customer_id"]).count()
print(f"naive dedup on key: {naive} rows - keeps an arbitrary event, tombstones included")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Sequence: take the highest `seq_num` per key
# MAGIC
# MAGIC This is `SEQUENCE BY`. A late-arriving event with a lower sequence loses, which
# MAGIC is what makes the result independent of arrival order.

# COMMAND ----------

w = Window.partitionBy("customer_id").orderBy(F.desc("seq_num"))
latest = (changes
    .withColumn("rn", F.row_number().over(w))
    .filter("rn = 1")
    .drop("rn"))

print("one event per key:", latest.count())
display(latest.groupBy("op").count().orderBy("op"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Deletes: a tombstone removes the key
# MAGIC
# MAGIC This is `APPLY AS DELETE WHEN`. A key whose latest event is a delete must be
# MAGIC **absent** from the result, not present with a flag — and a key that was deleted
# MAGIC and later updated is present again, because its highest sequence is the update.

# COMMAND ----------

current = latest.filter(F.col("op") != "delete")
print("surviving keys:", current.count())

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Publish current state

# COMMAND ----------

final = current.select(
    "customer_id", "tier", "balance",
    F.col("seq_num").alias("last_seq"),
    F.col("event_ts").alias("last_event_ts"),
)
final.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(TARGET)
print(f"wrote {spark.table(TARGET).count()} rows")
spark.table(TARGET).printSchema()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Fixtures

# COMMAND ----------

import json
t = spark.table(TARGET)
tombstoned = latest.filter("op = 'delete'").count()

probes = {}
for r in t.orderBy("customer_id").limit(3).collect():
    probes[r["customer_id"]] = {"tier": r["tier"], "balance": r["balance"],
                                "last_seq": r["last_seq"]}

print(json.dumps({
    "total_events": changes.count(),
    "distinct_keys": changes.select("customer_id").distinct().count(),
    "surviving_rows": t.count(),
    "tombstoned_keys": tombstoned,
    "naive_dedup_rows": naive,
    "max_seq": int(t.agg(F.max("last_seq")).collect()[0][0]),
    "probes": probes,
}, indent=2))
