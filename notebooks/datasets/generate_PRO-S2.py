# Databricks notebook source
# MAGIC %md
# MAGIC # PRO-S2 — generate the `teach` and `assess` datasets
# MAGIC
# MAGIC Multi-format ingestion into an append-only Delta pipeline. The pairing differs in
# MAGIC **whether the sources agree with each other**.
# MAGIC
# MAGIC ## What makes the assignment un-copyable
# MAGIC
# MAGIC 1. **The teach sources agree.** Three formats, same column order, same types, each
# MAGIC    record delivered once. `union` and `unionByName` are indistinguishable, and a
# MAGIC    plain append is correct.
# MAGIC 2. **The assess sources disagree.** Five formats with **shuffled column order**,
# MAGIC    a CSV that arrives all-`STRING` with a non-ISO timestamp, an Avro batch with an
# MAGIC    extra column, and XML that nests two fields inside a wrapper element.
# MAGIC 3. **`union` is positional.** The lesson's `union` still runs on the assess set,
# MAGIC    still returns the right number of rows, and silently files every Parquet
# MAGIC    record's carrier under `facility`. Nothing errors.
# MAGIC 4. **One source re-delivers.** The CSV batch repeats 60 scans already present in
# MAGIC    Parquet, as `revision = 2` with a corrected status — so an append-only pipeline
# MAGIC    has to be idempotent, which the teach set never forces.

# COMMAND ----------

import random
from datetime import datetime, timedelta

from pyspark.sql import Window
from pyspark.sql import functions as F
from pyspark.sql.types import (
    DoubleType, IntegerType, StringType, StructField, StructType, TimestampType,
)

CATALOG, SCHEMA = "workspace", "de_prep"
SEED = 20260905
ROOT = "/Volumes/workspace/de_prep/raw/pro_s2"

spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")
dbutils.fs.rm(ROOT, True)

FACILITIES = ["LEEDS", "DUBLIN", "PORTO", "MALMO", "LYON"]
CARRIERS = ["northwind", "brightline", "kestrel"]
STATUSES = ["received", "in_transit", "out_for_delivery", "delivered"]
T0 = datetime(2026, 2, 1, 6, 0, 0)

CANONICAL = StructType([
    StructField("scan_id", StringType()),
    StructField("facility", StringType()),
    StructField("carrier", StringType()),
    StructField("status", StringType()),
    StructField("weight_kg", DoubleType()),
    StructField("scanned_at", TimestampType()),
    StructField("revision", IntegerType()),
])


def scans(rng, ids):
    out = []
    for i in ids:
        out.append({
            "scan_id": f"S-{i:05d}",
            "facility": rng.choice(FACILITIES),
            "carrier": rng.choice(CARRIERS),
            "status": rng.choice(STATUSES),
            "weight_kg": round(rng.uniform(0.2, 40.0), 2),
            "scanned_at": T0 + timedelta(minutes=rng.randint(0, 60 * 24 * 20)),
            "revision": 1,
        })
    return out


def frame(rows, order=None):
    df = spark.createDataFrame(
        [tuple(r[f.name] for f in CANONICAL.fields) for r in rows], CANONICAL)
    return df.select(*order) if order else df

# COMMAND ----------

# MAGIC %md
# MAGIC ## `teach` — three formats that agree
# MAGIC
# MAGIC Same column order, compatible types, disjoint records, one delivery each.

# COMMAND ----------

rng = random.Random(SEED)
teach = scans(rng, range(1, 301))

frame(teach[0:100]).coalesce(1).write.mode("overwrite").json(f"{ROOT}/teach/json")
frame(teach[100:200]).coalesce(1).write.mode("overwrite").parquet(f"{ROOT}/teach/parquet")
(frame(teach[200:300]).coalesce(1).write.mode("overwrite")
 .option("header", "true").csv(f"{ROOT}/teach/csv"))

for f in ("json", "parquet", "csv"):
    print(f"teach/{f}:", len(dbutils.fs.ls(f"{ROOT}/teach/{f}")), "entries")

