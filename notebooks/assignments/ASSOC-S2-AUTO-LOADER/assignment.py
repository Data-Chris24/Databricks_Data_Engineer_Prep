# Databricks notebook source
# MAGIC %md
# MAGIC # ASSOC-S2-AUTO-LOADER assignment (optional) — your work goes here
# MAGIC
# MAGIC The task and the output contract are in the next cell (the same text as `README.md` in the repo).
# MAGIC
# MAGIC **The lesson's code will not solve this.** Each source is exported differently
# MAGIC from the lesson's. Copying `04_optional_auto_loader_deep_dive` and changing the
# MAGIC paths produces tables that fail the tests, and each failure names the assumption
# MAGIC that broke.
# MAGIC
# MAGIC Grade your work with:
# MAGIC ```
# MAGIC databricks bundle run grade_assoc_s2_auto_loader -t free --profile FREE
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC <!-- task:begin  generated from README.md by tools/sync_assignment_tasks.py; edit the README, then re-run it -->
# MAGIC ## Assignment — `ASSOC-S2-AUTO-LOADER` Five sources, five formats (optional)
# MAGIC
# MAGIC **Objectives exercised:** `ASSOC-S2-O1`, `ASSOC-S2-O3`
# MAGIC
# MAGIC **Optional.** It goes with the optional lesson `04_optional_auto_loader_deep_dive`
# MAGIC and does not count toward completing Section 2. Pass the section's own assignment
# MAGIC for that.
# MAGIC
# MAGIC ### Before you start
# MAGIC
# MAGIC 1. Work through `notebooks/lessons/associate/S2/04_optional_auto_loader_deep_dive`.
# MAGIC 2. The data comes with the section's datasets. If
# MAGIC    `/Volumes/workspace/de_prep/raw/s2_al_assess/` is missing, run the lesson's first
# MAGIC    cell (it generates it) or `databricks bundle run generate_datasets_assoc_s2 -t free`.
# MAGIC
# MAGIC > **The lesson's code will not solve this.** Every source is a format the lesson
# MAGIC > covered, exported differently. Copying the lesson's streams and changing the paths
# MAGIC > produces tables that fail the tests. Look at each source before you write a stream
# MAGIC > for it.
# MAGIC
# MAGIC ### The task
# MAGIC
# MAGIC A ferry operator drops its exports in `/Volumes/workspace/de_prep/raw/s2_al_assess/`:
# MAGIC
# MAGIC | Folder | Holds |
# MAGIC |---|---|
# MAGIC | `tickets/` | ticket sales, CSV |
# MAGIC | `vessels/batch_1/`, `vessels/batch_2/` | the fleet register, JSON, in two deliveries |
# MAGIC | `manifests/` | what each crossing carried, XML |
# MAGIC | `crossings/` | each crossing's departure and load, ORC |
# MAGIC | `scans/` | scanned boarding cards, among other files |
# MAGIC
# MAGIC Load each one into its own table **with Auto Loader** (`cloudFiles`, trigger
# MAGIC `availableNow`). You are not told the files' layout: opening them is part of the job.
# MAGIC
# MAGIC ### The output contract
# MAGIC
# MAGIC Five tables in `workspace.de_prep`. Every one must be written by an Auto Loader
# MAGIC stream: the tests read each table's history and expect `STREAMING UPDATE`, so a batch
# MAGIC `spark.read` and `saveAsTable` fails them even with the right rows.
# MAGIC
# MAGIC Every stream keeps its state under `/Volumes/workspace/de_prep/raw/s2_al_work/<table>/`:
# MAGIC its checkpoint in `_checkpoint` and its schema location in `_schema`.
# MAGIC
# MAGIC #### `workspace.de_prep.ferry_tickets`
# MAGIC
# MAGIC | Column | Type | Meaning |
# MAGIC |---|---|---|
# MAGIC | `ticket_no` | `STRING` | The ticket, unique per row |
# MAGIC | `route` | `STRING` | e.g. `DOV-CAL` |
# MAGIC | `vessel` | `STRING` | The vessel code |
# MAGIC | `departs` | `TIMESTAMP` | Scheduled departure. **Never null** |
# MAGIC | `fare_gbp` | `DECIMAL(8,2)` | The fare. Null where the export holds something that is not a price |
# MAGIC | `passengers` | `INT` | Passengers on the ticket |
# MAGIC | `remarks` | `STRING` | Desk remarks, possibly over several lines. **Null where there are none** |
# MAGIC | `_rescued_data` | `STRING` | What did not fit, kept by Auto Loader |
# MAGIC
# MAGIC #### `workspace.de_prep.ferry_vessels`
# MAGIC
# MAGIC | Column | Type | Meaning |
# MAGIC |---|---|---|
# MAGIC | `vessel_code` | `STRING` | The vessel, unique per row |
# MAGIC | `name` | `STRING` | Its name |
# MAGIC | `built` | `BIGINT` | Year built |
# MAGIC | `decks` | `BIGINT` | Number of decks |
# MAGIC | `engine` | `STRUCT<kw: BIGINT, make: STRING>` | A struct you can query as `engine.make`, not a JSON string |
# MAGIC | `imo_number` | `STRING` | Only the second delivery has it. **Null for the vessels in the first** |
# MAGIC
# MAGIC Column order is not checked for this table. Any other columns (such as
# MAGIC `_rescued_data`) may stay.
# MAGIC
# MAGIC #### `workspace.de_prep.ferry_manifests`
# MAGIC
# MAGIC | Column | Type | Meaning |
# MAGIC |---|---|---|
# MAGIC | `crossing` | `STRING` | The crossing, unique per row |
# MAGIC | `route` | `STRING` | Its route |
# MAGIC | `cars` | `BIGINT` | Cars carried |
# MAGIC | `freight_units` | `BIGINT` | Freight units carried |
# MAGIC | `hazardous` | `BOOLEAN` | Whether it carried hazardous goods |
# MAGIC | `_rescued_data` | `STRING` | What did not fit |
# MAGIC
# MAGIC Column order is not checked for this table.
# MAGIC
# MAGIC #### `workspace.de_prep.ferry_crossings`
# MAGIC
# MAGIC | Column | Type | Meaning |
# MAGIC |---|---|---|
# MAGIC | `crossing` | `STRING` | The crossing, unique per row |
# MAGIC | `vessel` | `STRING` | Which vessel sailed it |
# MAGIC | `departed_at` | `TIMESTAMP` | When it left |
# MAGIC | `load_pct` | `DOUBLE` | How full it was |
# MAGIC
# MAGIC #### `workspace.de_prep.ferry_scans`
# MAGIC
# MAGIC | Column | Type | Meaning |
# MAGIC |---|---|---|
# MAGIC | `path` | `STRING` | The scan's file |
# MAGIC | `modificationTime` | `TIMESTAMP` | When it was written |
# MAGIC | `length` | `BIGINT` | Its size in bytes |
# MAGIC
# MAGIC #### Requirements
# MAGIC
# MAGIC 1. **Auto Loader, every table.** Each table's history shows `STREAMING UPDATE`.
# MAGIC 2. **The right folder for each location.** Each stream's checkpoint is
# MAGIC    `s2_al_work/<table>/_checkpoint` and its schema location `s2_al_work/<table>/_schema`.
# MAGIC    The tests look inside both, so a swapped pair fails.
# MAGIC 3. **Tickets parse completely.** One row per ticket, multi-line remarks intact,
# MAGIC    `departs` never null, `N/A` read as null, and the fares that are not prices left
# MAGIC    null in `fare_gbp` with their original text in `_rescued_data`.
# MAGIC 4. **The vessels arrive in two deliveries, and so must your stream.** Land
# MAGIC    `batch_1` and run the stream; then land `batch_2` and run it again (the starter
# MAGIC    has a `land_vessels(n)` helper). The second run meets a field the first never
# MAGIC    saw. The table's history must show both loads, and `imo_number` must be filled for
# MAGIC    the second delivery only.
# MAGIC 5. **Manifests: one row per crossing**, with the attribute names as the contract
# MAGIC    spells them.
# MAGIC 6. **Scans: boarding-card images only, without their bytes.** The folder holds other
# MAGIC    files; none of them belongs in the table, and neither does a `content` column.
# MAGIC 7. **Column order matters** for `ferry_tickets`, `ferry_crossings` and
# MAGIC    `ferry_scans`. The tests use `assertSchemaEqual`.
# MAGIC
# MAGIC ### How you are graded
# MAGIC
# MAGIC **Unit tests — authoritative.** Run them with:
# MAGIC
# MAGIC ```bash
# MAGIC databricks bundle run grade_assoc_s2_auto_loader -t free --profile FREE
# MAGIC ```
# MAGIC
# MAGIC They check each table's schema and row count, that Auto Loader wrote it, both
# MAGIC locations of every stream, the parsed timestamps and the rescued fares, that the
# MAGIC vessels table evolved across two loads, and a few known values.
# MAGIC
# MAGIC **AI review — advisory, optional.** If you have attached a model (see
# MAGIC `docs/grading.md`), it also reviews *how* you did it: whether each option sits on the
# MAGIC reader or the writer for the right reason. It can never overturn a unit test result.
# MAGIC <!-- task:end -->

