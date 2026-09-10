# Databricks notebook source
# MAGIC %md
# MAGIC # PRO-S4 — Data Sharing and Federation assignment
# MAGIC
# MAGIC Read `README.md` first. The table there is the contract.

# COMMAND ----------

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sharing import AuthenticationType

w = WorkspaceClient()
CATALOG, SCHEMA = "workspace", "de_prep"
SHARE, RECIPIENT = "pro_s4_partner_share", "pro_s4_partner"

spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 0. Look at what you have been given
# MAGIC
# MAGIC Check each table's properties before you try to share it. Two properties decide
# MAGIC what terms are available to you.

# COMMAND ----------

for t in ("pro_s4_assess_orders", "pro_s4_assess_customers",
          "pro_s4_assess_events", "pro_s4_assess_salaries"):
    props = {r["key"]: r["value"] for r in spark.sql(f"SHOW TBLPROPERTIES {t}").collect()}
    print(f"{t:28} DV={props.get('delta.enableDeletionVectors', '-'):6} "
          f"CDF={props.get('delta.enableChangeDataFeed', '-')}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. The share

# COMMAND ----------

# TODO


# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Add the objects, each on its own terms

# COMMAND ----------

# TODO


# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. The recipient, and the grant

# COMMAND ----------

# TODO


# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Check what you actually built
# MAGIC
# MAGIC Read `history_sharing` and `cdf_shared` for every row, and confirm the one table
# MAGIC that must not be shared is absent. Both failures are silent.

# COMMAND ----------

display(spark.sql(f"SHOW ALL IN SHARE {SHARE}")
        .select("name", "type", "history_sharing", "cdf_shared", "shared_object"))
display(spark.sql(f"SHOW GRANTS ON SHARE {SHARE}"))
