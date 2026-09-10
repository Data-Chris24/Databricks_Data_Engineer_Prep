# Databricks notebook source
# MAGIC %md
# MAGIC # Anti-transplant check — PRO-S6
# MAGIC
# MAGIC Applies the **lesson's** single-cause diagnosis - cluster on the filtered column -
# MAGIC and asserts the graded suite FAILS.

# COMMAND ----------

from pyspark.sql import functions as F

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")
T = "pro_s6_optimization_report"

if spark.catalog.tableExists(T):
    spark.sql(f"CREATE OR REPLACE TABLE {T}_backup AS SELECT * FROM {T}")
    print("backed up the correct report")

# COMMAND ----------

# MAGIC %md
# MAGIC ## The lesson's approach, verbatim
# MAGIC
# MAGIC Profile the table, notice it is unclustered, recommend clustering. Correct for
# MAGIC the teach table, where that was the only problem.

# COMMAND ----------

d = spark.sql("DESCRIBE DETAIL pro_s6_assess_orders").collect()[0]

lesson_only = spark.createDataFrame([
    ("bad_cluster_key", "region", 0.03,
     f"the table has {d['numFiles']} files and no clustering; cluster on region"),
], "finding STRING, recommendation STRING, metric DOUBLE, detail STRING")

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
workdir = tempfile.mkdtemp(prefix="transplant_pro_s6_")
shutil.copytree(os.path.join(repo_root, "notebooks", "assignments", "PRO-S6", "tests"),
                os.path.join(workdir, "tests"))
fx = os.path.join(workdir, "expected.json")
shutil.copyfile(os.path.join(repo_root, "solutions", "PRO-S6", "expected.json"), fx)
os.environ["PRO_S6_FIXTURES"] = fx

buf = io.StringIO()
with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
    code = pytest.main([os.path.join(workdir, "tests"), "-q", "--tb=line",
                        "-p", "no:cacheprovider"])
print(buf.getvalue()[-2500:])

# COMMAND ----------

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")
T = "pro_s6_optimization_report"
if spark.catalog.tableExists(f"{T}_backup"):
    spark.sql(f"CREATE OR REPLACE TABLE {T} AS SELECT * FROM {T}_backup")
    spark.sql(f"DROP TABLE {T}_backup")
    print("restored the correct report")

if code == 0:
    raise RuntimeError(
        "DESIGN REGRESSION: the lesson's single-cause diagnosis PASSED. Redesign the "
        "pairing before shipping this section."
    )
print(f"anti-transplant property holds - the lesson's approach fails (pytest exit {code})")