# COMMAND ----------

# MAGIC %md
# MAGIC <!-- hints:begin  generated from README.md by tools/sync_assignment_tasks.py; edit the README, then re-run it -->
# MAGIC #### Hints, if you want them
# MAGIC
# MAGIC One per cell below, each opening with the problem it answers, so you can read only the one you need. To put a hint away again, collapse its cell from the cell menu on its right - a collapsed cell shows its first line only.

# COMMAND ----------

# MAGIC %md
# MAGIC **Hint 1 - I do not know where to start**
# MAGIC
# MAGIC `dbutils.fs.head(path, 600)` on one file per folder. For each, write down the
# MAGIC separator or row element, how a missing value is written, and how a timestamp is
# MAGIC written. Those notes are your reader options.

# COMMAND ----------

# MAGIC %md
# MAGIC **Hint 2 - `departs` is null on every row**
# MAGIC
# MAGIC Inference did not recognise the date format, and a hint to `TIMESTAMP` cannot parse
# MAGIC it either: the original is in `_rescued_data`. There is a CSV reader option that
# MAGIC says how timestamps are written, in Spark's datetime pattern syntax.

# COMMAND ----------

# MAGIC %md
# MAGIC **Hint 3 - The vessels stream failed with `UNKNOWN_FIELD_EXCEPTION`**
# MAGIC
# MAGIC That is the second run meeting the new field, working as designed. Run the cell
# MAGIC again. If the run after that fails with `DELTA_METADATA_MISMATCH`, one of the two
# MAGIC schema-evolution settings is missing; lesson 04 section 5 has the table.

