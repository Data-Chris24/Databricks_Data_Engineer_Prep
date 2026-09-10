# Databricks notebook source
# MAGIC %md
# MAGIC # PRO-S8 — Data Governance assignment
# MAGIC
# MAGIC Read `README.md` first. The contract there is what the tests check.

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
