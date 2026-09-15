# Databricks notebook source
# MAGIC %md
# MAGIC # ASSOC-S4 assignment — your work goes here
# MAGIC
# MAGIC The task and the output contract are in the next cell (the same text as `README.md` in the repo).
# MAGIC
# MAGIC **The lesson's linear chain will not survive this source. One file has a value that will not cast, and there is a directory the main glob never looks at.**
# MAGIC
# MAGIC When you are done, go back to the study app and press **Grade my assignment**.
# MAGIC Each failing check says what it expected and why.

# COMMAND ----------

# MAGIC %md
# MAGIC <!-- task:begin  generated from README.md by tools/sync_assignment_tasks.py; edit the README, then re-run it -->
# MAGIC ## Assignment — `ASSOC-S4` Working with Lakeflow Jobs
# MAGIC
# MAGIC **Objectives:** `ASSOC-S4-O1`, `O2`, `O3`, `O4`
# MAGIC
# MAGIC ### Before you start
# MAGIC
# MAGIC Work the two lessons in `notebooks/lessons/associate/S4/`, and generate the data
# MAGIC (the study app generates the data the first time you open this section; `databricks bundle run generate_datasets_assoc_s4 -t free` does the same from a terminal).
# MAGIC
# MAGIC > **The lesson's linear chain will not survive this source.** One region's file
# MAGIC > contains a value that will not cast, and a chain that reads everything at once dies
# MAGIC > with it. There is also a directory the lesson never looked at.
# MAGIC
# MAGIC ### The task
# MAGIC
# MAGIC Build a pipeline over `/Volumes/workspace/de_prep/raw/s4_assess/` that publishes
# MAGIC regional order data — **without letting one bad region stop the others**.
# MAGIC
# MAGIC ### The output contract
# MAGIC
# MAGIC **`workspace.de_prep.s4_gold_regional_orders`**
# MAGIC
# MAGIC | Column | Type |
# MAGIC |---|---|
# MAGIC | `order_id` | `STRING` |
# MAGIC | `region` | `STRING` |
# MAGIC | `units` | `INT` |
# MAGIC | `ordered_on` | `DATE` |
# MAGIC
# MAGIC **`workspace.de_prep.s4_quarantine_orders`** — every row that could not be published,
# MAGIC with its raw values preserved and the file it came from.
# MAGIC
# MAGIC | Column | Type |
# MAGIC |---|---|
# MAGIC | `order_id` | `STRING` |
# MAGIC | `region` | `STRING` |
# MAGIC | `raw_units` | `STRING` |
# MAGIC | `raw_ordered_on` | `STRING` |
# MAGIC | `source_file` | `STRING` |
# MAGIC
# MAGIC #### Requirements
# MAGIC
# MAGIC 1. **A bad row must not stop the pipeline.** Publish everything that is valid.
# MAGIC 2. **Nothing is silently dropped.** Every row that does not publish appears in
# MAGIC    quarantine with its original values.
# MAGIC 3. **Include the late arrivals.** There is a subdirectory the main glob will not pick
# MAGIC    up. Its rows belong in the published table.
# MAGIC 4. **Be idempotent.** The grader runs your job **twice**. Row counts must be identical
# MAGIC    after the second run.
# MAGIC 5. Column order matters — the tests compare the whole schema.
# MAGIC
# MAGIC ### Grading
# MAGIC
# MAGIC ```bash
# MAGIC databricks bundle run grade_assoc_s4 -t free --profile FREE
# MAGIC ```
# MAGIC
# MAGIC ### Hints
# MAGIC
# MAGIC <details><summary>My job fails reading the files</summary>
# MAGIC
# MAGIC Requirement 1. What happens if you read with a declared `INT` schema and one value is
# MAGIC `"twelve"`? Read as text and separate good from bad yourself — `try_cast` returns null
# MAGIC where `cast` raises.
# MAGIC </details>
# MAGIC
# MAGIC <details><summary>I published 360 rows</summary>
# MAGIC
# MAGIC Two things are missing: the 89 good rows from the region that also has a bad one, and
# MAGIC the late arrivals.
# MAGIC </details>
# MAGIC
# MAGIC <details><summary>The second run doubled my data</summary>
# MAGIC
# MAGIC Requirement 4. `append` is not idempotent.
# MAGIC </details>
# MAGIC <!-- task:end -->

# COMMAND ----------

from pyspark.sql import functions as F

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")
RAW = "/Volumes/workspace/de_prep/raw/s4_assess"
GOLD = "s4_gold_regional_orders"
QUARANTINE = "s4_quarantine_orders"

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 0 — look at the landing area, including subdirectories
# MAGIC
# MAGIC Requirement 3: the late arrivals live somewhere the obvious glob misses.

# COMMAND ----------

for f in dbutils.fs.ls(RAW):
    print(f.path, f.size)
# What is inside any subdirectory?

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1 — read everything as text, remembering the file
# MAGIC
# MAGIC Requirement 1: a value that will not cast must not stop the read. Read as strings and keep `_metadata.file_path` (or `input_file_name()`) so quarantine can cite the file.

# COMMAND ----------

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2 — separate what publishes from what does not
# MAGIC
# MAGIC `try_cast` returns null where `cast` raises. A row with any failed cast goes to quarantine with its raw values.

# COMMAND ----------

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3 — write both tables, idempotently
# MAGIC
# MAGIC Requirement 4: the grader runs this twice. `append` doubles the data; choose a mode that does not.

# COMMAND ----------

# COMMAND ----------

# MAGIC %md
# MAGIC ## Check yourself before grading

# COMMAND ----------

# print("published:", spark.table(GOLD).count(), "| quarantined:", spark.table(QUARANTINE).count())
# Run this notebook a second time: both counts must be unchanged.
