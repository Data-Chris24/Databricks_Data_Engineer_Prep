# Databricks notebook source
# MAGIC %md
# MAGIC # Anti-transplant check — ASSOC-S7
# MAGIC
# MAGIC Applies the **lesson's** approach — one mask on one column, no hashing, no row
# MAGIC filter — to the assessment table and asserts the graded suite FAILS.

# COMMAND ----------

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")
T = "s7_governed_employees"

if spark.catalog.tableExists(T):
    spark.sql(f"CREATE OR REPLACE TABLE {T}_backup AS SELECT * FROM {T}")
    print("backed up the correct table")

# COMMAND ----------

# MAGIC %md
# MAGIC ## The lesson's approach, verbatim
# MAGIC
# MAGIC Lesson 2 masked one column and left the rest alone. That was correct there —
# MAGIC one sensitive column, one audience. Here it leaves the direct identifier in the
# MAGIC table.

# COMMAND ----------

# Drop policies from any previous run so this starts from the lesson's position.
for stmt in (f"ALTER TABLE {T} DROP ROW FILTER",
             f"ALTER TABLE {T} ALTER COLUMN salary DROP MASK",
             f"ALTER TABLE {T} ALTER COLUMN case_note DROP MASK"):
    try:
        spark.sql(stmt)
    except Exception:
        pass

# The lesson-style table: national_id carried through, masked rather than hashed.
spark.sql(f"""
    CREATE OR REPLACE TABLE {T} AS
    SELECT employee_id, full_name, national_id, region, department, salary,
           case_note, hired_on
    FROM s7_assess_employees
""")
spark.sql("""
    CREATE OR REPLACE FUNCTION s7_lesson_mask(v STRING)
    RETURN CASE WHEN is_member('admins') THEN v ELSE '****' END
""")
spark.sql(f"ALTER TABLE {T} ALTER COLUMN national_id SET MASK s7_lesson_mask")
print("lesson-style table built: national_id present and merely masked")

# COMMAND ----------

# MAGIC %pip install pytest -q
# MAGIC %restart_python

# COMMAND ----------

import io, contextlib, os, shutil, tempfile
import pytest

ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
repo_root = ("/Workspace" + os.path.dirname(ctx.notebookPath().get())).split("/files/")[0] + "/files"
workdir = tempfile.mkdtemp(prefix="transplant_s7_")
shutil.copytree(os.path.join(repo_root, "notebooks", "assignments", "ASSOC-S7", "tests"),
                os.path.join(workdir, "tests"))
fx = os.path.join(workdir, "expected.json")
shutil.copyfile(os.path.join(repo_root, "solutions", "ASSOC-S7", "expected.json"), fx)
os.environ["ASSOC_S7_FIXTURES"] = fx

buf = io.StringIO()
with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
    code = pytest.main([os.path.join(workdir, "tests"), "-q", "--tb=line",
                        "-p", "no:cacheprovider"])
print(buf.getvalue()[-2500:])

# COMMAND ----------

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")
T = "s7_governed_employees"
try:
    spark.sql(f"ALTER TABLE {T} ALTER COLUMN national_id DROP MASK")
except Exception:
    pass
if spark.catalog.tableExists(f"{T}_backup"):
    spark.sql(f"CREATE OR REPLACE TABLE {T} AS SELECT * FROM {T}_backup")
    spark.sql(f"DROP TABLE {T}_backup")
    print("restored the correct table")

if code == 0:
    raise RuntimeError(
        "DESIGN REGRESSION: the lesson's own approach PASSED the assignment. Redesign "
        "the pairing before shipping this section."
    )
print(f"anti-transplant property holds - the lesson's approach fails (pytest exit {code})")