# COMMAND ----------

# MAGIC %md
# MAGIC **Hint 4 - The crossings stream fails before it starts**
# MAGIC
# MAGIC Read the error to the end: it names the option and the value it wants.

# COMMAND ----------

# MAGIC %md
# MAGIC **Hint 5 - I need to start a table again**
# MAGIC
# MAGIC Drop the table **and** delete its folder under `s2_al_work/`. Dropping only the table
# MAGIC leaves the checkpoint, which remembers every file as done, so the next run loads
# MAGIC nothing.
# MAGIC <!-- hints:end -->

# COMMAND ----------

CATALOG, SCHEMA = "workspace", "de_prep"
SRC = f"/Volumes/{CATALOG}/{SCHEMA}/raw/s2_al_assess"
WORK = f"/Volumes/{CATALOG}/{SCHEMA}/raw/s2_al_work"

spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")


def checkpoint(table):
    """Where the contract wants this table's stream to keep its checkpoint."""
    return f"{WORK}/{table}/_checkpoint"


def schema_location(table):
    """Where the contract wants this table's stream to keep its schema."""
    return f"{WORK}/{table}/_schema"


VESSELS_LANDING = f"{WORK}/vessels_landing"


def land_vessels(n):
    """Deliver vessels batch n (1 or 2) into the folder your vessels stream reads."""
    for f in dbutils.fs.ls(f"{SRC}/vessels/batch_{n}"):
        dbutils.fs.cp(f.path, f"{VESSELS_LANDING}/{f.name}")
    print("landed:", sorted(f.name for f in dbutils.fs.ls(VESSELS_LANDING)))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 0 — look at every source first
