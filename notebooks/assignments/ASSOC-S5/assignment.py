# Databricks notebook source
# MAGIC %md
# MAGIC # ASSOC-S5 assignment — your work goes here
# MAGIC
# MAGIC Read `README.md` in this folder for the task and the output contract.
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
