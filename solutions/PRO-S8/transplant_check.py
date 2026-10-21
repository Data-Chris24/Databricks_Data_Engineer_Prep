# Databricks notebook source
# MAGIC %md
# MAGIC # Anti-transplant check — PRO-S8
# MAGIC
# MAGIC Applies **lesson 02's worked audit** to the assess catalog and asserts the graded
# MAGIC suite FAILS.
# MAGIC
# MAGIC The lesson's audit was three columns of `information_schema.table_privileges`,
# MAGIC which was a complete answer for a catalog whose grants all sat on tables. Here it
# MAGIC returns the same shape and cannot answer either question the report asks.

# COMMAND ----------

# MAGIC %pip install pytest -q
# MAGIC %restart_python

# COMMAND ----------

from databricks.sdk import WorkspaceClient
from pyspark.sql import functions as F

ASSESS = "pro_s8_assess"
spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")
REPORT, DOCS = "pro_s8_access_report", "pro_s8_documentation"

for t in (REPORT, DOCS):
    if spark.catalog.tableExists(t):
        spark.sql(f"CREATE OR REPLACE TABLE {t}_backup AS SELECT * FROM {t}")
print("backed up the correct tables")

# COMMAND ----------

# MAGIC %md
# MAGIC ## The lesson's audit, unchanged
# MAGIC
# MAGIC Plus the minimum needed to meet the contract's column list — because the point is
# MAGIC that the columns can be *produced* without being *answered*.

# COMMAND ----------

w = WorkspaceClient()
names = {sp.application_id: sp.display_name for sp in w.service_principals.list()
         if sp.display_name and sp.display_name.startswith("de_prep_")}
name_map = F.create_map(*[x for kv in names.items() for x in (F.lit(kv[0]), F.lit(kv[1]))])

audit = spark.sql(f"""
    SELECT grantee, table_schema, table_name, privilege_type
    FROM {ASSESS}.information_schema.table_privileges
    WHERE table_schema <> 'information_schema'
""")

report = (audit
    .withColumn("principal", name_map[F.col("grantee")])
    .filter("principal IS NOT NULL")
    .select("principal", "table_schema", "table_name",
            F.col("privilege_type").alias("privilege"),
            # the grant is listed against the table, so it must be granted there
            F.lit("TABLE").alias("granted_at_level"),
            # it is listed, so the principal must be able to use it
            F.lit(True).alias("has_use_catalog"),
            F.lit(True).alias("has_use_schema"),
            F.lit(True).alias("is_effective")))
report.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(REPORT)

docs = spark.sql(f"""
    SELECT t.table_schema, t.table_name,
           t.comment IS NOT NULL AS has_table_comment,
           CAST(count(c.column_name) AS INT) AS column_count,
           CAST(count(c.comment) AS INT) AS documented_columns,
           CAST(0 AS INT) AS tag_count,
           false AS has_pii_column,
           t.comment IS NOT NULL AS is_documented
    FROM {ASSESS}.information_schema.tables t
    JOIN {ASSESS}.information_schema.columns c
      ON c.table_schema = t.table_schema AND c.table_name = t.table_name
    WHERE t.table_schema <> 'information_schema'
    GROUP BY t.table_schema, t.table_name, t.comment
""")
docs.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(DOCS)

print("it ran, and it wrote both tables")
print("report rows:", spark.table(REPORT).count(), "(the correct answer is also 17)")
display(spark.table(REPORT).limit(6))

# COMMAND ----------

# MAGIC %md
# MAGIC The row count is right. Every column the contract asks for is present and
# MAGIC populated. Nothing errored. Only the answers are wrong.

# COMMAND ----------

import contextlib, io, os, shutil, tempfile
import pytest

ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
repo_root = ("/Workspace" + os.path.dirname(ctx.notebookPath().get())).split("/files/")[0] + "/files"

workdir = tempfile.mkdtemp(prefix="transplant_pro_s8_")
shutil.copytree(os.path.join(repo_root, "grading", "PRO-S8", "tests"),
                os.path.join(workdir, "tests"))
fixtures = os.path.join(workdir, "expected.json")
shutil.copyfile(os.path.join(repo_root, "grading", "PRO-S8", "expected.json"), fixtures)
os.environ["PRO_S8_FIXTURES"] = fixtures

buf = io.StringIO()
with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
    exit_code = pytest.main([os.path.join(workdir, "tests"), "-v", "--tb=line",
                             "-p", "no:cacheprovider"])
report_txt = buf.getvalue()
print(report_txt)
dbutils.fs.mkdirs("/Volumes/workspace/de_prep/raw/_grading")
dbutils.fs.put("/Volumes/workspace/de_prep/raw/_grading/PRO-S8-transplant.txt",
               report_txt[-30000:] + f"\n\nexit={exit_code}\n", overwrite=True)

# COMMAND ----------

for t in (REPORT, DOCS):
    if spark.catalog.tableExists(f"{t}_backup"):
        spark.sql(f"CREATE OR REPLACE TABLE {t} AS SELECT * FROM {t}_backup")
        spark.sql(f"DROP TABLE {t}_backup")
print("restored the correct tables")

assert exit_code != 0, (
    "The transplanted lesson code PASSED the graded suite. The pairing is not doing "
    "its job and PRO-S8 needs redesigning."
)
print(f"\nAnti-transplant property holds: the lesson's audit fails the suite "
      f"(pytest exit {exit_code}).")
