# Databricks notebook source
# MAGIC %md
# MAGIC # PRO-S2 · Reading the formats the exam names
# MAGIC
# MAGIC **Objective:** `PRO-S2-O1`
# MAGIC
# MAGIC Delta, Parquet, ORC, Avro, JSON, CSV, XML, text and binary. The useful way to
# MAGIC hold them in your head is not a list but a question:
# MAGIC
# MAGIC > **Does the file tell you its own schema?**
# MAGIC
# MAGIC Everything else — cost, safety, which options you must supply — follows from the
# MAGIC answer.

# COMMAND ----------

from pyspark.sql import functions as F
from pyspark.sql.types import (
    DoubleType, IntegerType, StringType, StructField, StructType, TimestampType,
)

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")
ROOT = "/Volumes/workspace/de_prep/raw/pro_s2/teach"
SCRATCH = "/Volumes/workspace/de_prep/raw/pro_s2/_lesson"
dbutils.fs.rm(SCRATCH, True)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Self-describing: Parquet, ORC, Avro, Delta
# MAGIC
# MAGIC These carry their schema in the file. You supply a path and nothing else, and the
# MAGIC types you get back are the types that were written.

# COMMAND ----------

p = spark.read.parquet(f"{ROOT}/parquet")
print("parquet:", p.count(), "rows")
p.printSchema()

# COMMAND ----------

# MAGIC %md
# MAGIC The other three read the same way. Write the Parquet batch out as each so we can
# MAGIC read it back — and note that `format(...)` plus `save(...)` is the general form;
# MAGIC `.parquet(...)` and friends are shorthand.

# COMMAND ----------

