# Databricks notebook source
# MAGIC %md
# MAGIC # PRO-S2 assignment — reference solution
# MAGIC
# MAGIC Five formats that disagree about column order, types, nesting and how many times
# MAGIC a record gets sent. Line them up **by name**, parse what CSV cannot type, and make
# MAGIC the append idempotent on the way to silver.

# COMMAND ----------

import json

from pyspark.sql import Window
from pyspark.sql import functions as F
from pyspark.sql.types import (
    DoubleType, IntegerType, StringType, StructField, StructType, TimestampType,
)

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")
ROOT = "/Volumes/workspace/de_prep/raw/pro_s2/assess"
BRONZE, SILVER = "pro_s2_scans_bronze", "pro_s2_scans"

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Read each source on its own terms
# MAGIC
# MAGIC The point of this step is that **no two of these readers are the same call**.

# COMMAND ----------

# JSON — names but no types. Declare the schema rather than infer it.
CORE = StructType([
    StructField("scan_id", StringType()),
    StructField("facility", StringType()),
    StructField("carrier", StringType()),
    StructField("status", StringType()),
    StructField("weight_kg", DoubleType()),
    StructField("scanned_at", TimestampType()),
    StructField("revision", IntegerType()),
])
j = spark.read.schema(CORE).json(f"{ROOT}/json") \
    .withColumn("source_format", F.lit("json"))

# Parquet — self-describing, but its column ORDER differs. Names, not positions.
p = spark.read.parquet(f"{ROOT}/parquet") \
    .withColumn("source_format", F.lit("parquet"))
print("parquet column order:", p.columns)

# Avro — self-describing, and carries a column nobody else has.
a = spark.read.format("avro").load(f"{ROOT}/avro") \
    .withColumn("source_format", F.lit("avro"))
print("avro extra column   :", set(a.columns) - set(j.columns))

# CSV — no types at all, and a dd/MM/yyyy timestamp the built-in parser will not take.
c = (spark.read.option("header", "true").csv(f"{ROOT}/csv")
     .select(
         "scan_id", "facility", "carrier", "status",
         F.col("weight_kg").cast("double").alias("weight_kg"),
         F.to_timestamp("scanned_at", "dd/MM/yyyy HH:mm:ss").alias("scanned_at"),
         F.col("revision").cast("int").alias("revision"))
     .withColumn("source_format", F.lit("csv")))

# XML — needs rowTag, and two fields live inside a wrapper element.
x = (spark.read.format("xml").option("rowTag", "scan").load(f"{ROOT}/xml")
     .select(
         "scan_id",
         F.col("location.facility").alias("facility"),
         F.col("location.carrier").alias("carrier"),
         "status", "weight_kg", "scanned_at", "revision")
     .withColumn("source_format", F.lit("xml")))

for name, df in [("json", j), ("parquet", p), ("avro", a), ("csv", c), ("xml", x)]:
    print(f"{name:8} {df.count():>4} records")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Combine by name, not by position
# MAGIC
# MAGIC `union` would be accepted here and would file every Parquet record's carrier under
# MAGIC `facility`. `allowMissingColumns` handles Avro's extra column by nulling it
# MAGIC elsewhere rather than refusing the whole union.

# COMMAND ----------

# The final select pins the types. Without it the table's schema is decided by
# whichever source happened to be widest - XML infers `revision` as a bigint, the
# union keeps the wider type, and the contract quietly stops being met.
bronze = (j.unionByName(p, allowMissingColumns=True)
          .unionByName(a, allowMissingColumns=True)
          .unionByName(c, allowMissingColumns=True)
          .unionByName(x, allowMissingColumns=True)
          .select("scan_id", "facility", "carrier", "status",
                  F.col("weight_kg").cast("double").alias("weight_kg"),
                  "scanned_at",
                  F.col("revision").cast("int").alias("revision"),
                  F.col("route_code").cast("string").alias("route_code"),
                  "source_format"))

bronze.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(BRONZE)
b = spark.table(BRONZE)
print(b.count(), "rows in bronze")
display(b.groupBy("source_format").count().orderBy("source_format"))

# COMMAND ----------

# The check that catches a positional union: every facility must be a facility.
bad = b.filter(~F.col("facility").isin("LEEDS", "DUBLIN", "PORTO", "MALMO", "LYON")).count()
print(f"rows whose facility is not a facility: {bad}")
assert bad == 0

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Bronze keeps everything; silver decides
# MAGIC
# MAGIC Append-only means bronze faithfully holds the re-deliveries too. The rule for
# MAGIC which copy wins belongs in silver: highest `revision` per `scan_id`.

# COMMAND ----------

silver = (b.withColumn("rn", F.row_number().over(
              Window.partitionBy("scan_id").orderBy(F.desc("revision"))))
          .filter("rn = 1").drop("rn"))

print("bronze:", b.count(), " silver:", silver.count())
silver.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(SILVER)

# COMMAND ----------

s = spark.table(SILVER)
display(s.groupBy("source_format").count().orderBy("source_format"))
display(s.groupBy("status").count().orderBy("status"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Fixtures

# COMMAND ----------

def counts(df, col):
    return {r[col]: r["n"] for r in
            df.groupBy(col).agg(F.count("*").alias("n")).collect() if r[col] is not None}

probe_ids = ["S-00151", "S-00152", "S-00153", "S-00460", "S-00545", "S-00400"]
probes = [
    {"scan_id": r["scan_id"], "facility": r["facility"], "carrier": r["carrier"],
     "status": r["status"], "revision": r["revision"],
     "source_format": r["source_format"],
     "scanned_at": r["scanned_at"].strftime("%Y-%m-%d %H:%M:%S"),
     "weight_kg": r["weight_kg"], "route_code": r["route_code"]}
    for r in s.filter(F.col("scan_id").isin(probe_ids)).orderBy("scan_id").collect()
]

fixtures = {
    "_generated_by": "solutions/PRO-S2/solution.py, run on Free Edition serverless",
    "bronze_rows": b.count(),
    "silver_rows": s.count(),
    "bronze_by_source": counts(b, "source_format"),
    "silver_by_source": counts(s, "source_format"),
    "silver_by_status": counts(s, "status"),
    "silver_by_facility": counts(s, "facility"),
    "silver_by_carrier": counts(s, "carrier"),
    "route_code_not_null": s.filter("route_code IS NOT NULL").count(),
    "silver_total_weight": round(s.agg(F.sum("weight_kg")).collect()[0][0], 2),
    "bronze_total_weight": round(b.agg(F.sum("weight_kg")).collect()[0][0], 2),
    "revision_2_rows": s.filter("revision = 2").count(),
    "scanned_at_nulls": s.filter("scanned_at IS NULL").count(),
    "probe_scans": probes,
}
print(json.dumps(fixtures, indent=2))
dbutils.fs.put("/Volumes/workspace/de_prep/raw/_pro_s2_expected.json",
               json.dumps(fixtures, indent=2), overwrite=True)
