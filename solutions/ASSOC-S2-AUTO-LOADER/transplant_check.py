# Databricks notebook source
# MAGIC %md
# MAGIC # Anti-transplant check
# MAGIC
# MAGIC The claim the assignment rests on: **the deep-dive lesson's streams, pointed at
# MAGIC the ferry data, do not pass.** This tests it rather than assuming it.
# MAGIC
# MAGIC Each lesson stream is copied with only its path and table changed: the orders
# MAGIC CSV options for the tickets, the customers JSON options for the vessels (both
# MAGIC deliveries landed at once, as a learner skipping requirement 4 would), the
# MAGIC suppliers XML options for the manifests, the stock-count ORC options for the
# MAGIC crossings and the receipts binaryFile options for the scans. Every stream keeps
# MAGIC its state where the contract says, so the failures are about the data, not the
# MAGIC folders. **The suite must fail.**
# MAGIC
# MAGIC It overwrites the `ferry_*` tables and `s2_al_work/`. Run the reference solution
# MAGIC afterwards if you need them back.

# COMMAND ----------

CATALOG, SCHEMA = "workspace", "de_prep"
SRC = f"/Volumes/{CATALOG}/{SCHEMA}/raw/s2_al_assess"
WORK = f"/Volumes/{CATALOG}/{SCHEMA}/raw/s2_al_work"
TABLES = ["ferry_tickets", "ferry_vessels", "ferry_manifests", "ferry_crossings", "ferry_scans"]

spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")
for t in TABLES:
    spark.sql(f"DROP TABLE IF EXISTS {t}")
dbutils.fs.rm(WORK, True)
for f in dbutils.fs.ls(f"{SRC}/vessels/batch_1") + dbutils.fs.ls(f"{SRC}/vessels/batch_2"):
    dbutils.fs.cp(f.path, f"{WORK}/vessels_landing/{f.name}")


def lesson_stream(table, source, fmt, options, select=None):
    """A lesson stream with its path and table swapped; a failure is recorded, not raised."""
    try:
        r = (spark.readStream.format("cloudFiles")
             .option("cloudFiles.format", fmt)
             .option("cloudFiles.schemaLocation", f"{WORK}/{table}/_schema"))
        for k, v in options.items():
            r = r.option(k, v)
        df = r.load(source)
        if select:
            df = df.select(*select)
        (df.writeStream.option("checkpointLocation", f"{WORK}/{table}/_checkpoint")
            .trigger(availableNow=True).toTable(table).awaitTermination())
        print(f"{table}: loaded {spark.table(table).count()} rows")
    except Exception as e:
        print(f"{table}: the lesson's stream did not run here: {str(e).split(chr(10))[0][:200]}")


# 04_optional_auto_loader_deep_dive, section 3, verbatim but for paths and names.
lesson_stream("ferry_tickets", f"{SRC}/tickets", "csv", {
    "sep": ";", "multiLine": "true", "escape": '"',
    "cloudFiles.inferColumnTypes": "true", "cloudFiles.schemaHints": "unit_price DECIMAL(10,2)"})
lesson_stream("ferry_vessels", f"{WORK}/vessels_landing", "json", {
    "multiLine": "true", "cloudFiles.inferColumnTypes": "true"})
lesson_stream("ferry_manifests", f"{SRC}/manifests", "xml", {
    "rowTag": "supplier", "cloudFiles.inferColumnTypes": "true"})
lesson_stream("ferry_crossings", f"{SRC}/crossings", "orc", {"cloudFiles.schemaEvolutionMode": "none"})
lesson_stream("ferry_scans", f"{SRC}/scans", "binaryFile", {"pathGlobFilter": "*.png"},
              select=["path", "modificationTime", "length"])

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
grading = os.path.join(repo_root, "grading", "ASSOC-S2-AUTO-LOADER")

workdir = tempfile.mkdtemp(prefix="transplant_")
shutil.copytree(os.path.join(grading, "tests"), os.path.join(workdir, "tests"))
fixtures = os.path.join(workdir, "expected.json")
shutil.copyfile(os.path.join(grading, "expected.json"), fixtures)
os.environ["ASSOC_S2_AUTO_LOADER_FIXTURES"] = fixtures

buf = io.StringIO()
with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
    code = pytest.main([os.path.join(workdir, "tests"), "-q", "--tb=line", "-p", "no:cacheprovider"])
report = buf.getvalue()
print(report[-6000:])

# COMMAND ----------

# MAGIC %md
# MAGIC ## Verdict

# COMMAND ----------

if code == 0:
    raise RuntimeError(
        "DESIGN REGRESSION: the deep-dive lesson's own streams PASSED the optional "
        "assignment. The ferry exports are no longer different enough from the lesson's "
        "sources; redesign them before shipping."
    )
dbutils.notebook.exit(f"anti-transplant property holds - the lesson's streams fail (pytest exit {code})")