for fmt in ("orc", "avro", "delta"):
    p.write.format(fmt).mode("overwrite").save(f"{SCRATCH}/{fmt}")
    df = spark.read.format(fmt).load(f"{SCRATCH}/{fmt}")
    same = df.schema == p.schema
    print(f"{fmt:8} {df.count():>4} rows   schema round-tripped: {same}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### What separates them
# MAGIC
# MAGIC | | Layout | Good at | Watch out for |
# MAGIC |---|---|---|---|
# MAGIC | **Parquet** | columnar | analytics: reads only the columns you ask for, and skips row groups by statistics | no transaction log — a partial write is a partial read |
# MAGIC | **ORC** | columnar | the same, from the Hive world | rarely the right choice on Databricks unless you were handed it |
# MAGIC | **Avro** | row-oriented | whole-record reads, streaming, and schema evolution carried in the file | column pruning buys you nothing |
# MAGIC | **Delta** | Parquet **plus a transaction log** | everything above, and ACID, time travel and concurrent writers | it is a directory, not a file |
# MAGIC
# MAGIC Delta is Parquet with a `_delta_log`. That log is what turns a pile of files into a
# MAGIC table — which is why every landing zone in this repo ends in Delta even when it
# MAGIC started as something else.

# COMMAND ----------

display(dbutils.fs.ls(f"{SCRATCH}/delta"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Self-describing about *structure*, not types: JSON and XML
# MAGIC
# MAGIC JSON tells you the field names. It does not tell you the types — Spark infers
# MAGIC them, which means **reading the data twice**: once to work out the schema, once to
# MAGIC load it.

# COMMAND ----------

j = spark.read.json(f"{ROOT}/json")
j.printSchema()
print(j.count(), "rows")
print()
print("Notice scanned_at: it came back as STRING. JSON has no timestamp type, so an")
print("ISO string stays a string until you say otherwise.")

# COMMAND ----------

# MAGIC %md
# MAGIC Supplying the schema skips the inference pass entirely. On a large landing zone
# MAGIC this is the difference between one scan and two.

# COMMAND ----------

SCHEMA = StructType([
    StructField("scan_id", StringType()),
    StructField("facility", StringType()),
    StructField("carrier", StringType()),
    StructField("status", StringType()),
    StructField("weight_kg", DoubleType()),
    StructField("scanned_at", TimestampType()),
    StructField("revision", IntegerType()),
])

typed = spark.read.schema(SCHEMA).json(f"{ROOT}/json")
typed.printSchema()
print("scanned_at is now a real timestamp, parsed on read")

# COMMAND ----------

# MAGIC %md
# MAGIC ### XML needs to be told where a record starts
# MAGIC
# MAGIC XML has no notion of "one row per line". `rowTag` is what makes it tabular, and
# MAGIC nested elements come back as **structs** you reach into with dotted paths.

# COMMAND ----------

nested = typed.select(
    "scan_id",
    F.struct("facility", "carrier").alias("location"),
    "status", "weight_kg", "scanned_at", "revision")
nested.write.format("xml").mode("overwrite") \
    .option("rowTag", "scan").option("rootTag", "scans").save(f"{SCRATCH}/xml")

x = spark.read.format("xml").option("rowTag", "scan").load(f"{SCRATCH}/xml")
x.printSchema()
display(x.select("scan_id", F.col("location.facility"), F.col("location.carrier")).limit(5))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Not self-describing at all: CSV
# MAGIC
# MAGIC A CSV is text with commas. Every column is a string until someone decides
# MAGIC otherwise, and you get three ways to decide.

# COMMAND ----------

raw = spark.read.option("header", "true").csv(f"{ROOT}/csv")
print("header only — every column is a string:")
print(" ", [f"{f.name}:{f.dataType.simpleString()}" for f in raw.schema.fields])

inferred = spark.read.option("header", "true").option("inferSchema", "true") \
                .csv(f"{ROOT}/csv")
print("\ninferSchema — Spark guesses, at the cost of an extra pass over the file:")
print(" ", [f"{f.name}:{f.dataType.simpleString()}" for f in inferred.schema.fields])

declared = spark.read.option("header", "true").schema(SCHEMA).csv(f"{ROOT}/csv")
print("\nan explicit schema — one pass, and the types are yours, not a guess:")
print(" ", [f"{f.name}:{f.dataType.simpleString()}" for f in declared.schema.fields])

# COMMAND ----------

# MAGIC %md
# MAGIC ### Dates and times are where CSV bites
# MAGIC
# MAGIC An explicit schema only parses what the built-in parser recognises. Anything else
# MAGIC needs `to_timestamp` with a pattern, or a `timestampFormat` option on the reader.

# COMMAND ----------

odd = spark.createDataFrame([("14/03/2026 09:15:00",)], "s STRING")

print("try_cast, no pattern :",
      odd.selectExpr("try_cast(s AS TIMESTAMP) AS t").collect()[0]["t"])
print("to_timestamp, pattern:",
      odd.select(F.to_timestamp("s", "dd/MM/yyyy HH:mm:ss").alias("t"))
         .collect()[0]["t"])

# COMMAND ----------

# MAGIC %md
# MAGIC ### A trap worth carrying into every job you write
# MAGIC
# MAGIC ANSI mode is on, so a cast that cannot succeed **raises**. But it only raises if
# MAGIC it actually runs — and a projection nothing consumes gets pruned first.
# MAGIC
# MAGIC So a query that returns a number without complaining is **not** evidence that your
# MAGIC casts are valid. Only materialising the values proves that.

# COMMAND ----------

# It has to come off a file for this to be visible: a small literal DataFrame gets
# the cast folded at plan time, which raises immediately.
spark.createDataFrame([("14/03/2026 09:15:00",)] * 5, "s STRING") \
     .coalesce(1).write.mode("overwrite").option("header", "true") \
     .csv(f"{SCRATCH}/oddtime")
bad = spark.read.option("header", "true").csv(f"{SCRATCH}/oddtime")

print("count() over the failing cast:",
      bad.select(F.col("s").cast("timestamp")).count(), "- no error")
try:
    bad.select(F.col("s").cast("timestamp")).collect()
    print("collect(): no error")
except Exception as e:
    print("collect():", str(e).split("SQLSTATE")[0][:120].strip())
print()
print("Same expression, same data. One of them ran it.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Text and binary: when you want the bytes
# MAGIC
# MAGIC `text` gives one `value` column per line. `binaryFile` does not parse at all — it
# MAGIC hands you the file itself, plus its metadata. That is the reader for PDFs, images,
# MAGIC audio, or a proprietary format you will decode yourself.

# COMMAND ----------

t = spark.read.text(f"{ROOT}/csv")
print("text:", t.columns, "-", t.count(), "lines (the header is one of them)")
display(t.limit(3))

# COMMAND ----------

b = spark.read.format("binaryFile").load(f"{ROOT}/json")
print("binaryFile:", b.columns)
display(b.select("path", "modificationTime", "length").limit(5))

# COMMAND ----------

# MAGIC %md
# MAGIC `binaryFile` also takes `pathGlobFilter` and `recursiveFileLookup`, which is how
# MAGIC you pick one file type out of a mixed drop zone.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Combining sources: `union` is positional
# MAGIC
# MAGIC Two DataFrames of the same width will union whatever their column names say. Line
# MAGIC them up by name unless you are certain of the order — and you are rarely certain
# MAGIC of the order when the sources are different formats from different systems.

# COMMAND ----------

a = typed.limit(3)
b2 = typed.limit(3).select("scan_id", "carrier", "facility", "status",
                           "weight_kg", "scanned_at", "revision")

print("union (positional) — carrier values land under 'facility':")
display(a.union(b2).select("scan_id", "facility", "carrier"))

# COMMAND ----------

print("unionByName — the names decide:")
display(a.unionByName(b2).select("scan_id", "facility", "carrier"))

# COMMAND ----------

# MAGIC %md
# MAGIC And when one source has a column the others lack:

# COMMAND ----------

extra = typed.limit(2).withColumn("route_code", F.lit("R42"))
try:
    a.unionByName(extra).count()
except Exception as e:
    print("unionByName strict:", str(e).split("SQLSTATE")[0][:140].strip())

merged = a.unionByName(extra, allowMissingColumns=True)
print("\nwith allowMissingColumns=True:", merged.columns)
display(merged.select("scan_id", "route_code"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Recap
# MAGIC
# MAGIC | Format | Schema in the file? | Reader needs |
# MAGIC |---|---|---|
# MAGIC | Delta | yes, plus a log | nothing |
# MAGIC | Parquet / ORC | yes | nothing |
# MAGIC | Avro | yes | nothing |
# MAGIC | JSON | names only | inference pass, or `.schema()` |
# MAGIC | XML | names only | `rowTag`, and dotted paths for nesting |
# MAGIC | CSV | nothing | `header`, and `inferSchema` or `.schema()` |
# MAGIC | text | nothing | — one `value` column |
# MAGIC | binaryFile | n/a | — you decode it |
# MAGIC
# MAGIC Supplying a schema is the default worth reaching for: it is one pass instead of
# MAGIC two, and it fails loudly when the source changes shape instead of quietly
# MAGIC changing your types underneath you.

# COMMAND ----------

dbutils.fs.rm(SCRATCH, True)
print("cleaned up")
