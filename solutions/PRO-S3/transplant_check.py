# Databricks notebook source
# MAGIC %md
# MAGIC # Anti-transplant check — PRO-S3
# MAGIC
# MAGIC Applies the **lesson's** row-level quality rules to the meter readings and
# MAGIC asserts the graded suite FAILS.
# MAGIC
# MAGIC The lesson's rules are all of the form "is this value acceptable". Every row here
# MAGIC passes every one of them, so the transplanted check reports a clean table.

# COMMAND ----------

from pyspark.sql import functions as F

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")
T = "pro_s3_quality_findings"

if spark.catalog.tableExists(T):
    spark.sql(f"CREATE OR REPLACE TABLE {T}_backup AS SELECT * FROM {T}")
    print("backed up the correct findings")

# COMMAND ----------

# MAGIC %md
# MAGIC ## The lesson's rules, verbatim

# COMMAND ----------

t = spark.table("pro_s3_assess_meter_readings")

rules = {
    "value_present": F.col("meter_total").isNotNull(),
    "value_non_negative": F.col("meter_total") >= 0,
    "timestamp_present": F.col("read_at").isNotNull(),
    "value_in_range": F.col("meter_total").between(0, 100000),
}
total_violations = 0
for name, rule in rules.items():
    v = t.filter(~rule).count()
    total_violations += v
    print(f"{name:20} violations: {v}")

print(f"\ntotal row-level violations: {total_violations}")

# COMMAND ----------

findings = spark.createDataFrame([
    ("row_level_checks", 0.0, "",
     f"all {t.count()} rows pass every value-level rule; no quality issues detected"),
], "finding STRING, affected_rows DOUBLE, affected_devices STRING, detail STRING")

findings.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(T)
print("lesson-style conclusion: 'no quality issues detected' - which is wrong three times over")

# COMMAND ----------

# MAGIC %pip install pytest -q
# MAGIC %restart_python

# COMMAND ----------

import io, contextlib, os, shutil, tempfile
import pytest

ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
repo_root = ("/Workspace" + os.path.dirname(ctx.notebookPath().get())).split("/files/")[0] + "/files"
workdir = tempfile.mkdtemp(prefix="transplant_pro_s3_")
shutil.copytree(os.path.join(repo_root, "notebooks", "assignments", "PRO-S3", "tests"),
                os.path.join(workdir, "tests"))
fx = os.path.join(workdir, "expected.json")
shutil.copyfile(os.path.join(repo_root, "solutions", "PRO-S3", "expected.json"), fx)
os.environ["PRO_S3_FIXTURES"] = fx

buf = io.StringIO()
with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
    code = pytest.main([os.path.join(workdir, "tests"), "-q", "--tb=line",
                        "-p", "no:cacheprovider"])
print(buf.getvalue()[-2500:])

# COMMAND ----------

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")
T = "pro_s3_quality_findings"
if spark.catalog.tableExists(f"{T}_backup"):
    spark.sql(f"CREATE OR REPLACE TABLE {T} AS SELECT * FROM {T}_backup")
    spark.sql(f"DROP TABLE {T}_backup")
    print("restored the correct findings")

if code == 0:
    raise RuntimeError(
        "DESIGN REGRESSION: row-level checks PASSED the assignment. Redesign the "
        "pairing before shipping this section."
    )
print(f"anti-transplant property holds - the lesson's approach fails (pytest exit {code})")
