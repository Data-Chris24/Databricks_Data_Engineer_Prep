# Databricks notebook source
# MAGIC %md
# MAGIC # Schema evolution — and why this is a separate notebook
# MAGIC
# MAGIC **Objective `ASSOC-S2-O3`**, second half: schema *evolution*.
# MAGIC
# MAGIC Run `02_auto_loader.py` first — this continues from the landing area it leaves
# MAGIC behind.
# MAGIC
# MAGIC ## Read this before running
# MAGIC
# MAGIC With `schemaEvolutionMode = addNewColumns`, Auto Loader **deliberately fails**
# MAGIC the first time it meets a new column:
# MAGIC
# MAGIC ```
# MAGIC [UNKNOWN_FIELD_EXCEPTION.NEW_FIELDS_IN_FILE] Encountered unknown fields
# MAGIC during parsing: [channel], which can be fixed by an automatic retry: true
# MAGIC ```
# MAGIC
# MAGIC Note the last clause — *fixed by an automatic retry*. The failure **is** the
# MAGIC mechanism: Auto Loader records the wider schema, stops so a human notices, and
# MAGIC succeeds on restart.
# MAGIC
# MAGIC **So this notebook is expected to fail on its first run and succeed on its
# MAGIC second.** That is not a defect in the lesson. The bundle job that runs it sets
# MAGIC `max_retries: 2`, which is exactly how you would configure it in production —
# MAGIC and it is why schema evolution *looks* seamless in a real pipeline: a retry
# MAGIC policy absorbs the restart and nobody ever sees the exception.
# MAGIC
# MAGIC Catching the exception inside one notebook run does not work, incidentally.
# MAGIC Databricks tracks terminated streaming queries per notebook and fails the cell
# MAGIC with *"Some streams terminated before this command could finish!"* even when the
# MAGIC exception is handled, and `spark.streams.resetTerminated()` does not clear it.
# MAGIC The retry has to happen at the job level, which is where it belongs anyway.

# COMMAND ----------

CATALOG, SCHEMA = "workspace", "de_prep"
WORK = f"/Volumes/{CATALOG}/{SCHEMA}/raw/s2_teach_autoloader"
LANDING, CHECKPOINT, SCHEMA_LOC = f"{WORK}/landing", f"{WORK}/_checkpoint", f"{WORK}/_schema"

spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")

# Setup must be idempotent: this notebook runs more than once by design, and
# wiping state on retry would mean it never gets past the first failure.
try:
    dbutils.fs.ls(LANDING)
except Exception:
    raise RuntimeError("Run 02_auto_loader.py first - no landing area found.")

print("rows before:", spark.table("bronze_orders_al").count())

# COMMAND ----------

# MAGIC %md
# MAGIC ## Upstream adds a column
# MAGIC
# MAGIC Written only if absent, so a retry does not re-add it.

# COMMAND ----------

new_file = f"{LANDING}/orders_2026-03-03.csv"
existing = {f.name for f in dbutils.fs.ls(LANDING)}

if "orders_2026-03-03.csv" not in existing:
    dbutils.fs.put(new_file, "\n".join([
        "order_id,store,product_sku,quantity,unit_price,discount_pct,ordered_at,channel",
        "ORD-900001,boston,ESP-100,2,24.50,0.10,2026-03-03T09:15:00+00:00,web",
        "ORD-900002,denver,GRD-010,1,64.00,,2026-03-03T10:02:00+00:00,store",
        "ORD-900003,austin,MUG-021,4,8.75,0.05,2026-03-03T11:48:00+00:00,web",
    ]) + "\n", overwrite=True)
    print("added orders_2026-03-03.csv with a new `channel` column")
else:
    print("orders_2026-03-03.csv already present (this is a retry)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Run the stream
# MAGIC
# MAGIC Two options matter, and you need **both** — one on each side:
# MAGIC
# MAGIC | Setting | Side | Without it |
# MAGIC |---|---|---|
# MAGIC | `cloudFiles.schemaEvolutionMode` | reader | Auto Loader never notices the column |
# MAGIC | `mergeSchema` | writer | the Delta table rejects it, `DELTA_METADATA_MISMATCH` |
# MAGIC
# MAGIC The option that *looks* like "the schema evolution option" is only half the job.

# COMMAND ----------

(spark.readStream.format("cloudFiles")
    .option("cloudFiles.format", "csv")
    .option("cloudFiles.schemaLocation", SCHEMA_LOC)
    .option("header", "true")
    .option("cloudFiles.inferColumnTypes", "true")
    .option("cloudFiles.schemaEvolutionMode", "addNewColumns")   # reader side
    .option("rescuedDataColumn", "_rescued_data")
    .load(LANDING)
 .writeStream
    .option("checkpointLocation", CHECKPOINT)
    .option("mergeSchema", "true")                               # writer side
    .trigger(availableNow=True)
    .toTable("bronze_orders_al")
    .awaitTermination())

print("stream completed - the schema had already been recorded")

# COMMAND ----------

# MAGIC %md
# MAGIC ## What changed
# MAGIC
# MAGIC The earlier rows show `channel = NULL` — they predate the column. The three new
# MAGIC rows carry it. No table rebuild and no manual `ALTER TABLE`.

# COMMAND ----------

display(spark.sql("""
    SELECT
        CASE WHEN channel IS NULL THEN 'before evolution' ELSE 'after evolution' END AS era,
        count(*) AS rows
    FROM bronze_orders_al
    GROUP BY 1 ORDER BY 1
"""))

# COMMAND ----------

display(spark.sql("""
    SELECT order_id, store, channel FROM bronze_orders_al
    WHERE channel IS NOT NULL ORDER BY order_id
"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Takeaways
# MAGIC
# MAGIC - Schema evolution needs a setting on **both** the reader and the writer.
# MAGIC - `addNewColumns` signals a new column by failing once. Configure job retries
# MAGIC   and it becomes invisible; leave them off and your pipeline stops nightly.
# MAGIC - The checkpoint is what makes the restart safe — no row is loaded twice.
# MAGIC - Use `rescuedDataColumn` regardless. It is the difference between a
# MAGIC   surprising column and silently lost data.

# COMMAND ----------

# Clean up the scratch area now that the section is complete.
dbutils.fs.rm(WORK, True)
print("lesson scratch removed")
