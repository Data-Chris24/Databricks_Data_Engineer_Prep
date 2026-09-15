# Databricks notebook source
# MAGIC %md
# MAGIC # PRO-S8 — Data Governance assignment
# MAGIC
# MAGIC The task and the output contract are in the next cell (the same text as `README.md` in the repo).

# COMMAND ----------

# MAGIC %md
# MAGIC <!-- task:begin  generated from README.md by tools/sync_assignment_tasks.py; edit the README, then re-run it -->
# MAGIC ## Assignment — `PRO-S8` Data Governance
# MAGIC
# MAGIC **Objectives:** `PRO-S8-O1`, `PRO-S8-O2`
# MAGIC
# MAGIC ### Before you start
# MAGIC
# MAGIC Work both lessons in `notebooks/lessons/professional/S8/`, and build the structures
# MAGIC (the study app generates the data the first time you open this section; `databricks bundle run generate_datasets_pro_s8 -t free` does the same from a terminal).
# MAGIC
# MAGIC > **In the lesson, every grant sat on the table it named.** That made
# MAGIC > `information_schema.table_privileges` a complete and truthful answer, and the audit
# MAGIC > query three columns long. The catalog you are auditing now is not built that way.
# MAGIC
# MAGIC ### The task
# MAGIC
# MAGIC Audit `pro_s8_assess`. It has two schemas, five tables, and four principals — the
# MAGIC service principals `de_prep_analyst`, `de_prep_engineer`, `de_prep_auditor` and
# MAGIC `de_prep_intern`. Produce two tables.
# MAGIC
# MAGIC Somebody in that list holds `SELECT` on every table in the catalog and can read none
# MAGIC of them. Your report has to say so.
# MAGIC
# MAGIC ### The output contract
# MAGIC
# MAGIC **`workspace.de_prep.pro_s8_access_report`** — one row per (principal, table,
# MAGIC privilege) that applies, inherited ones included.
# MAGIC
# MAGIC | Column | Type | Meaning |
# MAGIC |---|---|---|
# MAGIC | `principal` | `STRING` | the **display name**, not the application id |
# MAGIC | `table_schema` | `STRING` | |
# MAGIC | `table_name` | `STRING` | |
# MAGIC | `privilege` | `STRING` | `SELECT`, `MODIFY`, … |
# MAGIC | `granted_at_level` | `STRING` | `TABLE`, `SCHEMA` or `CATALOG` — where the grant actually lives |
# MAGIC | `has_use_catalog` | `BOOLEAN` | can the principal traverse the catalog |
# MAGIC | `has_use_schema` | `BOOLEAN` | can it traverse *this* schema |
# MAGIC | `is_effective` | `BOOLEAN` | `has_use_catalog AND has_use_schema` |
# MAGIC
# MAGIC Only the four `de_prep_*` principals. Ignore `account users` and the owner.
# MAGIC
# MAGIC **`workspace.de_prep.pro_s8_documentation`** — one row per table.
# MAGIC
# MAGIC | Column | Type | Meaning |
# MAGIC |---|---|---|
# MAGIC | `table_schema` | `STRING` | |
# MAGIC | `table_name` | `STRING` | |
# MAGIC | `has_table_comment` | `BOOLEAN` | |
# MAGIC | `column_count` | `INT` | |
# MAGIC | `documented_columns` | `INT` | columns with a comment |
# MAGIC | `tag_count` | `INT` | table-level tags |
# MAGIC | `has_pii_column` | `BOOLEAN` | any column tagged `pii = 'true'` |
# MAGIC | `is_documented` | `BOOLEAN` | see the definition below |
# MAGIC
# MAGIC **`is_documented`** — because "documented" is a definition, not a column:
# MAGIC
# MAGIC > a table comment **or** a table tag named `description`, **and** at least one
# MAGIC > column carrying a comment.
# MAGIC
# MAGIC #### Requirements
# MAGIC
# MAGIC 1. **`granted_at_level` must be where the grant lives**, not where it applies. A
# MAGIC    privilege that applies to a table is not necessarily granted on it — and revoking
# MAGIC    it at the wrong level succeeds and changes nothing.
# MAGIC 2. **`is_effective` must account for traversal.** Holding `SELECT` is not the same as
# MAGIC    being able to read.
# MAGIC 3. **Name the principals.** Application ids are not an audit deliverable.
# MAGIC 4. Column order matters — the tests compare the whole schema.
# MAGIC
# MAGIC ### Grading
# MAGIC
# MAGIC ```bash
# MAGIC databricks bundle run grade_pro_s8 -t free
# MAGIC ```
# MAGIC
# MAGIC The tests are authoritative. The advisory AI review (`grading/rubrics/PRO-S8.yaml`)
# MAGIC judges whether you audited the model or just queried one view.
# MAGIC
# MAGIC ### What this section creates in your workspace
# MAGIC
# MAGIC Unlike every other section, PRO-S8 needs real principals — Unity Catalog will not
# MAGIC grant to a workspace-local group. The generator creates four **service principals**
# MAGIC (`de_prep_analyst`, `de_prep_engineer`, `de_prep_auditor`, `de_prep_intern`) and two
# MAGIC **catalogs** (`pro_s8_teach`, `pro_s8_assess`). None of them can sign in or run
# MAGIC anything; they exist only to be granted privileges.
# MAGIC
# MAGIC To remove it all afterwards:
# MAGIC
# MAGIC ```sql
# MAGIC DROP CATALOG pro_s8_teach  CASCADE;
# MAGIC DROP CATALOG pro_s8_assess CASCADE;
# MAGIC ```
# MAGIC
# MAGIC then delete the four service principals from **Settings → Identity and access →
# MAGIC Service principals**.
# MAGIC <!-- task:end -->

# COMMAND ----------

from databricks.sdk import WorkspaceClient
from pyspark.sql import functions as F

ASSESS = "pro_s8_assess"
spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")

display(spark.sql(f"""
    SELECT table_schema, table_name, table_owner
    FROM {ASSESS}.information_schema.tables
    WHERE table_schema <> 'information_schema'
"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Look at the three privilege views before you write anything
# MAGIC
# MAGIC `catalog_privileges`, `schema_privileges`, `table_privileges`. Check their
# MAGIC columns — one of them carries more than the obvious query selects — and check
# MAGIC how they spell the privilege names.

# COMMAND ----------

# TODO: your investigation


# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. The access report

# COMMAND ----------

# TODO
# report.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable("pro_s8_access_report")


# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. The documentation inventory
# MAGIC
# MAGIC Four sources: `tables`, `columns`, `table_tags`, `column_tags`.

# COMMAND ----------

# TODO
# docs.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable("pro_s8_documentation")


# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Sanity checks
# MAGIC
# MAGIC - Does any principal hold privileges it cannot use? If your answer is "none",
# MAGIC   check how you spelled `USE_CATALOG`.
# MAGIC - Do all four principals appear?
# MAGIC - Is every `granted_at_level` one of TABLE / SCHEMA / CATALOG?

# COMMAND ----------

# TODO
