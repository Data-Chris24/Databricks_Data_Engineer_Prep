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
# MAGIC ### Auto Loader runs fine in a notebook
# MAGIC
# MAGIC Nothing here says otherwise — `02_auto_loader.py` is a notebook and it works.
# MAGIC What needs care is narrower: **what happens the first time a new column
# MAGIC appears.**
# MAGIC
# MAGIC With `schemaEvolutionMode = addNewColumns`, Auto Loader **deliberately fails**
# MAGIC when it first meets one:
# MAGIC
# MAGIC ```
# MAGIC [UNKNOWN_FIELD_EXCEPTION.NEW_FIELDS_IN_FILE] Encountered unknown fields
# MAGIC during parsing: [channel], which can be fixed by an automatic retry: true
# MAGIC ```
# MAGIC
# MAGIC Note the last clause — *fixed by an automatic retry*. The failure **is** the
# MAGIC mechanism: Auto Loader records the wider schema, stops so a human notices, and
# MAGIC succeeds next time. Something just has to run it again.
# MAGIC
# MAGIC | Where you run it | New column appears | Why |
# MAGIC |---|---|---|
# MAGIC | **Notebook, interactively** | works | the stream fails once, **you re-run the cell** — you are the retry |
# MAGIC | **Job task with `max_retries`** | works | the retry policy restarts it and nobody sees the failure |
# MAGIC | Notebook run as a job task, no retries | fails | nothing restarts it |
# MAGIC | `try`/`except` inside one notebook run | fails | see below |
# MAGIC
# MAGIC **If you are working through this interactively, just run the stream cell
# MAGIC twice.** That is the whole trick, and it is worth doing by hand once so the
# MAGIC mechanism is not a mystery later.
# MAGIC
# MAGIC ### Why you cannot simply catch the exception
# MAGIC
# MAGIC An obvious idea that does not work: wrap the stream in `try`/`except` and
# MAGIC restart it in the handler. Databricks tracks terminated streaming queries per
# MAGIC notebook and fails the cell with
# MAGIC *"Some streams terminated before this command could finish!"* **even when the
# MAGIC exception was caught**, and `spark.streams.resetTerminated()` does not clear it.
# MAGIC The restart has to come from outside the notebook run — which is where it
# MAGIC belongs anyway.
# MAGIC
# MAGIC ### How this notebook is run
# MAGIC
# MAGIC The bundle job runs it as a task with `max_retries: 2`, so **it is expected to
# MAGIC fail on attempt 0 and succeed on attempt 1.** That is not a defect in the
# MAGIC lesson; it is the production configuration, and it is the reason schema
# MAGIC evolution *looks* seamless in a real pipeline.
# MAGIC
# MAGIC Setup below is written to be idempotent for exactly that reason — a retry must
# MAGIC not wipe the state it needs.

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
# MAGIC
# MAGIC ### The failures this section causes on purpose
# MAGIC
# MAGIC `content/lessons/associate/S2/errors-worth-meeting.md` collects all four, what
# MAGIC each one is protecting you from, and the exam-shaped question behind it:
# MAGIC
# MAGIC | Error | Protects you from |
# MAGIC |---|---|
# MAGIC | `DELTA_FAILED_TO_MERGE_FIELDS` | CSV text being silently coerced into your types |
# MAGIC | `UNKNOWN_FIELD_EXCEPTION.NEW_FIELDS_IN_FILE` | a source schema change nobody notices |
# MAGIC | `DELTA_METADATA_MISMATCH` | a typo silently becoming a column |
# MAGIC | `Some streams terminated…` | believing data loaded when the stream died |
# MAGIC
# MAGIC The general habit: when something fails on Databricks, ask *what would have
# MAGIC gone wrong if this had worked?*

# COMMAND ----------

# Clean up the scratch area now that the section is complete.
dbutils.fs.rm(WORK, True)
print("lesson scratch removed")
