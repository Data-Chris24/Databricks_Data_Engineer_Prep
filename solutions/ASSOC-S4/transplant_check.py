# Databricks notebook source
# MAGIC %md
# MAGIC # Anti-transplant check — ASSOC-S4
# MAGIC
# MAGIC Applies the **lesson's** linear-chain approach to the assessment source and
# MAGIC asserts the graded suite FAILS.

# COMMAND ----------

from pyspark.sql import functions as F

CATALOG, SCHEMA = "workspace", "de_prep"
SRC = f"/Volumes/{CATALOG}/{SCHEMA}/raw/s4_assess"
spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")
PUB, QUAR = "s4_gold_regional_orders", "s4_quarantine_orders"

for t in (PUB, QUAR):
    if spark.catalog.tableExists(t):
        spark.sql(f"CREATE OR REPLACE TABLE {t}_backup AS SELECT * FROM {t}")
print("backed up the correct tables")

# COMMAND ----------

# MAGIC %md
# MAGIC ## The lesson's approach, verbatim
# MAGIC
# MAGIC Read the glob, cast, publish. The lesson did exactly this and it was correct
# MAGIC there, because every teach file was clean and there was no extra directory.

# COMMAND ----------

raw = spark.read.format("csv").option("header", "true").load(f"{SRC}/*.csv")

# The lesson cast and published everything that survived. It never quarantined,
# because the teach data had nothing to quarantine.
naive = (raw
    .withColumn("units", F.expr("try_cast(units AS INT)"))
    .withColumn("ordered_on", F.expr("try_cast(ordered_on AS DATE)"))
    .filter("units IS NOT NULL AND ordered_on IS NOT NULL")
    .select("order_id", "region", "units", "ordered_on"))

naive.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(PUB)
print(f"lesson-style pipeline published {spark.table(PUB).count()} rows (should be 389)")

# It produced no quarantine table at all - drop it to reflect that honestly.
spark.sql(f"DROP TABLE IF EXISTS {QUAR}")
print("no quarantine table, because the lesson never needed one")

# COMMAND ----------

# MAGIC %pip install pytest -q
# MAGIC %restart_python

# COMMAND ----------

import io, contextlib, os, shutil, tempfile
import pytest

ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
repo_root = ("/Workspace" + os.path.dirname(ctx.notebookPath().get())).split("/files/")[0] + "/files"
workdir = tempfile.mkdtemp(prefix="transplant_s4_")
shutil.copytree(os.path.join(repo_root, "grading", "ASSOC-S4", "tests"),
                os.path.join(workdir, "tests"))
fx = os.path.join(workdir, "expected.json")
shutil.copyfile(os.path.join(repo_root, "grading", "ASSOC-S4", "expected.json"), fx)
os.environ["ASSOC_S4_FIXTURES"] = fx

buf = io.StringIO()
with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
    code = pytest.main([os.path.join(workdir, "tests"), "-q", "--tb=line",
                        "-p", "no:cacheprovider"])
print(buf.getvalue()[-3000:])

# COMMAND ----------

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")
for t in ("s4_gold_regional_orders", "s4_quarantine_orders"):
    if spark.catalog.tableExists(f"{t}_backup"):
        spark.sql(f"CREATE OR REPLACE TABLE {t} AS SELECT * FROM {t}_backup")
        spark.sql(f"DROP TABLE {t}_backup")
print("restored the correct tables")

if code == 0:
    raise RuntimeError(
        "DESIGN REGRESSION: the lesson's own approach PASSED the assignment. Redesign "
        "the pairing before shipping this section."
    )
print(f"anti-transplant property holds - the lesson's approach fails (pytest exit {code})")
