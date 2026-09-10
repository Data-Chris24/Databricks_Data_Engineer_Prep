# Databricks notebook source
# MAGIC %md
# MAGIC # Auto Loader — schema enforcement and schema evolution
# MAGIC
# MAGIC **Objective `ASSOC-S2-O3`** — use Auto Loader with schema enforcement and
# MAGIC evolution in batch mode to land data in a Unity Catalog table.
# MAGIC
# MAGIC Same `s2_teach` orders as the previous lesson, so you can compare the two
# MAGIC approaches on identical input.
# MAGIC
# MAGIC Auto Loader is Structured Streaming underneath, but `availableNow` makes it
# MAGIC behave like a batch job: process whatever has arrived, then stop. You get
# MAGIC streaming's bookkeeping — a checkpoint that remembers exactly what was consumed
# MAGIC — on a schedule you control, without a cluster running all day.

# COMMAND ----------

CATALOG, SCHEMA = "workspace", "de_prep"
RAW = f"/Volumes/{CATALOG}/{SCHEMA}/raw/s2_teach"
WORK = f"/Volumes/{CATALOG}/{SCHEMA}/raw/s2_teach_autoloader"   # lesson scratch

spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")

# Start clean so the lesson is repeatable. The next lesson continues from the
# landing area this creates, so it is not removed at the end.
dbutils.fs.rm(WORK, True)
dbutils.fs.mkdirs(f"{WORK}/landing")
for f in dbutils.fs.ls(RAW):
    if f.name.endswith(".csv"):
        dbutils.fs.cp(f.path, f"{WORK}/landing/{f.name}")

CHECKPOINT = f"{WORK}/_checkpoint"
SCHEMA_LOC = f"{WORK}/_schema"
print("landing:", f"{WORK}/landing")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. The three locations Auto Loader needs
# MAGIC
# MAGIC | Location | Holds | Delete it and… |
# MAGIC |---|---|---|
# MAGIC | landing path | the source files | there is nothing to read |
# MAGIC | `cloudFiles.schemaLocation` | the inferred schema and its versions | the schema is re-inferred from scratch |
# MAGIC | `checkpointLocation` | which files have been processed | **every file is reprocessed** |
# MAGIC
# MAGIC Confusing the last two is a common exam trap. The checkpoint is what makes
# MAGIC reruns safe; the schema location is what makes evolution possible.
# MAGIC
# MAGIC ### Two different schema evolutions, and you need both
# MAGIC
# MAGIC | Setting | Side | What it does |
# MAGIC |---|---|---|
# MAGIC | `cloudFiles.schemaEvolutionMode` | **reader** | lets Auto Loader notice a new column in the files |
# MAGIC | `mergeSchema` on the writer | **writer** | lets the Delta table accept the new column |
# MAGIC
# MAGIC Set only the first and the read succeeds, then the write fails with
# MAGIC `DELTA_METADATA_MISMATCH`. It is an easy one to get wrong, because the option
# MAGIC that looks like "the schema evolution option" is only half of it. The next
# MAGIC notebook demonstrates both halves working.

# COMMAND ----------

spark.sql("DROP TABLE IF EXISTS bronze_orders_al")

stream = (spark.readStream
    .format("cloudFiles")
    .option("cloudFiles.format", "csv")
    .option("cloudFiles.schemaLocation", SCHEMA_LOC)
    # directory listing: fine at this scale. File notification scales better on
    # very large buckets but needs cloud resources Free Edition will not give you.
    .option("cloudFiles.useNotifications", "false")
    .option("header", "true")
    # Without this every column is inferred as STRING. With it, Auto Loader samples
    # the data to pick types - and still records anything unparseable rather than
    # dropping it.
    .option("cloudFiles.inferColumnTypes", "true")
    .option("cloudFiles.schemaEvolutionMode", "addNewColumns")
    .option("rescuedDataColumn", "_rescued_data")
    .load(f"{WORK}/landing"))

(stream.writeStream
    .option("checkpointLocation", CHECKPOINT)
    # The READER evolving is not enough - the Delta table has to accept the wider
    # schema too. Without this, section 3 fails with DELTA_METADATA_MISMATCH.
    .option("mergeSchema", "true")
    .trigger(availableNow=True)      # batch mode: drain what is there, then stop
    .toTable("bronze_orders_al")
    .awaitTermination())

print("rows after first run:", spark.table("bronze_orders_al").count())
display(spark.table("bronze_orders_al").limit(5))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Re-running processes nothing
# MAGIC
# MAGIC The checkpoint already lists these files, so the second run reads no new data —
# MAGIC the same idempotence `COPY INTO` gave us, by a different mechanism.

# COMMAND ----------

def run_once():
    (spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "csv")
        .option("cloudFiles.schemaLocation", SCHEMA_LOC)
        .option("header", "true")
        .option("cloudFiles.inferColumnTypes", "true")
        .option("cloudFiles.schemaEvolutionMode", "addNewColumns")
        .option("rescuedDataColumn", "_rescued_data")
        .load(f"{WORK}/landing")
     .writeStream
        .option("checkpointLocation", CHECKPOINT)
        .option("mergeSchema", "true")
        .trigger(availableNow=True)
        .toTable("bronze_orders_al")
        .awaitTermination())

run_once()
print("rows after re-running:", spark.table("bronze_orders_al").count())

# COMMAND ----------

# MAGIC %md
# MAGIC ## What you have so far
# MAGIC
# MAGIC | | `COPY INTO` | Auto Loader |
# MAGIC |---|---|---|
# MAGIC | Tracks processed files in | table metadata | a checkpoint |
# MAGIC | Schema | must exist, enforced | inferred, can evolve |
# MAGIC | Scale | thousands of files | millions |
# MAGIC | Best for | predictable periodic loads | continuous or drifting sources |
# MAGIC
# MAGIC `_rescued_data` is worth remembering separately: anything Auto Loader cannot fit
# MAGIC into the schema lands there rather than being dropped, so a malformed batch
# MAGIC costs you a column to inspect, not the records themselves.
# MAGIC
# MAGIC **Next:** `03_schema_evolution.py` handles the case this notebook avoided — a
# MAGIC column appearing mid-stream. It is a separate notebook for a real reason,
# MAGIC explained there.

# COMMAND ----------

# The landing area persists for the next lesson. Nothing here touches s2_teach.
print("done - continue with 03_schema_evolution.py")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Next
# MAGIC
# MAGIC Continue with the next lesson notebook: [03_schema_evolution](./03_schema_evolution).
# MAGIC
# MAGIC When the lessons are done, open the graded assignment: [ASSOC-S2 assignment notebook](../../../assignments/ASSOC-S2/assignment) · [the task](../../../assignments/ASSOC-S2/README.md).
