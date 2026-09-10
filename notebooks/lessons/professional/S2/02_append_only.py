# Databricks notebook source
# MAGIC %md
# MAGIC # PRO-S2 · One append-only table, fed by batch *and* stream
# MAGIC
# MAGIC **Objective:** `PRO-S2-O2`
# MAGIC
# MAGIC Append-only is not a limitation you tolerate. It is the property that lets a batch
# MAGIC job and a stream write to the same table without coordinating, and it is what
# MAGIC makes the table readable *as* a stream downstream.
# MAGIC
# MAGIC This lesson builds one table three ways and shows what each write does to it.

# COMMAND ----------

from pyspark.sql import functions as F
from pyspark.sql.types import (
    DoubleType, IntegerType, StringType, StructField, StructType, TimestampType,
)

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")
ROOT = "/Volumes/workspace/de_prep/raw/pro_s2/teach"
CKPT = "/Volumes/workspace/de_prep/raw/pro_s2/_lesson_ckpt"
TABLE = "pro_s2_teach_scans"

dbutils.fs.rm(CKPT, True)
spark.sql(f"DROP TABLE IF EXISTS {TABLE}")

SCHEMA = StructType([
    StructField("scan_id", StringType()),
    StructField("facility", StringType()),
    StructField("carrier", StringType()),
    StructField("status", StringType()),
    StructField("weight_kg", DoubleType()),
    StructField("scanned_at", TimestampType()),
    StructField("revision", IntegerType()),
])

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. The batch half
# MAGIC
# MAGIC Two formats, lined up by name, tagged with where each record came from. That tag
# MAGIC costs one column and repays it every time something looks wrong.

# COMMAND ----------

j = (spark.read.schema(SCHEMA).json(f"{ROOT}/json")
     .withColumn("source_format", F.lit("json")))
p = (spark.read.parquet(f"{ROOT}/parquet")
     .withColumn("source_format", F.lit("parquet")))

batch = j.unionByName(p).withColumn("ingested_at", F.current_timestamp())
batch.write.mode("append").saveAsTable(TABLE)

print(spark.table(TABLE).count(), "rows after the batch load")
display(spark.table(TABLE).groupBy("source_format").count())

# COMMAND ----------

# MAGIC %md
# MAGIC ### `append` vs `overwrite`, in the log
# MAGIC
# MAGIC The distinction is not stylistic. `DESCRIBE HISTORY` records the operation, and an
# MAGIC append is the one a downstream stream can follow.

# COMMAND ----------

