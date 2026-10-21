# Databricks notebook source
# MAGIC %md
# MAGIC # Anti-transplant check — ASSOC-S5
# MAGIC
# MAGIC Applies the **lesson's** approach — a hardcoded destination — and asserts the
# MAGIC graded suite FAILS.
# MAGIC
# MAGIC This is the clearest case of the pairing in the whole project: the lesson's code
# MAGIC is not merely less good here, it is structurally incapable of producing the
# MAGIC required result, because one hardcoded destination cannot populate two
# MAGIC environments distinguishably.

# COMMAND ----------

from pyspark.sql import functions as F

CATALOG = "workspace"
spark.sql(f"USE CATALOG {CATALOG}")

for schema in ("de_prep", "de_prep_staging"):
    t = f"{CATALOG}.{schema}.s5_channel_summary"
    if spark.catalog.tableExists(t):
        spark.sql(f"CREATE OR REPLACE TABLE {t}_backup AS SELECT * FROM {t}")
print("backed up both environments")

# COMMAND ----------

# MAGIC %md
# MAGIC ## The lesson's approach, verbatim
# MAGIC
# MAGIC Lesson 1 wrote `saveAsTable("s5_channel_summary")` after `USE SCHEMA de_prep`.
# MAGIC Correct there — one environment. Run it "twice for two environments" and both
# MAGIC writes land in the same place, stamped identically.

# COMMAND ----------

spark.sql("USE SCHEMA de_prep")     # hardcoded, exactly as the lesson did

summary = (spark.table("workspace.de_prep.s5_source_transactions")
    .groupBy("channel")
    .agg(F.count("*").alias("txns"),
         F.round(F.sum("amount"), 2).alias("revenue"))
    .withColumn("environment", F.lit("de_prep")))     # hardcoded stamp

summary.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable("s5_channel_summary")

# "Deploying to staging" with hardcoded code writes to production again. Simulate the
# most generous reading - the learner also copied the table across by hand.
spark.sql("""
    CREATE OR REPLACE TABLE workspace.de_prep_staging.s5_channel_summary AS
    SELECT * FROM workspace.de_prep.s5_channel_summary
""")
print("both schemas populated - but both stamped 'de_prep'")

# COMMAND ----------

# MAGIC %pip install pytest -q
# MAGIC %restart_python

# COMMAND ----------

import io, contextlib, os, shutil, tempfile
import pytest

ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
repo_root = ("/Workspace" + os.path.dirname(ctx.notebookPath().get())).split("/files/")[0] + "/files"
workdir = tempfile.mkdtemp(prefix="transplant_s5_")
shutil.copytree(os.path.join(repo_root, "grading", "ASSOC-S5", "tests"),
                os.path.join(workdir, "tests"))
fx = os.path.join(workdir, "expected.json")
shutil.copyfile(os.path.join(repo_root, "grading", "ASSOC-S5", "expected.json"), fx)
os.environ["ASSOC_S5_FIXTURES"] = fx

buf = io.StringIO()
with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
    code = pytest.main([os.path.join(workdir, "tests"), "-q", "--tb=line",
                        "-p", "no:cacheprovider"])
print(buf.getvalue()[-2500:])

# COMMAND ----------

CATALOG = "workspace"
for schema in ("de_prep", "de_prep_staging"):
    t = f"{CATALOG}.{schema}.s5_channel_summary"
    if spark.catalog.tableExists(f"{t}_backup"):
        spark.sql(f"CREATE OR REPLACE TABLE {t} AS SELECT * FROM {t}_backup")
        spark.sql(f"DROP TABLE {t}_backup")
print("restored both environments")

if code == 0:
    raise RuntimeError(
        "DESIGN REGRESSION: the lesson's hardcoded approach PASSED the assignment. "
        "Redesign the pairing before shipping this section."
    )
print(f"anti-transplant property holds - the lesson's approach fails (pytest exit {code})")
