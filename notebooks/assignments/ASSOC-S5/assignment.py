# Databricks notebook source
# MAGIC %md
# MAGIC # ASSOC-S5 assignment — your work goes here
# MAGIC
# MAGIC The task and the output contract are in the next cell (the same text as `README.md` in the repo).
# MAGIC
# MAGIC **The lesson hardcoded its destination. Here the work is mostly outside this notebook: a job definition whose destination is a bundle variable.**
# MAGIC
# MAGIC The graded artefact is the pair of tables the job produces, one per schema, each
# MAGIC stamped with where it landed - which is only possible if the destination was
# MAGIC genuinely parameterised.
# MAGIC
# MAGIC When you are done, go back to the study app and press **Grade my assignment**.
# MAGIC Each failing check says what it expected and why.

# COMMAND ----------

# MAGIC %md
# MAGIC <!-- task:begin  generated from README.md by tools/sync_assignment_tasks.py; edit the README, then re-run it -->
# MAGIC ## Assignment — `ASSOC-S5` Implementing CI/CD
# MAGIC
# MAGIC **Objectives:** `ASSOC-S5-O1`, `O2`, `O3`, `O4`
# MAGIC
# MAGIC ### Before you start
# MAGIC
# MAGIC Work the two lessons in `notebooks/lessons/associate/S5/`, and generate the data
# MAGIC (the study app generates the data the first time you open this section; `databricks bundle run generate_datasets_assoc_s5 -t free` does the same from a terminal).
# MAGIC
# MAGIC > **The lesson hardcoded its destination.** That is fine for one environment and
# MAGIC > wrong for two. Copy it and staging gets production's data — or nothing at all.
# MAGIC
# MAGIC ### The task
# MAGIC
# MAGIC Publish a channel summary to **two environments from one job definition**.
# MAGIC
# MAGIC The two environments are two schemas on this workspace, standing in for staging and
# MAGIC production:
# MAGIC
# MAGIC | Environment | Schema |
# MAGIC |---|---|
# MAGIC | staging | `workspace.de_prep_staging` |
# MAGIC | production | `workspace.de_prep` |
# MAGIC
# MAGIC ### Requirements
# MAGIC
# MAGIC 1. **One job definition.** Not two jobs, not two notebooks. The same resource,
# MAGIC    deployed to two targets.
# MAGIC 2. **The destination comes from a bundle variable overridden per target** — the
# MAGIC    notebook must not contain either schema name.
# MAGIC 3. **Both environments end up with the same summary**, each row stamped with the
# MAGIC    schema it was written to in an `environment` column.
# MAGIC 4. The notebook must **fail loudly** if the parameters are missing, rather than
# MAGIC    quietly defaulting to one environment.
# MAGIC
# MAGIC ### The output contract
# MAGIC
# MAGIC `s5_channel_summary`, in **both** schemas:
# MAGIC
# MAGIC | Column | Type |
# MAGIC |---|---|
# MAGIC | `channel` | `STRING` |
# MAGIC | `txns` | `BIGINT` |
# MAGIC | `revenue` | `DOUBLE` |
# MAGIC | `environment` | `STRING` |
# MAGIC
# MAGIC ### Grading
# MAGIC
# MAGIC ```bash
# MAGIC databricks bundle run grade_assoc_s5 -t free --profile FREE
# MAGIC ```
# MAGIC
# MAGIC The suite checks both schemas, that the numbers match, and that each row records the
# MAGIC environment it landed in — which is only possible if the destination was genuinely
# MAGIC parameterised.
# MAGIC
# MAGIC ### Hints
# MAGIC
# MAGIC <details><summary>How does a target override a variable?</summary>
# MAGIC
# MAGIC ```yaml
# MAGIC variables:
# MAGIC   schema:
# MAGIC     default: de_prep
# MAGIC
# MAGIC targets:
# MAGIC   staging:
# MAGIC     variables:
# MAGIC       schema: de_prep_staging
# MAGIC ```
# MAGIC </details>
# MAGIC
# MAGIC <details><summary>How does the notebook receive it?</summary>
# MAGIC
# MAGIC `base_parameters` on the task, read with `dbutils.widgets.get()`.
# MAGIC </details>
# MAGIC
# MAGIC <details><summary>Both schemas have identical `environment` values</summary>
# MAGIC
# MAGIC The stamp is hardcoded rather than derived from the parameter.
# MAGIC </details>
# MAGIC <!-- task:end -->

# COMMAND ----------

# The notebook the job runs is publish_summary.py, next to this one. It must not
# contain either schema name; the job passes them in as parameters.
PRODUCTION = "workspace.de_prep"
STAGING = "workspace.de_prep_staging"

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1 — fill in publish_summary.py
# MAGIC
# MAGIC Read `s5_source_transactions`, aggregate by channel, write `s5_channel_summary` to the catalog and schema the job passes in, stamped with the schema in an `environment` column.

# COMMAND ----------

# Open publish_summary.py and complete its marked cell.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2 — write the job definition
# MAGIC
# MAGIC One resource, in your fork's bundle. The destination comes from a variable that each target overrides:
# MAGIC
# MAGIC ```yaml
# MAGIC resources:
# MAGIC   jobs:
# MAGIC     s5_publish_summary:
# MAGIC       tasks:
# MAGIC         - task_key: publish
# MAGIC           notebook_task:
# MAGIC             notebook_path: ../../notebooks/assignments/ASSOC-S5/publish_summary.py
# MAGIC             base_parameters:
# MAGIC               target_catalog: ${var.catalog}
# MAGIC               target_schema: ${var.schema}
# MAGIC ```

# COMMAND ----------

# Nothing to run here - this step lives in bundle/resources/.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3 — deploy and run it against both targets
# MAGIC
# MAGIC `free` writes to production, `staging` overrides the schema. Requirement 4: the notebook must fail loudly if the parameters are missing.

# COMMAND ----------

# databricks bundle run s5_publish_summary -t free --profile FREE
# databricks bundle run s5_publish_summary -t staging --profile FREE

# COMMAND ----------

# MAGIC %md
# MAGIC ## Check yourself before grading

# COMMAND ----------

# for schema in (PRODUCTION, STAGING):
#     display(spark.table(f"{schema}.s5_channel_summary"))
