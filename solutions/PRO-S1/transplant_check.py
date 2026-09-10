# Databricks notebook source
# MAGIC %md
# MAGIC # Anti-transplant check — PRO-S1
# MAGIC
# MAGIC Applies the **lesson's** snapshot pipeline to the change feed and asserts the
# MAGIC graded suite FAILS.

# COMMAND ----------

from pyspark.sql import functions as F

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")
T = "pro_s1_current_customers"

if spark.catalog.tableExists(T):
    spark.sql(f"CREATE OR REPLACE TABLE {T}_backup AS SELECT * FROM {T}")
    print("backed up the correct table")

# COMMAND ----------

# MAGIC %md
# MAGIC ## The lesson's approach, verbatim
# MAGIC
# MAGIC Read, transform, write - plus the most generous addition a learner might make,
# MAGIC a dedup on the key. Correct for a snapshot. Here it keeps an arbitrary event per
# MAGIC key, tombstones included, and ignores sequencing entirely.

# COMMAND ----------

naive = (spark.table("pro_s1_assess_changes")
    .dropDuplicates(["customer_id"])
    .select("customer_id", "tier", "balance",
            F.col("seq_num").alias("last_seq"),
            F.col("event_ts").alias("last_event_ts")))

naive.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(T)
print(f"snapshot-style pipeline produced {spark.table(T).count()} rows (should be 272)")

# COMMAND ----------

# MAGIC %pip install pytest -q
# MAGIC %restart_python

# COMMAND ----------

import io, contextlib, os, shutil, tempfile
import pytest

ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
repo_root = ("/Workspace" + os.path.dirname(ctx.notebookPath().get())).split("/files/")[0] + "/files"
workdir = tempfile.mkdtemp(prefix="transplant_pro_s1_")
shutil.copytree(os.path.join(repo_root, "notebooks", "assignments", "PRO-S1", "tests"),
                os.path.join(workdir, "tests"))
fx = os.path.join(workdir, "expected.json")
shutil.copyfile(os.path.join(repo_root, "solutions", "PRO-S1", "expected.json"), fx)
os.environ["PRO_S1_FIXTURES"] = fx

buf = io.StringIO()
with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
    code = pytest.main([os.path.join(workdir, "tests"), "-q", "--tb=line",
                        "-p", "no:cacheprovider"])
print(buf.getvalue()[-2500:])

# COMMAND ----------

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")
T = "pro_s1_current_customers"
if spark.catalog.tableExists(f"{T}_backup"):
    spark.sql(f"CREATE OR REPLACE TABLE {T} AS SELECT * FROM {T}_backup")
    spark.sql(f"DROP TABLE {T}_backup")
    print("restored the correct table")

if code == 0:
    raise RuntimeError(
        "DESIGN REGRESSION: the snapshot pipeline PASSED the assignment. Redesign the "
        "pairing before shipping this section."
    )
print(f"anti-transplant property holds - the lesson's approach fails (pytest exit {code})")
