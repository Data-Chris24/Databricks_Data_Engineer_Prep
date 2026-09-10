# Databricks notebook source
# MAGIC %md
# MAGIC # Anti-transplant check — PRO-S9
# MAGIC
# MAGIC Applies the **lesson's** approach - look for the error, list the bad rows - and
# MAGIC asserts the graded suite FAILS.
# MAGIC
# MAGIC There is no error here, so the lesson's method has nothing to find. It reports
# MAGIC "no failure detected", which is exactly the wrong answer and exactly what a green
# MAGIC run invites you to conclude.

# COMMAND ----------

from pyspark.sql import functions as F

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")
T = "pro_s9_incident_report"

if spark.catalog.tableExists(T):
    spark.sql(f"CREATE OR REPLACE TABLE {T}_backup AS SELECT * FROM {T}")
    print("backed up the correct report")

# COMMAND ----------

# MAGIC %md
# MAGIC ## The lesson's approach, verbatim

# COMMAND ----------

src = spark.table("pro_s9_assess_daily")

# Step 1: look for failures in the history. There are none.
ops = [r["operation"] for r in spark.sql("DESCRIBE HISTORY pro_s9_assess_daily").collect()]
failures = [o for o in ops if "FAIL" in o.upper()]
print("failed operations in history:", failures or "none")

# Step 2: look for rows that will not cast. There are none.
bad = src.filter("try_cast(amount AS DOUBLE) IS NULL").count()
print("rows that will not cast:", bad)

# Conclusion the lesson's method reaches.
lesson_only = spark.createDataFrame([(
    "", "", 0, 0,
    "no errors found in run history and no malformed rows; pipeline appears healthy",
)], "first_bad_date STRING, missing_source STRING, degraded_days INT, rows_lost INT, detail STRING")

lesson_only.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(T)
print("\nlesson-style diagnosis: 'pipeline appears healthy' - which is wrong")

# COMMAND ----------

# MAGIC %pip install pytest -q
# MAGIC %restart_python

# COMMAND ----------

import io, contextlib, os, shutil, tempfile
import pytest

ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
repo_root = ("/Workspace" + os.path.dirname(ctx.notebookPath().get())).split("/files/")[0] + "/files"
workdir = tempfile.mkdtemp(prefix="transplant_pro_s9_")
shutil.copytree(os.path.join(repo_root, "grading", "PRO-S9", "tests"),
                os.path.join(workdir, "tests"))
fx = os.path.join(workdir, "expected.json")
shutil.copyfile(os.path.join(repo_root, "grading", "PRO-S9", "expected.json"), fx)
os.environ["PRO_S9_FIXTURES"] = fx

buf = io.StringIO()
with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
    code = pytest.main([os.path.join(workdir, "tests"), "-q", "--tb=line",
                        "-p", "no:cacheprovider"])
print(buf.getvalue()[-2500:])

# COMMAND ----------

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")
T = "pro_s9_incident_report"
if spark.catalog.tableExists(f"{T}_backup"):
    spark.sql(f"CREATE OR REPLACE TABLE {T} AS SELECT * FROM {T}_backup")
    spark.sql(f"DROP TABLE {T}_backup")
    print("restored the correct report")

if code == 0:
    raise RuntimeError(
        "DESIGN REGRESSION: 'no failure detected' PASSED the assignment. Redesign the "
        "pairing before shipping this section."
    )
print(f"anti-transplant property holds - the lesson's approach fails (pytest exit {code})")
