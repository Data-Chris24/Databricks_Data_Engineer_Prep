# Databricks notebook source
# MAGIC %md
# MAGIC # Anti-transplant check — ASSOC-S1
# MAGIC
# MAGIC Applies the **lesson's** approach — query the current version of the table — and
# MAGIC asserts the graded suite FAILS.
# MAGIC
# MAGIC The teach table's history is clean, so reading the latest version is always
# MAGIC correct there and the lesson never needs time travel to answer anything. Here the
# MAGIC latest version *is* the damage.

# COMMAND ----------

from pyspark.sql import functions as F

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")
REC, REP = "s1_recovered_catalog", "s1_incident_report"

for t in (REC, REP):
    if spark.catalog.tableExists(t):
        spark.sql(f"CREATE OR REPLACE TABLE {t}_backup AS SELECT * FROM {t}")
print("backed up the correct outputs")

# COMMAND ----------

# MAGIC %md
# MAGIC ## The lesson's approach, verbatim
# MAGIC
# MAGIC Read the table. No history, no version profiling - because the teach table never
# MAGIC required any.

# COMMAND ----------

cur = spark.table("s1_assess_catalog")
cur.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(REC)
print(f"lesson-style recovery produced {spark.table(REC).count()} rows (should be 420)")

# A report built from the current state cannot know what was lost.
spark.createDataFrame([(
    0, 0, 0, 0.0, "no damage detected in the current version of the table",
)], "bad_version INT, good_version INT, rows_lost INT, value_lost DOUBLE, detail STRING") \
 .write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(REP)
print("report claims nothing was lost, because the current version is all it looked at")

# COMMAND ----------

# MAGIC %pip install pytest -q
# MAGIC %restart_python

# COMMAND ----------

import io, contextlib, os, shutil, tempfile
import pytest

ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
repo_root = ("/Workspace" + os.path.dirname(ctx.notebookPath().get())).split("/files/")[0] + "/files"
workdir = tempfile.mkdtemp(prefix="transplant_s1_")
shutil.copytree(os.path.join(repo_root, "notebooks", "assignments", "ASSOC-S1", "tests"),
                os.path.join(workdir, "tests"))
fx = os.path.join(workdir, "expected.json")
shutil.copyfile(os.path.join(repo_root, "solutions", "ASSOC-S1", "expected.json"), fx)
os.environ["ASSOC_S1_FIXTURES"] = fx

buf = io.StringIO()
with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
    code = pytest.main([os.path.join(workdir, "tests"), "-q", "--tb=line",
                        "-p", "no:cacheprovider"])
print(buf.getvalue()[-2500:])

# COMMAND ----------

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")
for t in ("s1_recovered_catalog", "s1_incident_report"):
    if spark.catalog.tableExists(f"{t}_backup"):
        spark.sql(f"CREATE OR REPLACE TABLE {t} AS SELECT * FROM {t}_backup")
        spark.sql(f"DROP TABLE {t}_backup")
print("restored the correct outputs")

if code == 0:
    raise RuntimeError(
        "DESIGN REGRESSION: reading the current version PASSED the assignment. "
        "Redesign the pairing before shipping this section."
    )
print(f"anti-transplant property holds - the lesson's approach fails (pytest exit {code})")
