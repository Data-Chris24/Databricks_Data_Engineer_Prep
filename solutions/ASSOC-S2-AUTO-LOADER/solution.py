# Databricks notebook source
# MAGIC %md
# MAGIC # ASSOC-S2-AUTO-LOADER assignment — reference solution
# MAGIC
# MAGIC **Learners: this is the answer.** Read it after you have a passing suite, or after
# MAGIC you are genuinely stuck.
# MAGIC
# MAGIC Its other job is to generate the expected-value fixtures the test suite asserts
# MAGIC against (`grading/ASSOC-S2-AUTO-LOADER/expected.json`): the run's exit value is the
# MAGIC fixture JSON, so the tests never need this notebook present.

# COMMAND ----------

import json

from pyspark.sql import functions as F

CATALOG, SCHEMA = "workspace", "de_prep"
SRC = f"/Volumes/{CATALOG}/{SCHEMA}/raw/s2_al_assess"
WORK = f"/Volumes/{CATALOG}/{SCHEMA}/raw/s2_al_work"
TABLES = ["ferry_tickets", "ferry_vessels", "ferry_manifests", "ferry_crossings", "ferry_scans"]

spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")

# Start from nothing: the tables AND their folders. Dropping only a table leaves its
# checkpoint, which would remember every file as loaded.
for t in TABLES:
    spark.sql(f"DROP TABLE IF EXISTS {t}")
dbutils.fs.rm(WORK, True)


def cp(table):
    return f"{WORK}/{table}/_checkpoint"


def sl(table):
    return f"{WORK}/{table}/_schema"

# COMMAND ----------

# MAGIC %md
# MAGIC ## Tickets: `|`, `N/A`, `dd/MM/yyyy HH:mm`, multi-line remarks, bad fares
# MAGIC
# MAGIC Every option here is a reader option: they all describe the file. The hint pins
# MAGIC two types; `timestampFormat` lets the hint parse; the fares that are not numbers
# MAGIC become null and land in `_rescued_data`.

# COMMAND ----------

(spark.readStream.format("cloudFiles")
    .option("cloudFiles.format", "csv")
    .option("cloudFiles.schemaLocation", sl("ferry_tickets"))
    .option("header", "true")
    .option("sep", "|")
    .option("multiLine", "true")
    .option("escape", '"')
    .option("nullValue", "N/A")
    .option("timestampFormat", "dd/MM/yyyy HH:mm")
    .option("cloudFiles.inferColumnTypes", "true")
    .option("cloudFiles.schemaHints", "departs TIMESTAMP, fare_gbp DECIMAL(8,2)")
    .load(f"{SRC}/tickets")
 .writeStream
    .option("checkpointLocation", cp("ferry_tickets"))
    .trigger(availableNow=True)
    .toTable("ferry_tickets")
    .awaitTermination())

# COMMAND ----------

# MAGIC %md
# MAGIC ## Vessels: two deliveries, one new field
# MAGIC
# MAGIC Reader: `multiLine` (each file is one array), `inferColumnTypes` (so `engine` is
# MAGIC a struct), `addNewColumns`. Writer: `mergeSchema`, so the table may gain
# MAGIC `imo_number`. The stream itself is in `vessels_stream.py`; see there for why.

# COMMAND ----------

def land_vessels(n):
    for f in dbutils.fs.ls(f"{SRC}/vessels/batch_{n}"):
        dbutils.fs.cp(f.path, f"{WORK}/vessels_landing/{f.name}")


def run_vessels(max_attempts=3):
    """Run the stream until it succeeds, as a job's retry policy would."""
    errors = []
    for _ in range(max_attempts):
        try:
            dbutils.notebook.run("./vessels_stream", 900)
            return errors
        except Exception as e:
            errors.append(str(e)[:200])
    raise RuntimeError(f"vessels stream failed {max_attempts} times: {errors}")


