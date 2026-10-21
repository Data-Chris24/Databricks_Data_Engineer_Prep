# Databricks notebook source
# MAGIC %md
# MAGIC # Anti-transplant check — PRO-S7
# MAGIC
# MAGIC Applies the **lesson's** column-by-column de-identification and asserts the
# MAGIC graded suite FAILS. It hashes the subject and drops the name — correct for the
# MAGIC teach table, where that was all the PII there was.

# COMMAND ----------

from pyspark.sql import functions as F

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")
T = "pro_s7_compliant_records"
SALT = "per-dataset-salt-kept-in-a-secret-scope"

if spark.catalog.tableExists(T):
    spark.sql(f"CREATE OR REPLACE TABLE {T}_backup AS SELECT * FROM {T}")
    print("backed up the correct table")

# COMMAND ----------

# MAGIC %md
# MAGIC ## The lesson's approach, verbatim
# MAGIC
# MAGIC Hash the identifier, drop the name, publish. No purge, no retention, no scan of
# MAGIC the free-text column - because the teach table had none of those problems.

# COMMAND ----------

naive = (spark.table("pro_s7_assess_records")
    .withColumn("subject_hash", F.sha2(F.concat(F.lit(SALT), F.col("subject_id")), 256))
    .select("record_id", "subject_hash", "record_type", "case_note", "created_on"))

naive.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(T)
print(f"lesson-style de-identification published {spark.table(T).count()} rows (should be ~263)")

leaky = spark.table(T).filter(
    F.col("case_note").rlike(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")).count()
print(f"notes still containing an email address: {leaky}")

# COMMAND ----------

# MAGIC %pip install pytest -q
# MAGIC %restart_python

# COMMAND ----------

import io, contextlib, os, shutil, tempfile
import pytest

ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
repo_root = ("/Workspace" + os.path.dirname(ctx.notebookPath().get())).split("/files/")[0] + "/files"
workdir = tempfile.mkdtemp(prefix="transplant_pro_s7_")
shutil.copytree(os.path.join(repo_root, "grading", "PRO-S7", "tests"),
                os.path.join(workdir, "tests"))
fx = os.path.join(workdir, "expected.json")
shutil.copyfile(os.path.join(repo_root, "grading", "PRO-S7", "expected.json"), fx)
os.environ["PRO_S7_FIXTURES"] = fx

buf = io.StringIO()
with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
    code = pytest.main([os.path.join(workdir, "tests"), "-q", "--tb=line",
                        "-p", "no:cacheprovider"])
print(buf.getvalue()[-2500:])

# COMMAND ----------

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")
T = "pro_s7_compliant_records"
if spark.catalog.tableExists(f"{T}_backup"):
    spark.sql(f"CREATE OR REPLACE TABLE {T} AS SELECT * FROM {T}_backup")
    spark.sql(f"DROP TABLE {T}_backup")
    print("restored the correct table")

if code == 0:
    raise RuntimeError(
        "DESIGN REGRESSION: column-by-column de-identification PASSED. Redesign the "
        "pairing before shipping this section."
    )
print(f"anti-transplant property holds - the lesson's approach fails (pytest exit {code})")
