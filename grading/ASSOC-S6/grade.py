# Databricks notebook source
# MAGIC %md
# MAGIC # Grade the ASSOC-S6 assignment
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
grading_dir = "/Workspace" + os.path.dirname(ctx.notebookPath().get())

workdir = tempfile.mkdtemp(prefix="grade_assoc_s6_")
shutil.copytree(os.path.join(grading_dir, "tests"), os.path.join(workdir, "tests"))
fixtures = os.path.join(workdir, "expected.json")
shutil.copyfile(os.path.join(grading_dir, "expected.json"), fixtures)
os.environ["ASSOC_S6_FIXTURES"] = fixtures
tests_dir = os.path.join(workdir, "tests")
print("running from:", tests_dir)

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
    "section": "ASSOC-S6",
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
