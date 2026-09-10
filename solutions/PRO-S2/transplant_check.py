# Databricks notebook source
# MAGIC %md
# MAGIC # Anti-transplant check — PRO-S2
# MAGIC
# MAGIC Applies **lesson 02's pipeline verbatim** to the assess drop zones and asserts the
# MAGIC graded suite FAILS.
# MAGIC
# MAGIC The lesson read JSON with a declared schema, Parquet as-is, and CSV with that same
# MAGIC declared schema, lined them up with `unionByName`, and resolved duplicates by
# MAGIC `revision`. Every one of those steps was correct on the teach sources. Here the
# MAGIC same code runs, writes both tables, and is wrong in three different ways at once —
# MAGIC none of which raises.

# COMMAND ----------

# MAGIC %pip install pytest -q
# MAGIC %restart_python

# COMMAND ----------

from pyspark.sql import Window
from pyspark.sql import functions as F
from pyspark.sql.types import (
    DoubleType, IntegerType, StringType, StructField, StructType, TimestampType,
)

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")
ROOT = "/Volumes/workspace/de_prep/raw/pro_s2/assess"
BRONZE, SILVER = "pro_s2_scans_bronze", "pro_s2_scans"

for t in (BRONZE, SILVER):
    if spark.catalog.tableExists(t):
        spark.sql(f"CREATE OR REPLACE TABLE {t}_backup AS SELECT * FROM {t}")
print("backed up the correct tables")

# COMMAND ----------

# MAGIC %md
# MAGIC ## The lesson's pipeline, unchanged

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

j = (spark.read.schema(SCHEMA).json(f"{ROOT}/json")
     .withColumn("source_format", F.lit("json")))
p = (spark.read.parquet(f"{ROOT}/parquet")
     .withColumn("source_format", F.lit("parquet")))
c = (spark.read.option("header", "true").schema(SCHEMA).csv(f"{ROOT}/csv")
     .withColumn("source_format", F.lit("csv")))

bronze = (j.unionByName(p).unionByName(c)
          .withColumn("route_code", F.lit(None).cast("string"))
          .select("scan_id", "facility", "carrier", "status", "weight_kg",
                  "scanned_at", "revision", "route_code", "source_format"))
bronze.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(BRONZE)

silver = (spark.table(BRONZE).withColumn("rn", F.row_number().over(
              Window.partitionBy("scan_id").orderBy(F.desc("revision"))))
          .filter("rn = 1").drop("rn"))
silver.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(SILVER)

print("it ran, and it wrote both tables")

# COMMAND ----------

# MAGIC %md
# MAGIC ## What it actually produced

# COMMAND ----------

b = spark.table(BRONZE)
print(f"bronze rows: {b.count()}  (correct answer: 660)")
print(f"silver rows: {spark.table(SILVER).count()}  (correct answer: 600)")
print()
FACILITIES = ["LEEDS", "DUBLIN", "PORTO", "MALMO", "LYON"]
print("rows whose facility is not a facility:",
      b.filter(~F.col("facility").isin(FACILITIES)).count())
print("rows with a null scanned_at        :", b.filter("scanned_at IS NULL").count())
print("formats present                    :",
      sorted(r["source_format"] for r in
             b.select("source_format").distinct().collect()))
display(b.select("scan_id", "facility", "carrier", "status", "source_format").limit(8))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Now run the graded suite against it

# COMMAND ----------

import contextlib, io, os, shutil, tempfile
import pytest

ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
repo_root = ("/Workspace" + os.path.dirname(ctx.notebookPath().get())).split("/files/")[0] + "/files"

workdir = tempfile.mkdtemp(prefix="transplant_pro_s2_")
shutil.copytree(os.path.join(repo_root, "notebooks", "assignments", "PRO-S2", "tests"),
                os.path.join(workdir, "tests"))
fixtures = os.path.join(workdir, "expected.json")
shutil.copyfile(os.path.join(repo_root, "solutions", "PRO-S2", "expected.json"), fixtures)
os.environ["PRO_S2_FIXTURES"] = fixtures

buf = io.StringIO()
with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
    exit_code = pytest.main([os.path.join(workdir, "tests"), "-v", "--tb=line",
                             "-p", "no:cacheprovider"])
report = buf.getvalue()
print(report)
dbutils.fs.mkdirs("/Volumes/workspace/de_prep/raw/_grading")
dbutils.fs.put("/Volumes/workspace/de_prep/raw/_grading/PRO-S2-transplant.txt",
               report[-30000:] + f"\n\nexit={exit_code}\n", overwrite=True)

# COMMAND ----------

# restore before asserting, so a failure here never leaves the wrong tables behind
for t in (BRONZE, SILVER):
    if spark.catalog.tableExists(f"{t}_backup"):
        spark.sql(f"CREATE OR REPLACE TABLE {t} AS SELECT * FROM {t}_backup")
        spark.sql(f"DROP TABLE {t}_backup")
print("restored the correct tables")

assert exit_code != 0, (
    "The transplanted lesson code PASSED the graded suite. The dataset pairing is not "
    "doing its job and PRO-S2 needs redesigning."
)
print(f"\nAnti-transplant property holds: the lesson's pipeline fails the suite "
      f"(pytest exit {exit_code}).")