# COMMAND ----------

# MAGIC %md
# MAGIC ## `assess` — five formats that disagree

# COMMAND ----------

rng = random.Random(SEED + 1)
assess = scans(rng, range(1, 601))
by_id = {r["scan_id"]: r for r in assess}

json_rows = assess[0:150]
parquet_rows = assess[150:330]
avro_rows = assess[330:450]
csv_rows = assess[450:540]
xml_rows = assess[540:600]

# JSON: canonical.
frame(json_rows).coalesce(1).write.mode("overwrite").json(f"{ROOT}/assess/json")

# Parquet: facility and carrier swapped. Both STRING, so a positional union is
# accepted and silently wrong.
PARQUET_ORDER = ["scan_id", "carrier", "facility", "status", "weight_kg",
                 "scanned_at", "revision"]
frame(parquet_rows, PARQUET_ORDER).coalesce(1).write.mode("overwrite") \
    .parquet(f"{ROOT}/assess/parquet")

# Avro: canonical plus a column no other source has.
(frame(avro_rows)
 .withColumn("route_code", F.concat(F.lit("R"), F.lpad(
     (F.abs(F.hash("scan_id")) % 90 + 10).cast("string"), 2, "0")))
 .coalesce(1).write.mode("overwrite").format("avro").save(f"{ROOT}/assess/avro"))

# COMMAND ----------

# MAGIC %md
# MAGIC ### The CSV batch: all strings, a non-ISO timestamp, and 60 re-deliveries

# COMMAND ----------

corrections = []
for r in parquet_rows[0:60]:
    c = dict(r)
    c["revision"] = 2
    c["status"] = "delivered" if r["status"] != "delivered" else "received"
    corrections.append(c)

CSV_ORDER = ["scan_id", "status", "facility", "carrier", "weight_kg",
             "scanned_at", "revision"]
csv_df = (frame(csv_rows + corrections)
          .withColumn("scanned_at", F.date_format("scanned_at", "dd/MM/yyyy HH:mm:ss"))
          .select(*CSV_ORDER))
csv_df.coalesce(1).write.mode("overwrite").option("header", "true") \
    .csv(f"{ROOT}/assess/csv")
print(f"csv holds {csv_df.count()} records, of which {len(corrections)} are re-deliveries")

# COMMAND ----------

# MAGIC %md
# MAGIC ### The XML batch: two fields nested inside a wrapper

# COMMAND ----------

xml_df = (frame(xml_rows)
          .select("scan_id",
                  F.struct(F.col("facility"), F.col("carrier")).alias("location"),
                  "status", "weight_kg", "scanned_at", "revision"))
xml_df.coalesce(1).write.mode("overwrite").format("xml") \
    .option("rowTag", "scan").option("rootTag", "scans").save(f"{ROOT}/assess/xml")

for f in ("json", "parquet", "avro", "csv", "xml"):
    print(f"assess/{f}: written")

# COMMAND ----------

# MAGIC %md
# MAGIC ## The traps, measured
# MAGIC
# MAGIC Each is asserted, so the pairing cannot erode without this notebook failing.

# COMMAND ----------

j = spark.read.json(f"{ROOT}/assess/json")
p = spark.read.parquet(f"{ROOT}/assess/parquet")
a = spark.read.format("avro").load(f"{ROOT}/assess/avro")
c = spark.read.option("header", "true").csv(f"{ROOT}/assess/csv")
x = spark.read.format("xml").option("rowTag", "scan").load(f"{ROOT}/assess/xml")

delivered = j.count() + p.count() + a.count() + c.count() + x.count()
distinct_ids = 600
print(f"records delivered : {delivered}")
print(f"distinct scan_ids : {distinct_ids}")
assert delivered == 660, delivered
assert delivered > distinct_ids, "no re-deliveries - an append needs no idempotence"

# COMMAND ----------

