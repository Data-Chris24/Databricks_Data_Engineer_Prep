# Databricks notebook source
# MAGIC %md
# MAGIC # Reference solution helper: one run of the vessels stream
# MAGIC
# MAGIC `solution.py` runs this with `dbutils.notebook.run` once per attempt. The run
# MAGIC after the second delivery fails by design (`addNewColumns` meeting `imo_number`),
# MAGIC and a stream that fails while running fails its notebook even when caught, so the
# MAGIC attempt lives here and the solution plays the job's retry.

# COMMAND ----------

CATALOG, SCHEMA = "workspace", "de_prep"
WORK = f"/Volumes/{CATALOG}/{SCHEMA}/raw/s2_al_work"
TABLE = "ferry_vessels"

spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")

(spark.readStream.format("cloudFiles")
    .option("cloudFiles.format", "json")                                # reader
    .option("cloudFiles.schemaLocation", f"{WORK}/{TABLE}/_schema")     # reader
    .option("multiLine", "true")                                       # reader: one array per file
    .option("cloudFiles.inferColumnTypes", "true")                     # reader: engine as a struct
    .option("cloudFiles.schemaEvolutionMode", "addNewColumns")         # reader: the default, said out loud
    .load(f"{WORK}/vessels_landing")
 .writeStream
    .option("checkpointLocation", f"{WORK}/{TABLE}/_checkpoint")       # writer
    .option("mergeSchema", "true")                                     # writer: let the table gain imo_number
    .trigger(availableNow=True)                                        # writer
    .toTable(TABLE)
    .awaitTermination())

dbutils.notebook.exit("ok")
