# Databricks notebook source
# MAGIC %md
# MAGIC # PRO-S4 — generate the `teach` and `assess` sharing surfaces
# MAGIC
# MAGIC Delta Sharing and Lakehouse Federation. The pairing differs in **whether the
# MAGIC tables can be shared the way the spec demands.**
# MAGIC
# MAGIC ## What makes the assignment un-copyable
# MAGIC
# MAGIC 1. **The teach tables have deletion vectors off.** `ALTER SHARE ... ADD TABLE`
# MAGIC    works, and `WITHOUT HISTORY` works, so sharing is one statement per table.
# MAGIC 2. **Most assess tables have deletion vectors on.** Delta Sharing then refuses to
# MAGIC    share them without full history — you must disable the feature and rewrite the
# MAGIC    files with `REORG ... APPLY (PURGE)` first.
# MAGIC 3. **The default is the trap.** A plain `ADD TABLE` shares history **ENABLED**.
# MAGIC    Nothing errors, nothing warns, and `SHOW ALL IN SHARE` will tell you so only if
# MAGIC    you read the column. A spec that says "no history" is quietly not met.
# MAGIC 4. **One table must not be shared at all.** Over-sharing is the failure mode a
# MAGIC    sharing review exists to catch, and it never raises an error.

# COMMAND ----------

import random
from datetime import date, timedelta

from databricks.sdk import WorkspaceClient

CATALOG, SCHEMA = "workspace", "de_prep"
SEED = 20260906
spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")

w = WorkspaceClient()
print("global metastore id:", w.metastores.summary().global_metastore_id)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Reset: a shared table cannot be dropped
# MAGIC
# MAGIC Delta Sharing holds a reference. `DROP TABLE` on an object that is in a share
# MAGIC fails with `DELTA_SHARING_SECURABLE_DELETE_BLOCKED.BY_SHARES` - the same class of
# MAGIC guardrail as a connection that a foreign catalog is built on. So this generator
# MAGIC tears the shares down before it rebuilds the tables.

# COMMAND ----------

# SHOW SHARES names its first column `share`, not `name`.
for row in spark.sql("SHOW SHARES").collect():
    if row["share"].startswith("pro_s4"):
        spark.sql(f"DROP SHARE `{row['share']}`")
        print("dropped share", row["share"])
for r in w.recipients.list():
    if r.name and r.name.startswith("pro_s4"):
        w.recipients.delete(r.name)
        print("dropped recipient", r.name)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Sharing requires traversal privileges, even from the owner
# MAGIC
# MAGIC Owning a table is not enough to put it in a share. `ALTER SHARE ... ADD TABLE`
# MAGIC checks for `USE CATALOG` and `USE SCHEMA` explicitly, and fails with
# MAGIC `PERMISSION_DENIED` without them. This is the same traversal rule as `PRO-S8`,
# MAGIC showing up somewhere you would not expect it.

# COMMAND ----------