# Trap 1: union is positional, and here that silently swaps two columns.
naive = j.select(*[f.name for f in CANONICAL.fields]).union(
    p.select(*PARQUET_ORDER))
swapped = naive.filter(~F.col("facility").isin(FACILITIES)).count()
print(f"rows whose 'facility' is not a facility after a positional union: {swapped}")
assert swapped == p.count(), \
    "the positional union did not swap columns - the Parquet order must differ"
by_name = j.unionByName(p).filter(~F.col("facility").isin(FACILITIES)).count()
assert by_name == 0, "unionByName should line the columns up correctly"
print("unionByName is clean; union is not. Both run without error.")

# COMMAND ----------

# Trap 2: the CSV timestamp is dd/MM/yyyy, which needs an explicit pattern.
total = c.count()

# ANSI is on, but "it did not error" proves nothing: a projection nothing consumes
# is pruned before it runs, so the failing cast never executes.
pruned = c.select(F.col("scanned_at").cast("timestamp")).count()
print(f"count() over a cast that cannot succeed: {pruned} rows, no error")

raised = None
try:
    c.select(F.col("scanned_at").cast("timestamp")).limit(1).collect()
except Exception as e:
    raised = str(e).split("SQLSTATE")[0][:200]
print("the same cast, materialised:", raised or "did not raise")
assert raised is not None and "CAST_INVALID_INPUT" in raised, \
    f"expected ANSI cast to raise CAST_INVALID_INPUT once materialised, got: {raised}"

# try_cast tolerates it - and parses none of it.
castable = c.selectExpr("try_cast(scanned_at AS TIMESTAMP) AS t") \
            .filter("t IS NOT NULL").count()
print(f"try_cast: {castable} of {total} parsed")
assert castable == 0, "the CSV timestamp must not be parseable without a pattern"

# The right pattern parses every row.
parsed = c.select(F.to_timestamp("scanned_at", "dd/MM/yyyy HH:mm:ss").alias("t")) \
          .filter("t IS NULL").count()
print(f"to_timestamp with dd/MM/yyyy HH:mm:ss: {total - parsed} of {total} parsed")
assert parsed == 0, "to_timestamp with the right pattern should parse every row"

# COMMAND ----------

# Trap 3: keeping the wrong revision changes the answer.
allrows = (j.select(*[f.name for f in CANONICAL.fields])
           .unionByName(p)
           .unionByName(a.drop("route_code"))
           .unionByName(c.select(
               "scan_id", "facility", "carrier", "status",
               F.col("weight_kg").cast("double").alias("weight_kg"),
               F.to_timestamp("scanned_at", "dd/MM/yyyy HH:mm:ss").alias("scanned_at"),
               F.col("revision").cast("int").alias("revision")))
           .unionByName(x.select(
               "scan_id", F.col("location.facility").alias("facility"),
               F.col("location.carrier").alias("carrier"),
               "status", "weight_kg", "scanned_at", "revision")))

latest = allrows.withColumn(
    "rn", F.row_number().over(
        Window.partitionBy("scan_id").orderBy(F.desc("revision")))
).filter("rn = 1").drop("rn")
first = allrows.dropDuplicates(["scan_id"])

print("status counts, latest revision vs an arbitrary duplicate drop:")
lm = {r["status"]: r["n"] for r in latest.groupBy("status").agg(F.count("*").alias("n")).collect()}
print(" latest:", dict(sorted(lm.items())))
assert latest.count() == distinct_ids, latest.count()
assert allrows.count() == delivered
changed = latest.alias("l").join(
    allrows.filter("revision = 1").alias("o"), "scan_id").filter(
    "l.status <> o.status").count()
print(f"scans whose status differs between revision 1 and the latest: {changed}")
assert changed == 60, changed

# COMMAND ----------

# Trap 4: the extra Avro column exists nowhere else.
assert "route_code" in a.columns and "route_code" not in j.columns
print("avro carries route_code;", len(a.columns), "columns vs", len(j.columns), "elsewhere")
print("\nall traps hold")
