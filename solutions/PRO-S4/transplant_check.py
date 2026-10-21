# Databricks notebook source
# MAGIC %md
# MAGIC # Anti-transplant check — PRO-S4
# MAGIC
# MAGIC Applies **lesson 01's sharing script** to the assess objects and asserts the
# MAGIC graded suite FAILS.
# MAGIC
# MAGIC The lesson's statements were correct for tables with deletion vectors off. Here
# MAGIC the same script produces a share that exists, holds the right number of objects,
# MAGIC is granted to the right recipient, and is wrong on three of the four terms.

# COMMAND ----------

# MAGIC %pip install pytest -q
# MAGIC %restart_python

# COMMAND ----------

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sharing import AuthenticationType

w = WorkspaceClient()
CATALOG, SCHEMA = "workspace", "de_prep"
SHARE, RECIPIENT = "pro_s4_partner_share", "pro_s4_partner"
spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")

# Snapshot the correct configuration so it can be rebuilt afterwards.
correct = spark.sql(f"SHOW ALL IN SHARE {SHARE}").collect() \
    if SHARE in [r["share"] for r in spark.sql("SHOW SHARES").collect()] else []
print(f"snapshot: {len(correct)} objects in the correct share")

# COMMAND ----------

# MAGIC %md
# MAGIC ## The lesson's script, applied to the assess objects

# COMMAND ----------

spark.sql(f"DROP SHARE IF EXISTS {SHARE}")
spark.sql(f"CREATE SHARE {SHARE}")

# Start from the state the generator leaves behind, not from whatever a previous
# solution run did to these tables. Without this the check quietly gets easier every
# time it runs - the remedy the solution applied is still in place.
spark.sql(f"ALTER TABLE {CATALOG}.{SCHEMA}.pro_s4_assess_orders "
          "SET TBLPROPERTIES (delta.enableDeletionVectors = true)")
spark.sql(f"ALTER TABLE {CATALOG}.{SCHEMA}.pro_s4_assess_events "
          "SET TBLPROPERTIES (delta.enableChangeDataFeed = false)")
print("assess tables reset to their generator-fresh properties")

me = w.current_user.me().user_name
spark.sql(f"GRANT USE CATALOG ON CATALOG {CATALOG} TO `{me}`")
spark.sql(f"GRANT USE SCHEMA ON SCHEMA {CATALOG}.{SCHEMA} TO `{me}`")

# The lesson added a table plainly, then re-added it WITHOUT HISTORY. That second
# statement is refused on a table with deletion vectors, so the plain one is what
# survives - and it shares the history.
spark.sql(f"ALTER SHARE {SHARE} ADD TABLE {CATALOG}.{SCHEMA}.pro_s4_assess_orders "
          f"AS partner.orders")
try:
    spark.sql(f"ALTER SHARE {SHARE} REMOVE TABLE {CATALOG}.{SCHEMA}.pro_s4_assess_orders")
    spark.sql(f"ALTER SHARE {SHARE} ADD TABLE {CATALOG}.{SCHEMA}.pro_s4_assess_orders "
              f"AS partner.orders WITHOUT HISTORY")
    print("history removed")
except Exception as e:
    print("the lesson's WITHOUT HISTORY step failed here:")
    print(" ", str(e).split("\n")[0][:170])

spark.sql(f"ALTER SHARE {SHARE} ADD TABLE {CATALOG}.{SCHEMA}.pro_s4_assess_customers "
          f"AS partner.customers")

# The lesson used the WITH CHANGE DATA FEED clause. It is refused on this metastore,
# so the table lands without its change feed.
try:
    spark.sql(f"ALTER SHARE {SHARE} ADD TABLE {CATALOG}.{SCHEMA}.pro_s4_assess_events "
              f"AS partner.events WITH CHANGE DATA FEED")
except Exception as e:
    print("the lesson's CDF clause failed here:")
    print(" ", str(e).split("\n")[0][:170])
    spark.sql(f"ALTER SHARE {SHARE} ADD TABLE {CATALOG}.{SCHEMA}.pro_s4_assess_events "
              f"AS partner.events")

spark.sql(f"ALTER SHARE {SHARE} ADD VOLUME {CATALOG}.{SCHEMA}.pro_s4_assess_files "
          f"AS partner.files")

