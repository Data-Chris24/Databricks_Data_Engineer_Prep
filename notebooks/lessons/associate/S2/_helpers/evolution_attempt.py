# Databricks notebook source
# MAGIC %md
# MAGIC # Helper: one schema-evolution attempt, run on its own
# MAGIC
# MAGIC Called by `04_optional_auto_loader_deep_dive` with `dbutils.notebook.run`, never
# MAGIC opened by hand. It lands one file, runs the stream, lands a second file with a
# MAGIC new column, and runs the stream three more times, recording what each run did.
# MAGIC
# MAGIC **Why a separate notebook run.** A stream that fails *while running* fails the
# MAGIC notebook that started it, even when the exception is caught: measured on Free
# MAGIC Edition serverless (2026-10-24), the notebook still ends "Workload failed". The
# MAGIC deep dive wants to show you those failures, so it runs them here and reads
# MAGIC back the record this notebook writes before it fails.

# COMMAND ----------

import json
import re

dbutils.widgets.text("mode", "addNewColumns")        # cloudFiles.schemaEvolutionMode
dbutils.widgets.text("merge_schema", "true")         # the writer's mergeSchema
dbutils.widgets.text("work", "")                     # a scratch folder of its own
dbutils.widgets.text("table", "")
dbutils.widgets.text("extra_reader_options", "{}")   # more reader options, as JSON

MODE = dbutils.widgets.get("mode")
MERGE = dbutils.widgets.get("merge_schema")
WORK = dbutils.widgets.get("work")
TABLE = dbutils.widgets.get("table")
EXTRA = json.loads(dbutils.widgets.get("extra_reader_options") or "{}")
if not WORK.startswith("/Volumes/") or not TABLE:
    raise ValueError("work must be a /Volumes path and table must be set")

LANDING = f"{WORK}/landing"
dbutils.fs.rm(WORK, True)
spark.sql(f"DROP TABLE IF EXISTS {TABLE}")
dbutils.fs.put(f"{LANDING}/orders_1.csv", "order_id,store\nA-1,boston\nA-2,denver\n")

record = {"mode": MODE, "merge_schema": MERGE, "extra_reader_options": EXTRA, "runs": []}


def run_stream():
    (spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "csv")
        .option("cloudFiles.schemaLocation", f"{WORK}/_schema")         # reader
        .option("header", "true")                                      # reader
        .option("cloudFiles.schemaEvolutionMode", MODE)                # reader
        .options(**EXTRA)                                              # reader: whatever the lesson adds
        .load(LANDING)
     .writeStream
        .option("checkpointLocation", f"{WORK}/_checkpoint")           # writer
        .option("mergeSchema", MERGE)                                  # writer
        .trigger(availableNow=True)                                    # writer
        .toTable(TABLE)
        .awaitTermination())


def attempt(label):
    entry = {"run": label}
    try:
        run_stream()
        t = spark.table(TABLE)
        entry.update(ok=True, columns=t.columns, rows=t.count())
    except Exception as e:
        msg = str(e)
        # "[STREAM_FAILED] Query [...] terminated with exception: [THE_REAL_ONE] ..."
        codes = [c for c in re.findall(r"\[([A-Z][A-Z0-9_.]+)\]", msg) if c != "STREAM_FAILED"]
        code = codes[0] if codes else type(e).__name__
        entry.update(ok=False, error=code, message=msg.split("JVM stacktrace")[0].strip()[:400])
    if entry.get("ok") and "_rescued_data" in entry["columns"]:
        entry["rescued"] = [r[0] for r in spark.table(TABLE).where("_rescued_data IS NOT NULL").select("_rescued_data").collect()]
    record["runs"].append(entry)
    # Written after every run: if the notebook fails at the end, this is all that survives.
    dbutils.fs.put(f"{WORK}/_record.json", json.dumps(record), overwrite=True)


attempt("1: first file")
dbutils.fs.put(f"{LANDING}/orders_2.csv", "order_id,store,channel\nA-3,austin,web\n")
for n in (2, 3, 4):
    attempt(f"{n}: after a file with a new column")

dbutils.notebook.exit(json.dumps(record))
