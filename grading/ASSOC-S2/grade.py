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

import io, contextlib, json
import pytest


class _Collect:
    """Per-test outcomes, so the result can be returned as data and not only as text."""

    def __init__(self):
        self.results = []

    def pytest_runtest_logreport(self, report):
        if report.when == "call" or (report.when == "setup" and report.outcome != "passed"):
            message = str(report.longrepr)[-600:] if report.failed else ""
            self.results.append({
                "test": report.nodeid.split("::")[-1],
                "outcome": report.outcome,
                "message": message,
            })


collector = _Collect()
buf = io.StringIO()
with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
    exit_code = pytest.main([tests_dir, "-v", "--tb=short", "-p", "no:cacheprovider"], plugins=[collector])
report = buf.getvalue()
print(report)
print(f"\npytest exit code: {exit_code}")

# COMMAND ----------

# The study app triggers this job and reads the value below from the run's
# output, so the grade comes back inside the app. Run by hand, the report above
# says the same thing in prose.
result = {
    "section": "ASSOC-S2",
    "passed": exit_code == 0,
    "total": len(collector.results),
    "failed": [r for r in collector.results if r["outcome"] != "passed"],
    "tests": [{"test": r["test"], "outcome": r["outcome"]} for r in collector.results],
    "report_tail": report[-4000:],
}
if result["passed"]:
    print("PASS - all graded checks satisfied.")
else:
    print(f"Assignment not yet passing: {len(result['failed'])} of {result['total']} checks failed. "
          "Each failure above says what the checker expected and why.")
dbutils.notebook.exit(json.dumps(result))