land_vessels(1)
first = run_vessels()
land_vessels(2)
second = run_vessels()
print("attempts that failed before succeeding:", len(first), "then", len(second), "(expect 0 then 1)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Manifests: `rowTag`, and attributes without the `_`

# COMMAND ----------

(spark.readStream.format("cloudFiles")
    .option("cloudFiles.format", "xml")
    .option("cloudFiles.schemaLocation", sl("ferry_manifests"))
    .option("rowTag", "manifest")
    .option("attributePrefix", "")
    .option("cloudFiles.inferColumnTypes", "true")
    .load(f"{SRC}/manifests")
 .writeStream
    .option("checkpointLocation", cp("ferry_manifests"))
    .trigger(availableNow=True)
    .toTable("ferry_manifests")
    .awaitTermination())

# COMMAND ----------

# MAGIC %md
# MAGIC ## Crossings: ORC needs evolution mode `none`

# COMMAND ----------

(spark.readStream.format("cloudFiles")
    .option("cloudFiles.format", "orc")
    .option("cloudFiles.schemaLocation", sl("ferry_crossings"))
    .option("cloudFiles.schemaEvolutionMode", "none")
    .load(f"{SRC}/crossings")
 .writeStream
    .option("checkpointLocation", cp("ferry_crossings"))
    .trigger(availableNow=True)
    .toTable("ferry_crossings")
    .awaitTermination())

# COMMAND ----------

# MAGIC %md
# MAGIC ## Scans: images only, without their bytes

# COMMAND ----------

(spark.readStream.format("cloudFiles")
    .option("cloudFiles.format", "binaryFile")
    .option("cloudFiles.schemaLocation", sl("ferry_scans"))
    .option("pathGlobFilter", "*.jpg")
    .load(f"{SRC}/scans")
    .select("path", "modificationTime", "length")
 .writeStream
    .option("checkpointLocation", cp("ferry_scans"))
    .trigger(availableNow=True)
    .toTable("ferry_scans")
    .awaitTermination())

# COMMAND ----------

# MAGIC %md
# MAGIC ## Emit the fixtures the tests assert against

# COMMAND ----------

for t in TABLES:
    print(f"{t:16}", spark.table(t).count(), spark.table(t).schema.simpleString())

tk, vs, mf, cr, sc = (spark.table(t) for t in TABLES)


def one(df, cond, cols):
    r = df.where(cond).collect()
    assert len(r) == 1, cond
    return {c: (r[0][c].isoformat() if hasattr(r[0][c], "isoformat") else
                (float(r[0][c]) if r[0][c] is not None and type(r[0][c]).__name__ == "Decimal" else r[0][c]))
            for c in cols}


fixtures = {
    "_comment": "Generated by solutions/ASSOC-S2-AUTO-LOADER/solution.py against the seeded s2_al_assess data. The tests assert against these, so they never need the solution present. Regenerate only if the generator's seed changes.",
    "tickets": {
        "rows": tk.count(),
        "null_fares": tk.where("fare_gbp IS NULL").count(),
        "rescued_fares": sorted(r[0] for r in tk.where("_rescued_data IS NOT NULL").select(F.expr("_rescued_data:fare_gbp")).collect()),
        "null_remarks": tk.where("remarks IS NULL").count(),
        "multiline_remarks": tk.where("remarks LIKE '%\n%'").count(),
        "min_departs": tk.agg(F.min("departs")).first()[0].isoformat(),
        "max_departs": tk.agg(F.max("departs")).first()[0].isoformat(),
        "fare_total": float(tk.agg(F.sum("fare_gbp")).first()[0]),
        "probes": {k: one(tk, f"ticket_no = '{k}'", ["route", "vessel", "departs", "fare_gbp", "passengers", "remarks"])
                   for k in ("T0000001", "T0000006", "T0000120")},
    },
    "vessels": {
        "rows": vs.count(),
        "with_imo": vs.where("imo_number IS NOT NULL").count(),
        "loads": spark.sql("DESCRIBE HISTORY ferry_vessels").where("operation = 'STREAMING UPDATE'")
                      .where("operationMetrics.numOutputRows > 0").count(),
        "probes": {k: one(vs, f"vessel_code = '{k}'", ["name", "built", "decks", "imo_number"])
                   for k in ("V01", "V08")},
        "engine_make_v01": vs.where("vessel_code = 'V01'").select("engine.make").first()[0],
    },
    "manifests": {
        "rows": mf.count(),
        "hazardous": mf.where("hazardous").count(),
        "cars_total": mf.agg(F.sum("cars")).first()[0],
        "probes": {k: one(mf, f"crossing = '{k}'", ["route", "cars", "freight_units", "hazardous"]) for k in ("X0001", "X0018")},
    },
    "crossings": {
        "rows": cr.count(),
        "probes": {k: one(cr, f"crossing = '{k}'", ["vessel", "departed_at", "load_pct"]) for k in ("X0001", "X0018")},
    },
    "scans": {
        "rows": sc.count(),
        "bytes_total": sc.agg(F.sum("length")).first()[0],
    },
}
print(json.dumps(fixtures, indent=2))
dbutils.notebook.exit(json.dumps(fixtures))