# MAGIC
# MAGIC For each folder: what is the separator or the row element, how is a missing value
# MAGIC written, how is a timestamp written, and what else is in the folder?
# MAGIC
# MAGIC <!-- contract: requirements: 3, 5, 6 -->
# MAGIC <!-- excerpt:begin  generated from README.md by tools/sync_assignment_tasks.py; edit the README or the contract marker above, then re-run it -->
# MAGIC
# MAGIC **What this step must satisfy** (from the contract at the top)
# MAGIC
# MAGIC **Requirement 3.** **Tickets parse completely.** One row per ticket, multi-line remarks intact,
# MAGIC `departs` never null, `N/A` read as null, and the fares that are not prices left
# MAGIC null in `fare_gbp` with their original text in `_rescued_data`.
# MAGIC
# MAGIC **Requirement 5.** **Manifests: one row per crossing**, with the attribute names as the contract
# MAGIC spells them.
# MAGIC
# MAGIC **Requirement 6.** **Scans: boarding-card images only, without their bytes.** The folder holds other
# MAGIC files; none of them belongs in the table, and neither does a `content` column.
# MAGIC <!-- excerpt:end -->

# COMMAND ----------

for folder in dbutils.fs.ls(SRC):
    print(folder.name)

# COMMAND ----------

# Open one file from each folder. dbutils.fs.head(path, 600) prints the start of a file.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1 — tickets (CSV)
# MAGIC
# MAGIC Label each option you set with the object it belongs to: reader or writer.
# MAGIC
# MAGIC <!-- contract: ferry_tickets; requirements: 1, 2, 3, 7 -->
# MAGIC <!-- excerpt:begin  generated from README.md by tools/sync_assignment_tasks.py; edit the README or the contract marker above, then re-run it -->
# MAGIC
# MAGIC **What this step must satisfy** (from the contract at the top)
# MAGIC
# MAGIC **`workspace.de_prep.ferry_tickets`**
# MAGIC
# MAGIC | Column | Type | Meaning |
# MAGIC |---|---|---|
# MAGIC | `ticket_no` | `STRING` | The ticket, unique per row |
# MAGIC | `route` | `STRING` | e.g. `DOV-CAL` |
# MAGIC | `vessel` | `STRING` | The vessel code |
# MAGIC | `departs` | `TIMESTAMP` | Scheduled departure. **Never null** |
# MAGIC | `fare_gbp` | `DECIMAL(8,2)` | The fare. Null where the export holds something that is not a price |
# MAGIC | `passengers` | `INT` | Passengers on the ticket |
# MAGIC | `remarks` | `STRING` | Desk remarks, possibly over several lines. **Null where there are none** |
# MAGIC | `_rescued_data` | `STRING` | What did not fit, kept by Auto Loader |
# MAGIC
# MAGIC **Requirement 1.** **Auto Loader, every table.** Each table's history shows `STREAMING UPDATE`.
# MAGIC
# MAGIC **Requirement 2.** **The right folder for each location.** Each stream's checkpoint is
# MAGIC `s2_al_work/<table>/_checkpoint` and its schema location `s2_al_work/<table>/_schema`.
# MAGIC The tests look inside both, so a swapped pair fails.
# MAGIC
# MAGIC **Requirement 3.** **Tickets parse completely.** One row per ticket, multi-line remarks intact,
# MAGIC `departs` never null, `N/A` read as null, and the fares that are not prices left
# MAGIC null in `fare_gbp` with their original text in `_rescued_data`.
# MAGIC
# MAGIC **Requirement 7.** **Column order matters** for `ferry_tickets`, `ferry_crossings` and
# MAGIC `ferry_scans`. The tests use `assertSchemaEqual`.
# MAGIC <!-- excerpt:end -->

