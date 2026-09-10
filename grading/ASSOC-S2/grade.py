# Databricks notebook source
# MAGIC %md
# MAGIC # Grade the ASSOC-S2 assignment
# MAGIC
# MAGIC Runs the authoritative test suite against `silver_sensor_readings`.
# MAGIC A failing test names what is wrong and usually why.
# MAGIC
# MAGIC > **Note for anyone extending this:** the suite runs **in-process** via
# MAGIC > `pytest.main`, not as a subprocess. A subprocess gets a fresh Python
# MAGIC > interpreter with no attachment to this notebook's serverless Spark session,
# MAGIC > so `SparkSession.builder.getOrCreate()` inside the tests would fail to find
# MAGIC > a session and pytest would exit 2 during collection.

# COMMAND ----------

# MAGIC %pip install pytest -q
# MAGIC %restart_python

# COMMAND ----------

import os
import shutil
import tempfile

# This notebook's own workspace path, so the sibling tests/ folder can be found
# regardless of where the bundle deployed it.
ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
notebook_path = ctx.notebookPath().get()
grading_dir = "/Workspace" + os.path.dirname(notebook_path)

# pytest rewrites assertions and writes the result to __pycache__, which the
# Workspace filesystem does not support (OSError 95, Operation not supported).
# So copy the suite and its fixtures to local disk and run from there. Keeping
# assertion rewriting is worth the copy - it is what turns a bare assert into a
# readable diff.
workdir = tempfile.mkdtemp(prefix="grade_assoc_s2_")
shutil.copytree(os.path.join(grading_dir, "tests"), os.path.join(workdir, "tests"))

fixtures_src = os.path.join(grading_dir, "expected.json")
fixtures_dst = os.path.join(workdir, "expected.json")
shutil.copyfile(fixtures_src, fixtures_dst)
os.environ["ASSOC_S2_FIXTURES"] = fixtures_dst

tests_dir = os.path.join(workdir, "tests")
print("running from:", tests_dir)
print("fixtures    :", fixtures_dst)

# COMMAND ----------

import io
import contextlib
import pytest

# Run in-process so the tests share this notebook's Spark session, capturing the
# report so it survives into the job run output as well as the cell output.
buf = io.StringIO()
with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
    exit_code = pytest.main([
        tests_dir,
        "-v",
        "--tb=short",
        "-p", "no:cacheprovider",
    ])

report = buf.getvalue()
print(report)
print(f"\npytest exit code: {exit_code}")

# Persist the report so it can be read back without scraping the run UI.
REPORT_PATH = "/Volumes/workspace/de_prep/raw/_grading/ASSOC-S2-report.txt"
dbutils.fs.mkdirs("/Volumes/workspace/de_prep/raw/_grading")
dbutils.fs.put(REPORT_PATH, report[-30000:] + f"\n\nexit={exit_code}\n", overwrite=True)
print("report written to", REPORT_PATH)

# COMMAND ----------

if exit_code != 0:
    raise RuntimeError(
        f"Assignment not yet passing (pytest exit {exit_code}). "
        "Read the failures above - each says what the checker expected and why."
    )
print("PASS - all graded checks satisfied.")
