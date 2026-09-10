# Databricks notebook source
# MAGIC %md
# MAGIC # Anti-transplant check — ASSOC-S6
# MAGIC
# MAGIC Applies the **lesson's** single-query diagnosis to the assessment table and
# MAGIC asserts the graded suite FAILS. The lesson found skew with one `GROUP BY`; here
# MAGIC that is one finding out of three.

# COMMAND ----------

from pyspark.sql import functions as F

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")
T = "s6_health_report"

if spark.catalog.tableExists(T):
    spark.sql(f"CREATE OR REPLACE TABLE {T}_backup AS SELECT * FROM {T}")
    print("backed up the correct report")

# COMMAND ----------

# MAGIC %md
# MAGIC ## The lesson's approach, verbatim
# MAGIC
# MAGIC Group by the key, find the dominant one, report it. Correct as far as it goes —
# MAGIC and it goes one third of the way.

# COMMAND ----------

t = spark.table("s6_assess_orders")
total = t.count()
dist = t.groupBy("region").count().orderBy(F.desc("count"))
top = dist.first()
skew_pct = round(100.0 * top["count"] / total, 1)

lesson_only = spark.createDataFrame([
    ("skew", "region", float(skew_pct),
     f"{top['region']} holds {skew_pct}% of rows, so any shuffle on region is unbalanced"),
], "finding STRING, column_name STRING, metric DOUBLE, detail STRING")

lesson_only.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(T)
print(f"lesson-style diagnosis produced {spark.table(T).count()} finding (should be 3)")

# COMMAND ----------

# MAGIC %pip install pytest -q
# MAGIC %restart_python

# COMMAND ----------

import io, contextlib, os, shutil, tempfile
import pytest

ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
repo_root = ("/Workspace" + os.path.dirname(ctx.notebookPath().get())).split("/files/")[0] + "/files"
workdir = tempfile.mkdtemp(prefix="transplant_s6_")
shutil.copytree(os.path.join(repo_root, "notebooks", "assignments", "ASSOC-S6", "tests"),
                os.path.join(workdir, "tests"))
fx = os.path.join(workdir, "expected.json")
shutil.copyfile(os.path.join(repo_root, "solutions", "ASSOC-S6", "expected.json"), fx)
os.environ["ASSOC_S6_FIXTURES"] = fx

buf = io.StringIO()
with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
    code = pytest.main([os.path.join(workdir, "tests"), "-q", "--tb=line",
                        "-p", "no:cacheprovider"])
print(buf.getvalue()[-2500:])

# COMMAND ----------

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")
T = "s6_health_report"
if spark.catalog.tableExists(f"{T}_backup"):
    spark.sql(f"CREATE OR REPLACE TABLE {T} AS SELECT * FROM {T}_backup")
    spark.sql(f"DROP TABLE {T}_backup")
    print("restored the correct report")

if code == 0:
    raise RuntimeError(
        "DESIGN REGRESSION: the lesson's single-query diagnosis PASSED the assignment. "
        "Redesign the pairing before shipping this section."
    )
print(f"anti-transplant property holds - the lesson's approach fails (pytest exit {code})")
