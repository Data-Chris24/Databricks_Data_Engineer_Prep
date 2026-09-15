# Databricks notebook source
# MAGIC %md
# MAGIC # PRO-S2 — Data Ingestion & Acquisition assignment
# MAGIC
# MAGIC The task and the output contract are in the next cell (the same text as `README.md` in the repo).
# MAGIC
# MAGIC Produce:
# MAGIC - `workspace.de_prep.pro_s2_scans_bronze` — append-only, every delivered record
# MAGIC - `workspace.de_prep.pro_s2_scans` — one row per scan, latest revision

# COMMAND ----------

# MAGIC %md
# MAGIC <!-- task:begin  generated from README.md by tools/sync_assignment_tasks.py; edit the README, then re-run it -->
# MAGIC ## Assignment — `PRO-S2` Data Ingestion & Acquisition
# MAGIC
# MAGIC **Objectives:** `PRO-S2-O1`, `PRO-S2-O2`
# MAGIC
# MAGIC ### Before you start
# MAGIC
# MAGIC Work both lessons in `notebooks/lessons/professional/S2/`, and generate the data
# MAGIC (the study app generates the data the first time you open this section; `databricks bundle run generate_datasets_pro_s2 -t free` does the same from a terminal).
# MAGIC
# MAGIC > **In the lesson, the sources agreed with each other.** Three formats, same column
# MAGIC > order, same types, each record delivered once — so `union` and `unionByName` gave
# MAGIC > the same answer and a plain append was correct. None of that holds here.
# MAGIC
# MAGIC ### The task
# MAGIC
# MAGIC Five drop zones under `/Volumes/workspace/de_prep/raw/pro_s2/assess/`:
# MAGIC
# MAGIC | Path | Format |
# MAGIC |---|---|
# MAGIC | `assess/json` | JSON |
# MAGIC | `assess/parquet` | Parquet |
# MAGIC | `assess/avro` | Avro |
# MAGIC | `assess/csv` | CSV, with a header |
# MAGIC | `assess/xml` | XML |
# MAGIC
# MAGIC Between them they deliver 660 records covering 600 distinct scans. Land all of it in
# MAGIC an append-only bronze table, then produce a silver table with one row per scan.
# MAGIC
# MAGIC **The schemas are not documented here on purpose.** Reading them off the sources is
# MAGIC part of the task, and the sources do not agree — on column order, on types, or on
# MAGIC how many times they send a record.
# MAGIC
# MAGIC ### The output contract
# MAGIC
# MAGIC Both tables share this schema, in this order:
# MAGIC
# MAGIC | Column | Type | Meaning |
# MAGIC |---|---|---|
# MAGIC | `scan_id` | `STRING` | business key |
# MAGIC | `facility` | `STRING` | one of LEEDS, DUBLIN, PORTO, MALMO, LYON |
# MAGIC | `carrier` | `STRING` | one of northwind, brightline, kestrel |
# MAGIC | `status` | `STRING` | received, in_transit, out_for_delivery, delivered |
# MAGIC | `weight_kg` | `DOUBLE` | |
# MAGIC | `scanned_at` | `TIMESTAMP` | |
# MAGIC | `revision` | `INT` | 1 for an original, higher for a correction |
# MAGIC | `route_code` | `STRING` | only one source sends it; `NULL` elsewhere |
# MAGIC | `source_format` | `STRING` | which drop zone this record came from |
# MAGIC
# MAGIC **`workspace.de_prep.pro_s2_scans_bronze`** — append-only. Every delivered record,
# MAGIC corrections *and* the originals they supersede.
# MAGIC
# MAGIC **`workspace.de_prep.pro_s2_scans`** — one row per `scan_id`: the highest `revision`
# MAGIC delivered for that scan.
# MAGIC
# MAGIC #### Requirements
# MAGIC
# MAGIC 1. **Every source lands.** If a format is missing from `source_format`, its reader
# MAGIC    needed an option you did not pass.
# MAGIC 2. **Columns go where their names say.** Two sources ship the same columns in a
# MAGIC    different order, and the values are all strings, so nothing will error.
# MAGIC 3. **No value is lost to parsing.** No null `scanned_at`, no null `weight_kg`.
# MAGIC 4. **Bronze keeps the duplicates. Silver resolves them.** Those are different jobs;
# MAGIC    don't do the second one in the first table.
# MAGIC 5. **Pin your types.** A union keeps the widest type it is given, so one source
# MAGIC    inferring `revision` as a `BIGINT` is enough to change the table's schema. State
# MAGIC    the types you want rather than accepting what the union settled on.
# MAGIC 6. Column order matters — the tests compare the whole schema.
# MAGIC
# MAGIC ### Grading
# MAGIC
# MAGIC ```bash
# MAGIC databricks bundle run grade_pro_s2 -t free
# MAGIC ```
# MAGIC
# MAGIC The tests are authoritative. The advisory AI review (`grading/rubrics/PRO-S2.yaml`)
# MAGIC judges whether you read each format on its own terms or forced them all through one
# MAGIC reader, and whether bronze is genuinely append-only.
# MAGIC <!-- task:end -->

# COMMAND ----------

from pyspark.sql import Window
from pyspark.sql import functions as F

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")
ROOT = "/Volumes/workspace/de_prep/raw/pro_s2/assess"

display(dbutils.fs.ls(ROOT))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Read each source and look at what you got
# MAGIC
# MAGIC Check the column **order** and the column **types**, not just the names. Two of
# MAGIC these will union together without complaining and still be wrong.

# COMMAND ----------

# TODO: one reader per format


# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Bronze — append everything

# COMMAND ----------

# TODO
# bronze.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable("pro_s2_scans_bronze")


# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Silver — one row per scan
# MAGIC
# MAGIC Some scans were sent twice. Decide which copy wins, and be able to say why.

# COMMAND ----------

# TODO
# silver.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable("pro_s2_scans")


# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Check yourself before you grade
# MAGIC
# MAGIC Three quick ones that catch most of the ways this goes quietly wrong:
# MAGIC
# MAGIC - every `facility` value is a real facility
# MAGIC - no null `scanned_at`
# MAGIC - bronze row count > silver row count, by exactly the number of corrections

# COMMAND ----------

# TODO