# COMMAND ----------

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2 — vessels (JSON), in two deliveries
# MAGIC
# MAGIC Land batch 1 and run your stream. Then land batch 2 and run the same stream
# MAGIC again: expect the first attempt after the new field to fail, and the next to
# MAGIC succeed. Interactively, re-running the cell is the retry.
# MAGIC
# MAGIC <!-- contract: ferry_vessels; requirements: 1, 2, 4 -->
# MAGIC <!-- excerpt:begin  generated from README.md by tools/sync_assignment_tasks.py; edit the README or the contract marker above, then re-run it -->
# MAGIC
# MAGIC **What this step must satisfy** (from the contract at the top)
# MAGIC
# MAGIC **`workspace.de_prep.ferry_vessels`**
# MAGIC
# MAGIC | Column | Type | Meaning |
# MAGIC |---|---|---|
# MAGIC | `vessel_code` | `STRING` | The vessel, unique per row |
# MAGIC | `name` | `STRING` | Its name |
# MAGIC | `built` | `BIGINT` | Year built |
# MAGIC | `decks` | `BIGINT` | Number of decks |
# MAGIC | `engine` | `STRUCT<kw: BIGINT, make: STRING>` | A struct you can query as `engine.make`, not a JSON string |
# MAGIC | `imo_number` | `STRING` | Only the second delivery has it. **Null for the vessels in the first** |
# MAGIC
# MAGIC **Requirement 1.** **Auto Loader, every table.** Each table's history shows `STREAMING UPDATE`.
# MAGIC
# MAGIC **Requirement 2.** **The right folder for each location.** Each stream's checkpoint is
# MAGIC `s2_al_work/<table>/_checkpoint` and its schema location `s2_al_work/<table>/_schema`.
# MAGIC The tests look inside both, so a swapped pair fails.
# MAGIC
# MAGIC **Requirement 4.** **The vessels arrive in two deliveries, and so must your stream.** Land
# MAGIC `batch_1` and run the stream; then land `batch_2` and run it again (the starter
# MAGIC has a `land_vessels(n)` helper). The second run meets a field the first never
# MAGIC saw. The table's history must show both loads, and `imo_number` must be filled for
# MAGIC the second delivery only.
# MAGIC <!-- excerpt:end -->

# COMMAND ----------

land_vessels(1)

# COMMAND ----------

# your vessels stream: read VESSELS_LANDING

# COMMAND ----------

land_vessels(2)

# COMMAND ----------

# the same stream again (and again, if it stops on the new field)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3 — manifests (XML)
# MAGIC
# MAGIC <!-- contract: ferry_manifests; requirements: 1, 2, 5 -->
# MAGIC <!-- excerpt:begin  generated from README.md by tools/sync_assignment_tasks.py; edit the README or the contract marker above, then re-run it -->
# MAGIC
# MAGIC **What this step must satisfy** (from the contract at the top)
# MAGIC
# MAGIC **`workspace.de_prep.ferry_manifests`**
# MAGIC
# MAGIC | Column | Type | Meaning |
# MAGIC |---|---|---|
# MAGIC | `crossing` | `STRING` | The crossing, unique per row |
# MAGIC | `route` | `STRING` | Its route |
# MAGIC | `cars` | `BIGINT` | Cars carried |
# MAGIC | `freight_units` | `BIGINT` | Freight units carried |
# MAGIC | `hazardous` | `BOOLEAN` | Whether it carried hazardous goods |
# MAGIC | `_rescued_data` | `STRING` | What did not fit |
# MAGIC
# MAGIC **Requirement 1.** **Auto Loader, every table.** Each table's history shows `STREAMING UPDATE`.
# MAGIC
# MAGIC **Requirement 2.** **The right folder for each location.** Each stream's checkpoint is
# MAGIC `s2_al_work/<table>/_checkpoint` and its schema location `s2_al_work/<table>/_schema`.
# MAGIC The tests look inside both, so a swapped pair fails.
# MAGIC
# MAGIC **Requirement 5.** **Manifests: one row per crossing**, with the attribute names as the contract
# MAGIC spells them.
# MAGIC <!-- excerpt:end -->