me = w.current_user.me().user_name
spark.sql(f"GRANT USE CATALOG ON CATALOG {CATALOG} TO `{me}`")
spark.sql(f"GRANT USE SCHEMA ON SCHEMA {CATALOG}.{SCHEMA} TO `{me}`")
print(f"granted traversal to {me}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## `teach` — tables that share without argument

# COMMAND ----------

rng = random.Random(SEED)
base = date(2026, 1, 1)

rows = [(f"T-{i:04d}", rng.choice(["north", "south"]),
         round(rng.uniform(10, 900), 2), base + timedelta(days=rng.randint(0, 120)))
        for i in range(1, 201)]
for name in ("pro_s4_teach_orders", "pro_s4_teach_customers"):
    spark.sql(f"DROP TABLE IF EXISTS {name}")
    (spark.createDataFrame(
        rows, "id STRING, region STRING, amount DOUBLE, booked_on DATE")
     .write.mode("overwrite").saveAsTable(name))
    # deletion vectors OFF, so history-free sharing is available
    spark.sql(f"ALTER TABLE {name} SET TBLPROPERTIES (delta.enableDeletionVectors = false)")
    spark.sql(f"REORG TABLE {name} APPLY (PURGE)")
print("teach tables built with deletion vectors disabled")

# COMMAND ----------

# MAGIC %md
# MAGIC ## `assess` — three tables with deletion vectors on, one without, and a volume

# COMMAND ----------

ASSESS = {
    "pro_s4_assess_orders": True,      # DV on  - must end up shared WITHOUT history
    "pro_s4_assess_customers": True,   # DV on  - must end up shared WITH history
    "pro_s4_assess_events": True,      # DV on  - must end up shared WITH CDF
    "pro_s4_assess_salaries": False,   # DV off - and must NOT be shared at all
}
for name, dv in ASSESS.items():
    spark.sql(f"DROP TABLE IF EXISTS {name}")
    (spark.createDataFrame(
        rows, "id STRING, region STRING, amount DOUBLE, booked_on DATE")
     .write.mode("overwrite").saveAsTable(name))
    spark.sql(f"ALTER TABLE {name} SET TBLPROPERTIES "
              f"(delta.enableDeletionVectors = {'true' if dv else 'false'})")
    if not dv:
        spark.sql(f"REORG TABLE {name} APPLY (PURGE)")

spark.sql("CREATE VOLUME IF NOT EXISTS pro_s4_assess_files "
          "COMMENT 'Partner drop zone, shared as a volume'")
print("assess objects built")

# COMMAND ----------

# MAGIC %md
# MAGIC ## The traps, measured

# COMMAND ----------

def dv_on(table):
    props = {r["key"]: r["value"] for r in
             spark.sql(f"SHOW TBLPROPERTIES {table}").collect()}
    return props.get("delta.enableDeletionVectors", "false") == "true"

for name, expected_dv in ASSESS.items():
    print(f"{name:26} deletionVectors={dv_on(name)}")
    assert dv_on(name) == expected_dv, name
for name in ("pro_s4_teach_orders", "pro_s4_teach_customers"):
    print(f"{name:26} deletionVectors={dv_on(name)}")
    assert not dv_on(name), name

# COMMAND ----------

# Trap 1: a teach table shares without history. An assess table does not.
spark.sql("DROP SHARE IF EXISTS pro_s4_trap_probe")
spark.sql("CREATE SHARE pro_s4_trap_probe")

spark.sql("ALTER SHARE pro_s4_trap_probe ADD TABLE "
          f"{CATALOG}.{SCHEMA}.pro_s4_teach_orders WITHOUT HISTORY")
print("teach table shared WITHOUT HISTORY: ok")

refused = None
try:
    spark.sql("ALTER SHARE pro_s4_trap_probe ADD TABLE "
              f"{CATALOG}.{SCHEMA}.pro_s4_assess_orders WITHOUT HISTORY")
except Exception as e:
    refused = str(e)
print("assess table shared WITHOUT HISTORY:",
      "refused" if refused else "ACCEPTED (trap missing)")
assert refused and "DeletionVectors" in refused, \
    "deletion vectors must block history-free sharing on the assess tables"
print(" ", refused.split("\n")[0][:160])

# COMMAND ----------

# Trap 2: the default is history ENABLED, silently.
spark.sql("ALTER SHARE pro_s4_trap_probe ADD TABLE "
          f"{CATALOG}.{SCHEMA}.pro_s4_assess_customers")
objs = {r["name"]: r for r in spark.sql("SHOW ALL IN SHARE pro_s4_trap_probe").collect()}

teach_hist = objs["de_prep.pro_s4_teach_orders"]["history_sharing"]
assess_hist = objs["de_prep.pro_s4_assess_customers"]["history_sharing"]
print(f"teach_orders      (explicit WITHOUT HISTORY): {teach_hist}")
print(f"assess_customers  (plain ADD TABLE)         : {assess_hist}")
assert teach_hist == "DISABLED" and assess_hist == "ENABLED", (teach_hist, assess_hist)
print("\nA plain ADD TABLE shares the history. It does not say so, and it does not fail.")

# COMMAND ----------

# Trap 3: the remedy path works, so the assignment is solvable.
spark.sql(f"ALTER TABLE {CATALOG}.{SCHEMA}.pro_s4_assess_orders "
          "SET TBLPROPERTIES (delta.enableDeletionVectors = false)")
spark.sql(f"REORG TABLE {CATALOG}.{SCHEMA}.pro_s4_assess_orders APPLY (PURGE)")
spark.sql("ALTER SHARE pro_s4_trap_probe ADD TABLE "
          f"{CATALOG}.{SCHEMA}.pro_s4_assess_orders WITHOUT HISTORY")
print("after disabling deletion vectors and REORG ... APPLY (PURGE): shared, no history")

# put it back, so the assignment starts from the same place every time
spark.sql("DROP SHARE IF EXISTS pro_s4_trap_probe")
spark.sql(f"DROP TABLE IF EXISTS {CATALOG}.{SCHEMA}.pro_s4_assess_orders")
(spark.createDataFrame(rows, "id STRING, region STRING, amount DOUBLE, booked_on DATE")
 .write.mode("overwrite").saveAsTable("pro_s4_assess_orders"))
spark.sql("ALTER TABLE pro_s4_assess_orders SET TBLPROPERTIES "
          "(delta.enableDeletionVectors = true)")
assert dv_on("pro_s4_assess_orders")
print("assess_orders reset with deletion vectors on")

# COMMAND ----------

# Trap 4: open-protocol sharing is unavailable here, so the recipient must be D2D.
from databricks.sdk.service.sharing import AuthenticationType
blocked = None
try:
    w.recipients.create(name="pro_s4_probe_open", authentication_type=AuthenticationType.TOKEN)
    w.recipients.delete("pro_s4_probe_open")
except Exception as e:
    blocked = str(e).strip().splitlines()[0]
print("open-protocol recipient:", blocked or "ACCEPTED")
assert blocked and "External Delta Sharing" in blocked, blocked

print("\nall traps hold")
