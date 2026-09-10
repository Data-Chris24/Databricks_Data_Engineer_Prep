# Databricks notebook source
# MAGIC %md
# MAGIC # Anti-transplant check — ASSOC-S3
# MAGIC
# MAGIC Applies the **lesson's** join approach to the assessment data and asserts the
# MAGIC graded suite FAILS. A pass here means the datasets are no longer structurally
# MAGIC different enough and the assignment became copy-pasteable.

# COMMAND ----------

from pyspark.sql import functions as F

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")
TABLE = "s3_gold_billing_enriched"
BACKUP = "s3_gold_billing_enriched_correct_backup"

if spark.catalog.tableExists(TABLE):
    spark.sql(f"CREATE OR REPLACE TABLE {BACKUP} AS SELECT * FROM {TABLE}")
    print("backed up the correct table")

# COMMAND ----------

# MAGIC %md
# MAGIC ## The lesson's approach, verbatim
# MAGIC
# MAGIC Lesson 1 joined a fact to a dimension on the key with a left join, and that was
# MAGIC correct there because the dimension had one row per key. Here it does not.

# COMMAND ----------

events = spark.table("s3_assess_billing_events")
plans = spark.table("s3_assess_plans")

transplanted = (events.join(plans, on="plan_id", how="left")
    .withColumn("amount", F.col("amount_cents"))          # no minor-unit conversion
    .withColumn("signed_amount", F.col("amount_cents"))
    .withColumn("plan_missing", F.col("plan_name").isNull())
    .select("billing_id", "account_id", "plan_id", "event_date", "event_type",
            "amount", "signed_amount", "plan_name", "tier", "plan_missing"))

transplanted.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(TABLE)
print(f"lesson-style join produced {spark.table(TABLE).count()} rows (should be 600)")

# COMMAND ----------

# MAGIC %pip install pytest -q
# MAGIC %restart_python

# COMMAND ----------

import io, contextlib, os, shutil, tempfile
import pytest

ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
repo_root = ("/Workspace" + os.path.dirname(ctx.notebookPath().get())).split("/files/")[0] + "/files"
workdir = tempfile.mkdtemp(prefix="transplant_s3_")
shutil.copytree(os.path.join(repo_root, "notebooks", "assignments", "ASSOC-S3", "tests"),
                os.path.join(workdir, "tests"))
fx = os.path.join(workdir, "expected.json")
shutil.copyfile(os.path.join(repo_root, "solutions", "ASSOC-S3", "expected.json"), fx)
os.environ["ASSOC_S3_FIXTURES"] = fx

buf = io.StringIO()
with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
    code = pytest.main([os.path.join(workdir, "tests"), "-q", "--tb=line",
                        "-p", "no:cacheprovider"])
print(buf.getvalue()[-3000:])

# COMMAND ----------

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")
TABLE = "s3_gold_billing_enriched"
BACKUP = "s3_gold_billing_enriched_correct_backup"

if spark.catalog.tableExists(BACKUP):
    spark.sql(f"CREATE OR REPLACE TABLE {TABLE} AS SELECT * FROM {BACKUP}")
    spark.sql(f"DROP TABLE {BACKUP}")
    print("restored the correct table")

if code == 0:
    raise RuntimeError(
        "DESIGN REGRESSION: the lesson's own approach PASSED the assignment. The teach "
        "and assess datasets are no longer structurally different enough - the "
        "assignment can now be solved by copy-paste. Redesign the pairing."
    )
print(f"anti-transplant property holds - the lesson's approach fails (pytest exit {code})")