# COMMAND ----------

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 4 — crossings (ORC)
# MAGIC
# MAGIC <!-- contract: ferry_crossings; requirements: 1, 2, 7 -->
# MAGIC <!-- excerpt:begin  generated from README.md by tools/sync_assignment_tasks.py; edit the README or the contract marker above, then re-run it -->
# MAGIC
# MAGIC **What this step must satisfy** (from the contract at the top)
# MAGIC
# MAGIC **`workspace.de_prep.ferry_crossings`**
# MAGIC
# MAGIC | Column | Type | Meaning |
# MAGIC |---|---|---|
# MAGIC | `crossing` | `STRING` | The crossing, unique per row |
# MAGIC | `vessel` | `STRING` | Which vessel sailed it |
# MAGIC | `departed_at` | `TIMESTAMP` | When it left |
# MAGIC | `load_pct` | `DOUBLE` | How full it was |
# MAGIC
# MAGIC **Requirement 1.** **Auto Loader, every table.** Each table's history shows `STREAMING UPDATE`.
# MAGIC
# MAGIC **Requirement 2.** **The right folder for each location.** Each stream's checkpoint is
# MAGIC `s2_al_work/<table>/_checkpoint` and its schema location `s2_al_work/<table>/_schema`.
# MAGIC The tests look inside both, so a swapped pair fails.
# MAGIC
# MAGIC **Requirement 7.** **Column order matters** for `ferry_tickets`, `ferry_crossings` and
# MAGIC `ferry_scans`. The tests use `assertSchemaEqual`.
# MAGIC <!-- excerpt:end -->

# COMMAND ----------

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 5 — scans (binaryFile)
# MAGIC
# MAGIC <!-- contract: ferry_scans; requirements: 1, 2, 6, 7 -->
# MAGIC <!-- excerpt:begin  generated from README.md by tools/sync_assignment_tasks.py; edit the README or the contract marker above, then re-run it -->
# MAGIC
# MAGIC **What this step must satisfy** (from the contract at the top)
# MAGIC
# MAGIC **`workspace.de_prep.ferry_scans`**
# MAGIC
# MAGIC | Column | Type | Meaning |
# MAGIC |---|---|---|
# MAGIC | `path` | `STRING` | The scan's file |
# MAGIC | `modificationTime` | `TIMESTAMP` | When it was written |
# MAGIC | `length` | `BIGINT` | Its size in bytes |
# MAGIC
# MAGIC **Requirement 1.** **Auto Loader, every table.** Each table's history shows `STREAMING UPDATE`.
# MAGIC
# MAGIC **Requirement 2.** **The right folder for each location.** Each stream's checkpoint is
# MAGIC `s2_al_work/<table>/_checkpoint` and its schema location `s2_al_work/<table>/_schema`.
# MAGIC The tests look inside both, so a swapped pair fails.
# MAGIC
# MAGIC **Requirement 6.** **Scans: boarding-card images only, without their bytes.** The folder holds other
# MAGIC files; none of them belongs in the table, and neither does a `content` column.
# MAGIC
# MAGIC **Requirement 7.** **Column order matters** for `ferry_tickets`, `ferry_crossings` and
# MAGIC `ferry_scans`. The tests use `assertSchemaEqual`.
# MAGIC <!-- excerpt:end -->

# COMMAND ----------

# COMMAND ----------