for r in w.recipients.list():
    if r.name == RECIPIENT:
        w.recipients.delete(RECIPIENT)
w.recipients.create(name=RECIPIENT, authentication_type=AuthenticationType.DATABRICKS,
                    data_recipient_global_metastore_id=w.metastores.summary().global_metastore_id)
spark.sql(f"GRANT SELECT ON SHARE {SHARE} TO RECIPIENT {RECIPIENT}")

print()
print("four objects, right names, right recipient:")
for r in spark.sql(f"SHOW ALL IN SHARE {SHARE}").collect():
    print(f"  {r['name']:20} history={r['history_sharing']:9} cdf={r['cdf_shared']}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Run the graded suite against it

# COMMAND ----------

import contextlib, io, os, shutil, tempfile
import pytest

ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
repo_root = ("/Workspace" + os.path.dirname(ctx.notebookPath().get())).split("/files/")[0] + "/files"

workdir = tempfile.mkdtemp(prefix="transplant_pro_s4_")
shutil.copytree(os.path.join(repo_root, "grading", "PRO-S4", "tests"),
                os.path.join(workdir, "tests"))
fixtures = os.path.join(workdir, "expected.json")
shutil.copyfile(os.path.join(repo_root, "grading", "PRO-S4", "expected.json"), fixtures)
os.environ["PRO_S4_FIXTURES"] = fixtures

buf = io.StringIO()
with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
    exit_code = pytest.main([os.path.join(workdir, "tests"), "-v", "--tb=line",
                             "-p", "no:cacheprovider"])
report = buf.getvalue()
print(report)
dbutils.fs.mkdirs("/Volumes/workspace/de_prep/raw/_grading")
dbutils.fs.put("/Volumes/workspace/de_prep/raw/_grading/PRO-S4-transplant.txt",
               report[-30000:] + f"\n\nexit={exit_code}\n", overwrite=True)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Restore the correct configuration
# MAGIC
# MAGIC Rebuilt from the snapshot, so a failure above never leaves the wrong share in
# MAGIC place. A share cannot be rebuilt from `SHOW ALL IN SHARE` alone without also
# MAGIC restoring the table properties the terms depend on.

# COMMAND ----------

spark.sql(f"DROP SHARE IF EXISTS {SHARE}")
spark.sql(f"CREATE SHARE {SHARE} COMMENT 'Partner share for PRO-S4'")

spark.sql(f"ALTER TABLE {CATALOG}.{SCHEMA}.pro_s4_assess_orders "
          "SET TBLPROPERTIES (delta.enableDeletionVectors = false)")
spark.sql(f"REORG TABLE {CATALOG}.{SCHEMA}.pro_s4_assess_orders APPLY (PURGE)")
spark.sql(f"ALTER TABLE {CATALOG}.{SCHEMA}.pro_s4_assess_events "
          "SET TBLPROPERTIES (delta.enableChangeDataFeed = true)")

spark.sql(f"ALTER SHARE {SHARE} ADD TABLE {CATALOG}.{SCHEMA}.pro_s4_assess_orders "
          f"AS partner.orders WITHOUT HISTORY")
spark.sql(f"ALTER SHARE {SHARE} ADD TABLE {CATALOG}.{SCHEMA}.pro_s4_assess_customers "
          f"AS partner.customers")
spark.sql(f"ALTER SHARE {SHARE} ADD TABLE {CATALOG}.{SCHEMA}.pro_s4_assess_events "
          f"AS partner.events")
spark.sql(f"ALTER SHARE {SHARE} ADD VOLUME {CATALOG}.{SCHEMA}.pro_s4_assess_files "
          f"AS partner.files")
spark.sql(f"GRANT SELECT ON SHARE {SHARE} TO RECIPIENT {RECIPIENT}")

for r in spark.sql(f"SHOW ALL IN SHARE {SHARE}").collect():
    print(f"  {r['name']:20} history={r['history_sharing']:9} cdf={r['cdf_shared']}")
print("restored")

# COMMAND ----------

assert exit_code != 0, (
    "The transplanted lesson script PASSED the graded suite. The pairing is not doing "
    "its job and PRO-S4 needs redesigning."
)
print(f"\nAnti-transplant property holds: the lesson's script fails the suite "
      f"(pytest exit {exit_code}).")
