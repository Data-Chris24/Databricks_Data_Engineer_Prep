# Databricks notebook source
# MAGIC %md
# MAGIC # Anti-transplant check — PRO-S10
# MAGIC
# MAGIC Applies the **lesson's** natural-key join to the Type 2 dimension and asserts the
# MAGIC graded suite FAILS.
# MAGIC
# MAGIC The lesson joined `fact.customer_id = dim.customer_id`, which was correct there:
# MAGIC that dimension had one row per customer. Transplanted here it still runs, still
# MAGIC returns 900 rows, and still produces a revenue breakdown — a wrong one.

# COMMAND ----------

# MAGIC %pip install pytest -q
# MAGIC %restart_python

# COMMAND ----------

from pyspark.sql import functions as F

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")
DIM, FACT = "pro_s10_dim_customer", "pro_s10_fact_orders"

for t in (DIM, FACT):
    if spark.catalog.tableExists(t):
        spark.sql(f"CREATE OR REPLACE TABLE {t}_backup AS SELECT * FROM {t}")
print("backed up the correct model")

# COMMAND ----------

# MAGIC %md
# MAGIC ## The lesson's approach, verbatim
# MAGIC
# MAGIC One row per customer, joined on the natural key. Both steps are the lesson's.

# COMMAND ----------

versions = spark.table("pro_s10_assess_customer_versions")
orders = spark.table("pro_s10_assess_orders")

# the lesson's dimension: one row per customer
dim = (versions.filter("is_current")
       .withColumn("customer_sk", F.sha2(F.concat_ws("|", F.col("customer_id"),
                                                     F.col("valid_from")), 256))
       .select("customer_sk", "customer_id", "segment", "region",
               "valid_from", "valid_to", "is_current"))
dim.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(DIM)

# the lesson's join: natural key, no validity window
fact = (orders.alias("o").join(dim.alias("d"), on="customer_id", how="left")
        .select(F.col("o.order_id"), F.col("d.customer_sk"), F.col("o.customer_id"),
                F.col("d.segment").alias("segment_at_order"),
                F.col("d.region").alias("region_at_order"),
                F.col("o.amount"), F.col("o.ordered_on")))
fact.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(FACT)

print("rows out:", spark.table(FACT).count(), "- the grain survived, so nothing looks wrong")
display(spark.table(FACT).groupBy("segment_at_order")
        .agg(F.round(F.sum("amount"), 2).alias("revenue")).orderBy("segment_at_order"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Now run the graded suite against it

# COMMAND ----------

import contextlib, io, os, shutil, tempfile
import pytest

ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
repo_root = ("/Workspace" + os.path.dirname(ctx.notebookPath().get())).split("/files/")[0] + "/files"

workdir = tempfile.mkdtemp(prefix="transplant_pro_s10_")
shutil.copytree(os.path.join(repo_root, "grading", "PRO-S10", "tests"),
                os.path.join(workdir, "tests"))
fixtures = os.path.join(workdir, "expected.json")
shutil.copyfile(os.path.join(repo_root, "grading", "PRO-S10", "expected.json"), fixtures)
os.environ["PRO_S10_FIXTURES"] = fixtures

buf = io.StringIO()
with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
    exit_code = pytest.main([os.path.join(workdir, "tests"), "-v", "--tb=line",
                             "-p", "no:cacheprovider"])
report = buf.getvalue()
print(report)

# COMMAND ----------

# restore before asserting, so a failure here never leaves the wrong model behind
for t in (DIM, FACT):
    if spark.catalog.tableExists(f"{t}_backup"):
        spark.sql(f"CREATE OR REPLACE TABLE {t} AS SELECT * FROM {t}_backup")
        spark.sql(f"DROP TABLE {t}_backup")
print("restored the correct model")

assert exit_code != 0, (
    "The transplanted lesson code PASSED the graded suite. The dataset pairing is not "
    "doing its job and PRO-S10 needs redesigning."
)
print(f"\nAnti-transplant property holds: the lesson's natural-key join fails the "
      f"suite (pytest exit {exit_code}).")
