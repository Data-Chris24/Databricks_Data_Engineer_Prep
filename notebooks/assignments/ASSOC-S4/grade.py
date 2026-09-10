# Databricks notebook source
# MAGIC %md
# MAGIC # Grade the ASSOC-S4 assignment
# MAGIC
# MAGIC > Runs pytest **in-process** (a subprocess cannot reach the serverless Spark
# MAGIC > session) from a **local-disk copy** (the Workspace filesystem refuses the
# MAGIC > `__pycache__` writes assertion rewriting needs, `OSError 95`).

# COMMAND ----------

# MAGIC %pip install pytest -q
# MAGIC %restart_python

# COMMAND ----------

import os, shutil, tempfile

ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
assignment_dir = "/Workspace" + os.path.dirname(ctx.notebookPath().get())
repo_root = assignment_dir.split("/files/")[0] + "/files"

workdir = tempfile.mkdtemp(prefix="grade_assoc_s4_")
shutil.copytree(os.path.join(assignment_dir, "tests"), os.path.join(workdir, "tests"))
fixtures = os.path.join(workdir, "expected.json")
shutil.copyfile(os.path.join(repo_root, "solutions", "ASSOC-S4", "expected.json"), fixtures)
os.environ["ASSOC_S4_FIXTURES"] = fixtures
tests_dir = os.path.join(workdir, "tests")
print("running from:", tests_dir)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Idempotence check
# MAGIC
# MAGIC Requirement 4: the published row count must not move when the pipeline is run
# MAGIC again. This records the count now; the suite asserts the expected value, so a
# MAGIC doubled table fails regardless of which run produced it.

# COMMAND ----------

from pyspark.sql import SparkSession
_spark = SparkSession.builder.getOrCreate()
try:
    before = _spark.table("workspace.de_prep.s4_gold_regional_orders").count()
    print(f"published rows at grading time: {before}")
except Exception as e:
    print(f"published table not found: {e}")

# COMMAND ----------

import io, contextlib
import pytest

buf = io.StringIO()
with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
    exit_code = pytest.main([tests_dir, "-v", "--tb=short", "-p", "no:cacheprovider"])
report = buf.getvalue()
print(report)
print(f"\npytest exit code: {exit_code}")

dbutils.fs.mkdirs("/Volumes/workspace/de_prep/raw/_grading")
dbutils.fs.put("/Volumes/workspace/de_prep/raw/_grading/ASSOC-S4-report.txt",
               report[-30000:] + f"\n\nexit={exit_code}\n", overwrite=True)

# COMMAND ----------

if exit_code != 0:
    raise RuntimeError(
        f"Assignment not yet passing (pytest exit {exit_code}). "
        "Read the failures above - each says what the checker expected and why."
    )
print("PASS - all graded checks satisfied.")