# MAGIC %md
# MAGIC ## Check yourself before grading
# MAGIC
# MAGIC <!-- contract: ferry_tickets; ferry_vessels; ferry_manifests; ferry_crossings; ferry_scans; requirements: 1, 2, 3, 4, 5, 6, 7 -->
# MAGIC <!-- excerpt:begin  generated from README.md by tools/sync_assignment_tasks.py; edit the README or the contract marker above, then re-run it -->
# MAGIC
# MAGIC **What this step must satisfy** (from the contract at the top)
# MAGIC
# MAGIC **`workspace.de_prep.ferry_tickets`**
# MAGIC
# MAGIC | Column | Type | Meaning |
# MAGIC |---|---|---|
# MAGIC | `ticket_no` | `STRING` | The ticket, unique per row |
# MAGIC | `route` | `STRING` | e.g. `DOV-CAL` |
# MAGIC | `vessel` | `STRING` | The vessel code |
# MAGIC | `departs` | `TIMESTAMP` | Scheduled departure. **Never null** |
# MAGIC | `fare_gbp` | `DECIMAL(8,2)` | The fare. Null where the export holds something that is not a price |
# MAGIC | `passengers` | `INT` | Passengers on the ticket |
# MAGIC | `remarks` | `STRING` | Desk remarks, possibly over several lines. **Null where there are none** |
# MAGIC | `_rescued_data` | `STRING` | What did not fit, kept by Auto Loader |
# MAGIC
# MAGIC **`workspace.de_prep.ferry_vessels`**
# MAGIC
# MAGIC | Column | Type | Meaning |
# MAGIC |---|---|---|
# MAGIC | `vessel_code` | `STRING` | The vessel, unique per row |
# MAGIC | `name` | `STRING` | Its name |
# MAGIC | `built` | `BIGINT` | Year built |
# MAGIC | `decks` | `BIGINT` | Number of decks |
# MAGIC | `engine` | `STRUCT<kw: BIGINT, make: STRING>` | A struct you can query as `engine.make`, not a JSON string |
# MAGIC | `imo_number` | `STRING` | Only the second delivery has it. **Null for the vessels in the first** |
# MAGIC
# MAGIC **`workspace.de_prep.ferry_manifests`**
# MAGIC
# MAGIC | Column | Type | Meaning |
# MAGIC |---|---|---|
# MAGIC | `crossing` | `STRING` | The crossing, unique per row |
# MAGIC | `route` | `STRING` | Its route |
# MAGIC | `cars` | `BIGINT` | Cars carried |
# MAGIC | `freight_units` | `BIGINT` | Freight units carried |
# MAGIC | `hazardous` | `BOOLEAN` | Whether it carried hazardous goods |
# MAGIC | `_rescued_data` | `STRING` | What did not fit |
# MAGIC
# MAGIC **`workspace.de_prep.ferry_crossings`**
# MAGIC
# MAGIC | Column | Type | Meaning |
# MAGIC |---|---|---|
# MAGIC | `crossing` | `STRING` | The crossing, unique per row |
# MAGIC | `vessel` | `STRING` | Which vessel sailed it |
# MAGIC | `departed_at` | `TIMESTAMP` | When it left |
# MAGIC | `load_pct` | `DOUBLE` | How full it was |
# MAGIC
# MAGIC **`workspace.de_prep.ferry_scans`**
# MAGIC
# MAGIC | Column | Type | Meaning |
# MAGIC |---|---|---|
# MAGIC | `path` | `STRING` | The scan's file |
# MAGIC | `modificationTime` | `TIMESTAMP` | When it was written |
# MAGIC | `length` | `BIGINT` | Its size in bytes |
# MAGIC
# MAGIC **Requirement 1.** **Auto Loader, every table.** Each table's history shows `STREAMING UPDATE`.
# MAGIC
# MAGIC **Requirement 2.** **The right folder for each location.** Each stream's checkpoint is
# MAGIC `s2_al_work/<table>/_checkpoint` and its schema location `s2_al_work/<table>/_schema`.
# MAGIC The tests look inside both, so a swapped pair fails.
# MAGIC
# MAGIC **Requirement 3.** **Tickets parse completely.** One row per ticket, multi-line remarks intact,
# MAGIC `departs` never null, `N/A` read as null, and the fares that are not prices left
# MAGIC null in `fare_gbp` with their original text in `_rescued_data`.
# MAGIC
# MAGIC **Requirement 4.** **The vessels arrive in two deliveries, and so must your stream.** Land
# MAGIC `batch_1` and run the stream; then land `batch_2` and run it again (the starter
# MAGIC has a `land_vessels(n)` helper). The second run meets a field the first never
# MAGIC saw. The table's history must show both loads, and `imo_number` must be filled for
# MAGIC the second delivery only.
# MAGIC
# MAGIC **Requirement 5.** **Manifests: one row per crossing**, with the attribute names as the contract
# MAGIC spells them.
# MAGIC
# MAGIC **Requirement 6.** **Scans: boarding-card images only, without their bytes.** The folder holds other
# MAGIC files; none of them belongs in the table, and neither does a `content` column.
# MAGIC
# MAGIC **Requirement 7.** **Column order matters** for `ferry_tickets`, `ferry_crossings` and
# MAGIC `ferry_scans`. The tests use `assertSchemaEqual`.
# MAGIC <!-- excerpt:end -->

# COMMAND ----------

for table in ("ferry_tickets", "ferry_vessels", "ferry_manifests", "ferry_crossings", "ferry_scans"):
    if not spark.catalog.tableExists(table):
        print(f"{table:16} not created yet")
        continue
    ops = [r.operation for r in spark.sql(f"DESCRIBE HISTORY {table}").collect()]
    print(f"{table:16} {spark.table(table).count():>4} rows   written by: {sorted(set(ops))}")
    print(" " * 17, spark.table(table).schema.simpleString())
