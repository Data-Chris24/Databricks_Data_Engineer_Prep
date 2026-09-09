# Databricks notebook source
# MAGIC %md
# MAGIC # Anti-transplant check
# MAGIC
# MAGIC The claim the whole assignment design rests on: **a learner cannot pass by
# MAGIC copying the lesson.** This tests that claim rather than assuming it.
# MAGIC
# MAGIC It applies the lesson's own approach — a plain read, no schema merge, a
# MAGIC straight cast to timestamp, no explode, no dedup — to the assess data, then
# MAGIC runs the graded suite against the result. **The suite must fail.**
# MAGIC
# MAGIC If it ever passes, the two datasets are no longer structurally different
# MAGIC enough and the pairing needs redesigning. That is a design regression, so this
# MAGIC runs in CI alongside the tests.

# COMMAND ----------

from pyspark.sql import functions as F

CATALOG, SCHEMA = "workspace", "de_prep"
RAW = f"/Volumes/{CATALOG}/{SCHEMA}/raw/s2_assess"
TABLE = "silver_sensor_readings"
BACKUP = "silver_sensor_readings_correct_backup"

spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")

# Preserve the correct table so this check does not destroy a real answer.
if spark.catalog.tableExists(TABLE):
    spark.sql(f"CREATE OR REPLACE TABLE {BACKUP} AS SELECT * FROM {TABLE}")
    print(f"backed up {TABLE} -> {BACKUP}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Apply the lesson's approach verbatim
# MAGIC
# MAGIC Read the files, cast the timestamp, write the table. Exactly the shape of
# MAGIC `01_copy_into.py`'s bronze-to-silver step, pointed at the new data.

# COMMAND ----------

# No mergeSchema - the lesson never needed it, its files all matched.
transplanted = spark.read.json(RAW)

print("columns the lesson's read produces:", transplanted.columns)

# The lesson's silver step: select, cast, write. There is no explode because the
# teach data had nothing nested, and no dedup because it had no duplicates.
try:
    naive = transplanted.select(
        F.col("device_id"),
        F.col("site"),
        F.col("firmware"),
        F.col("readings"),
    )
    naive.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(TABLE)
    print(f"wrote {spark.table(TABLE).count()} rows - note the grain is wrong")
except Exception as e:
    print("the lesson's code did not even run against this data:", type(e).__name__)
    raise

# COMMAND ----------

# MAGIC %md
# MAGIC ## Run the graded suite against it
# MAGIC
# MAGIC Expected: failures. Any pass here is the design regression.

# COMMAND ----------

# MAGIC %pip install pytest -q
# MAGIC %restart_python

# COMMAND ----------

import io, contextlib, os, shutil, tempfile
import pytest

ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
repo_root = ("/Workspace" + os.path.dirname(ctx.notebookPath().get())).split("/files/")[0] + "/files"
tests_src = os.path.join(repo_root, "notebooks", "assignments", "ASSOC-S2", "tests")

workdir = tempfile.mkdtemp(prefix="transplant_")
shutil.copytree(tests_src, os.path.join(workdir, "tests"))
fixtures = os.path.join(workdir, "expected.json")
shutil.copyfile(os.path.join(repo_root, "solutions", "ASSOC-S2", "expected.json"), fixtures)
os.environ["ASSOC_S2_FIXTURES"] = fixtures

buf = io.StringIO()
with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
    code = pytest.main([os.path.join(workdir, "tests"), "-q", "--tb=line",
                        "-p", "no:cacheprovider"])
report = buf.getvalue()
print(report[-4000:])

# COMMAND ----------

# MAGIC %md
# MAGIC ## Verdict

# COMMAND ----------

CATALOG, SCHEMA = "workspace", "de_prep"
TABLE = "silver_sensor_readings"
BACKUP = "silver_sensor_readings_correct_backup"
spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")

# Restore whatever was there before, so this check leaves no trace.
if spark.catalog.tableExists(BACKUP):
    spark.sql(f"CREATE OR REPLACE TABLE {TABLE} AS SELECT * FROM {BACKUP}")
    spark.sql(f"DROP TABLE {BACKUP}")
    print("restored the correct table")

if code == 0:
    raise RuntimeError(
        "DESIGN REGRESSION: the lesson's own approach PASSED the assignment. "
        "The teach and assess datasets are no longer structurally different "
        "enough - the assignment can now be solved by copy-paste. Redesign the "
        "pairing before shipping this section."
    )

print(f"anti-transplant property holds - the lesson's approach fails (pytest exit {code})")