display(spark.sql(f"DESCRIBE HISTORY {TABLE}")
        .select("version", "operation", "operationMetrics"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. The streaming half
# MAGIC
# MAGIC Auto Loader over the same volume. Two things make this work against a table the
# MAGIC batch job also writes to:
# MAGIC
# MAGIC - **`outputMode("append")`** — the stream only ever adds rows, so it never fights
# MAGIC   the batch writer over existing ones.
# MAGIC - **The checkpoint** — it records which files have been consumed, so a restart
# MAGIC   resumes rather than reprocesses. It is the stream's memory, and deleting it is
# MAGIC   how you accidentally double-load.
# MAGIC
# MAGIC `trigger(availableNow=True)` processes everything waiting and stops, which is what
# MAGIC you want in a job. Swap it for a continuous trigger and nothing else changes.

# COMMAND ----------

stream = (spark.readStream.format("cloudFiles")
          .option("cloudFiles.format", "csv")
          .option("cloudFiles.schemaLocation", f"{CKPT}/schema")
          .option("header", "true")
          .schema(SCHEMA)
          .load(f"{ROOT}/csv")
          .withColumn("source_format", F.lit("csv"))
          .withColumn("ingested_at", F.current_timestamp()))

q = (stream.writeStream
     .outputMode("append")
     .option("checkpointLocation", f"{CKPT}/scans")
     .option("mergeSchema", "true")
     .trigger(availableNow=True)
     .toTable(TABLE))
q.awaitTermination()

print(spark.table(TABLE).count(), "rows after the stream")
display(spark.table(TABLE).groupBy("source_format").count())

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Run the stream again
# MAGIC
# MAGIC Nothing new has landed, so nothing should be added. This is the checkpoint doing
# MAGIC its job — and it is the reason an append-only pipeline is safe to re-run.

# COMMAND ----------

before = spark.table(TABLE).count()
q2 = (stream.writeStream
      .outputMode("append")
      .option("checkpointLocation", f"{CKPT}/scans")
      .trigger(availableNow=True)
      .toTable(TABLE))
q2.awaitTermination()
after = spark.table(TABLE).count()
print(f"{before} rows before, {after} after - the stream added {after - before}")
assert after == before, "re-running the stream should be a no-op"

# COMMAND ----------

# MAGIC %md
# MAGIC ### And what happens if you lose the checkpoint
# MAGIC
# MAGIC A fresh checkpoint has no memory of the files already consumed, so it consumes
# MAGIC them again. Same data, twice, and no error anywhere.

# COMMAND ----------

q3 = (stream.writeStream
      .outputMode("append")
      .option("checkpointLocation", f"{CKPT}/scans_fresh")
      .trigger(availableNow=True)
      .toTable(TABLE))
q3.awaitTermination()
dupes = spark.table(TABLE).count()
print(f"{dupes} rows now - the CSV batch was loaded a second time")
print(f"distinct scan_ids: {spark.table(TABLE).select('scan_id').distinct().count()}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Idempotence is your job, not the table's
# MAGIC
# MAGIC An append-only table faithfully keeps everything it was given, duplicates
# MAGIC included. If a source can re-deliver, the pipeline needs a rule for which copy
# MAGIC wins, applied on the way to silver:
# MAGIC
# MAGIC - **the same record twice** — `dropDuplicates` on the business key
# MAGIC - **a corrected record** — a window over the key, ordered by whatever says
# MAGIC   "newer": a revision number, an emission time, or the file's arrival order
# MAGIC
# MAGIC Bronze keeps the history. Silver answers the question.

# COMMAND ----------

from pyspark.sql import Window

silver = (spark.table(TABLE)
          .withColumn("rn", F.row_number().over(
              Window.partitionBy("scan_id").orderBy(
                  F.desc("revision"), F.desc("ingested_at"))))
          .filter("rn = 1").drop("rn"))
print("bronze:", spark.table(TABLE).count(), " silver:", silver.count())

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Why append-only, specifically
# MAGIC
# MAGIC A Delta table can be read as a stream — but only if its history is append-only.
# MAGIC An update or delete produces a version the reader cannot express as new rows, and
# MAGIC it fails rather than silently skipping.

# COMMAND ----------

spark.sql(f"UPDATE {TABLE} SET status = 'delivered' WHERE status = 'in_transit'")
display(spark.sql(f"DESCRIBE HISTORY {TABLE}").select("version", "operation").limit(3))

try:
    (spark.readStream.table(TABLE)
     .writeStream.trigger(availableNow=True)
     .option("checkpointLocation", f"{CKPT}/downstream")
     .toTable("pro_s2_teach_downstream")).awaitTermination()
    print("the downstream stream accepted the update")
except Exception as e:
    print("the downstream stream refused it:")
    print(" ", str(e).split("SQLSTATE")[0][:260].strip())

# COMMAND ----------

# MAGIC %md
# MAGIC The error class is **`DELTA_SOURCE_TABLE_IGNORE_CHANGES`**, and it names its own
# MAGIC escape hatches: `skipChangeCommits` on the reader makes it step over such versions
# MAGIC (verified — the read then succeeds and adds nothing), and `ignoreChanges` makes it
# MAGIC re-emit the rewritten files as if they were new.
# MAGIC
# MAGIC Neither is free. `skipChangeCommits` means the downstream table never learns about
# MAGIC the update; `ignoreChanges` means it sees unchanged rows again and has to be
# MAGIC idempotent to survive it. Keeping bronze append-only means never making that
# MAGIC choice under pressure.

# COMMAND ----------

spark.sql(f"DROP TABLE IF EXISTS {TABLE}")
spark.sql("DROP TABLE IF EXISTS pro_s2_teach_downstream")
dbutils.fs.rm(CKPT, True)
print("cleaned up")
