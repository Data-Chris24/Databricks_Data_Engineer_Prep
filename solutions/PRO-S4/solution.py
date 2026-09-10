# Databricks notebook source
# MAGIC %md
# MAGIC # PRO-S4 assignment — reference solution
# MAGIC
# MAGIC The deliverable is a **configuration**, not a table. Four objects shared to one
# MAGIC recipient, each on different terms, and one table that must not leave the building.

# COMMAND ----------

import json

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sharing import AuthenticationType

w = WorkspaceClient()
CATALOG, SCHEMA = "workspace", "de_prep"
SHARE, RECIPIENT = "pro_s4_partner_share", "pro_s4_partner"

spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")

# Sharing checks traversal explicitly, even for the owner.
me = w.current_user.me().user_name
spark.sql(f"GRANT USE CATALOG ON CATALOG {CATALOG} TO `{me}`")
spark.sql(f"GRANT USE SCHEMA ON SCHEMA {CATALOG}.{SCHEMA} TO `{me}`")

spark.sql(f"DROP SHARE IF EXISTS {SHARE}")
spark.sql(f"CREATE SHARE {SHARE} COMMENT 'Partner share for PRO-S4'")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. `orders` — no history, and the deletion vectors are in the way
# MAGIC
# MAGIC The naive statement is refused. Show that first, because the error is the
# MAGIC instruction.

# COMMAND ----------

ORDERS = f"{CATALOG}.{SCHEMA}.pro_s4_assess_orders"

shared = False
try:
    spark.sql(f"ALTER SHARE {SHARE} ADD TABLE {ORDERS} AS partner.orders WITHOUT HISTORY")
    shared = True
    print("accepted - this table's deletion vectors are already off")
except Exception as e:
    print("refused:", str(e).split("\n")[0][:180])

# COMMAND ----------

# Turning the property off stops NEW deletion vectors. REORG rewrites away the ones
# already written - without it the table still carries the feature and still refuses.
if not shared:
    spark.sql(f"ALTER TABLE {ORDERS} SET TBLPROPERTIES (delta.enableDeletionVectors = false)")
    spark.sql(f"REORG TABLE {ORDERS} APPLY (PURGE)")
    spark.sql(f"ALTER SHARE {SHARE} ADD TABLE {ORDERS} AS partner.orders WITHOUT HISTORY")
print("orders shared without history")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. `customers` — history required, so the default is what we want
# MAGIC
# MAGIC The only object in this share where writing the shortest statement is correct.

# COMMAND ----------

spark.sql(f"ALTER SHARE {SHARE} ADD TABLE {CATALOG}.{SCHEMA}.pro_s4_assess_customers "
          f"AS partner.customers")
print("customers shared with history")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. `events` — the recipient needs the change feed
# MAGIC
# MAGIC `WITH CHANGE DATA FEED` is refused on this metastore (managed-key encryption), and
# MAGIC it is not what controls the outcome anyway: `cdf_shared` follows the **table's**
# MAGIC `delta.enableChangeDataFeed` property.

# COMMAND ----------

spark.sql(f"ALTER TABLE {CATALOG}.{SCHEMA}.pro_s4_assess_events "
          "SET TBLPROPERTIES (delta.enableChangeDataFeed = true)")
spark.sql(f"ALTER SHARE {SHARE} ADD TABLE {CATALOG}.{SCHEMA}.pro_s4_assess_events "
          f"AS partner.events")
print("events shared with the change feed")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. The volume

# COMMAND ----------

spark.sql(f"ALTER SHARE {SHARE} ADD VOLUME {CATALOG}.{SCHEMA}.pro_s4_assess_files "
          f"AS partner.files")
display(spark.sql(f"SHOW ALL IN SHARE {SHARE}")
        .select("name", "type", "history_sharing", "cdf_shared", "shared_object"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. `salaries` stays home
# MAGIC
# MAGIC There is nothing to write for this requirement, which is exactly why it is the
# MAGIC one that gets missed. Assert it instead.

# COMMAND ----------

shared_sources = {r["shared_object"] for r in
                  spark.sql(f"SHOW ALL IN SHARE {SHARE}").collect()}
assert f"{CATALOG}.{SCHEMA}.pro_s4_assess_salaries" not in shared_sources
print("salaries is not in the share:", sorted(shared_sources))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. The recipient, and the grant that makes it real

# COMMAND ----------

for r in w.recipients.list():
    if r.name == RECIPIENT:
        w.recipients.delete(RECIPIENT)

summary = w.metastores.summary()
w.recipients.create(
    name=RECIPIENT,
    authentication_type=AuthenticationType.DATABRICKS,
    data_recipient_global_metastore_id=summary.global_metastore_id,
    comment="Partner recipient for PRO-S4")

spark.sql(f"GRANT SELECT ON SHARE {SHARE} TO RECIPIENT {RECIPIENT}")
display(spark.sql(f"SHOW GRANTS ON SHARE {SHARE}"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Fixtures

# COMMAND ----------

objs = spark.sql(f"SHOW ALL IN SHARE {SHARE}").collect()
grants = spark.sql(f"SHOW GRANTS ON SHARE {SHARE}").collect()
rec = [r for r in w.recipients.list() if r.name == RECIPIENT][0]

fixtures = {
    "_generated_by": "solutions/PRO-S4/solution.py, run on Free Edition serverless",
    "share": SHARE,
    "recipient": RECIPIENT,
    "object_count": len(objs),
    "objects": sorted(
        [[r["name"], r["type"], r["history_sharing"], r["cdf_shared"],
          r["shared_object"]] for r in objs]),
    "grants": sorted([[r["recipient"], r["privilege"]] for r in grants]),
    "recipient_auth": rec.authentication_type.value,
    # Never commit the sharing identifier - it names this workspace, and this repo is
    # public. The test resolves the expected value live instead, which also makes the
    # fixture correct in whichever workspace a learner runs it.
    "recipient_targets_this_metastore":
        rec.data_recipient_global_metastore_id == summary.global_metastore_id,
    "must_not_be_shared": [f"{CATALOG}.{SCHEMA}.pro_s4_assess_salaries"],
}
print(json.dumps(fixtures, indent=2))
dbutils.fs.put("/Volumes/workspace/de_prep/raw/_pro_s4_expected.json",
               json.dumps(fixtures, indent=2), overwrite=True)
