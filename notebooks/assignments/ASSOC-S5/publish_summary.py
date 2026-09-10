# Databricks notebook source
# MAGIC %md
# MAGIC # ASSOC-S5 assignment — the job that gets promoted
# MAGIC
# MAGIC **This notebook must not hardcode its destination.** It is deployed once and run
# MAGIC against two environments, so the catalog and schema arrive as **job parameters**
# MAGIC fed by bundle variables that each target overrides.
# MAGIC
# MAGIC Fill in the marked cell. The lesson's version hardcoded
# MAGIC `workspace.de_prep` — copy that and the second environment gets the first one's
# MAGIC data.

# COMMAND ----------

# These come from the job definition, which reads them from bundle variables.
dbutils.widgets.text("target_catalog", "")
dbutils.widgets.text("target_schema", "")

target_catalog = dbutils.widgets.get("target_catalog")
target_schema = dbutils.widgets.get("target_schema")

if not target_catalog or not target_schema:
    raise ValueError(
        "target_catalog and target_schema must be supplied by the job. "
        "If these are empty, the job definition is not passing the bundle variables."
    )
print(f"publishing to {target_catalog}.{target_schema}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Your work
# MAGIC
# MAGIC Read `workspace.de_prep.s5_source_transactions`, aggregate by channel, and write
# MAGIC `s5_channel_summary` into **the target passed above** with this schema:
# MAGIC
# MAGIC | Column | Type |
# MAGIC |---|---|
# MAGIC | `channel` | `STRING` |
# MAGIC | `txns` | `BIGINT` |
# MAGIC | `revenue` | `DOUBLE` |
# MAGIC | `environment` | `STRING` — the schema it was written to |

# COMMAND ----------

# TODO: your transformation and write go here.


# COMMAND ----------

# MAGIC %md
# MAGIC ## Check yourself

# COMMAND ----------

# display(spark.table(f"{target_catalog}.{target_schema}.s5_channel_summary"))
