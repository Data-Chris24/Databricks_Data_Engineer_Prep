# Databricks notebook source
# MAGIC %md
# MAGIC # PRO-S8 · The Unity Catalog permission inheritance model
# MAGIC
# MAGIC **Objective:** `PRO-S8-O2`
# MAGIC
# MAGIC Two rules explain almost every access question in UC:
# MAGIC
# MAGIC 1. **A privilege granted on a container applies to everything inside it**, now and
# MAGIC    in the future. Metastore → catalog → schema → table.
# MAGIC 2. **You must be able to reach the object.** `SELECT` on a table is inert without
# MAGIC    `USE CATALOG` on its catalog *and* `USE SCHEMA` on its schema.
# MAGIC
# MAGIC Rule 1 is the one people know. Rule 2 is the one that generates support tickets.

# COMMAND ----------

from pyspark.sql import functions as F

TEACH = "pro_s8_teach"
DEMO = "pro_s8_inherit_demo"
spark.sql(f"USE CATALOG {TEACH}")

# The four service principals the generator created stand in for four roles.
from databricks.sdk import WorkspaceClient
w = WorkspaceClient()
ids = {sp.display_name: sp.application_id for sp in w.service_principals.list()
       if sp.display_name and sp.display_name.startswith("de_prep_")}
print(ids)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. The hierarchy, demonstrated
# MAGIC
# MAGIC A scratch catalog, one grant at the **schema** level, and a table created
# MAGIC **afterwards**. If inheritance works the way rule 1 says, the new table is already
# MAGIC covered.

# COMMAND ----------

analyst = ids["de_prep_analyst"]

spark.sql(f"DROP CATALOG IF EXISTS {DEMO} CASCADE")
spark.sql(f"CREATE CATALOG {DEMO}")
spark.sql(f"CREATE SCHEMA {DEMO}.s")
spark.sql(f"GRANT SELECT ON SCHEMA {DEMO}.s TO `{analyst}`")

# the table does not exist yet at the moment of the grant
spark.sql(f"CREATE TABLE {DEMO}.s.created_later (id INT)")

display(spark.sql(f"SHOW GRANTS ON TABLE {DEMO}.s.created_later"))

# COMMAND ----------

# MAGIC %md
# MAGIC Read that output carefully. The grant is listed against the table, and
# MAGIC `ObjectType` says **SCHEMA** and `ObjectKey` names the schema. The privilege
# MAGIC applies to the table; it does not *live* on the table.
# MAGIC
# MAGIC That distinction is the whole lesson. To revoke it you must revoke it where it
# MAGIC lives — a `REVOKE ... ON TABLE` removes a grant that was never there.

# COMMAND ----------

spark.sql(f"REVOKE SELECT ON TABLE {DEMO}.s.created_later FROM `{analyst}`")
print("REVOKE ON TABLE ran without error. Grants afterwards:")
display(spark.sql(f"SHOW GRANTS ON TABLE {DEMO}.s.created_later"))

# COMMAND ----------

# MAGIC %md
# MAGIC Still there. `REVOKE ... ON TABLE` reported success and removed nothing, because
# MAGIC there was no table-level grant to remove. Nothing failed, nothing changed, and an
# MAGIC access review that ticked this off is now wrong.
# MAGIC
# MAGIC Revoke it where it lives:

# COMMAND ----------

spark.sql(f"REVOKE SELECT ON SCHEMA {DEMO}.s FROM `{analyst}`")
print("after REVOKE ON SCHEMA:")
display(spark.sql(f"SHOW GRANTS ON TABLE {DEMO}.s.created_later"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Two surfaces that both know the answer — if you ask for it
# MAGIC
# MAGIC `SHOW GRANTS` names the origin in `ObjectType`. `information_schema.table_privileges`
# MAGIC carries it too, in a column called **`inherited_from`** — `NONE` for a grant that
# MAGIC really is on the table, `SCHEMA` or `CATALOG` for one that is not.
# MAGIC
# MAGIC The trap is not that the information is missing. It is that the obvious query
# MAGIC — `SELECT grantee, table_name, privilege_type` — does not select the column that
# MAGIC carries it, and the result looks complete without it.

# COMMAND ----------

spark.sql(f"GRANT SELECT ON SCHEMA {DEMO}.s TO `{analyst}`")

print("SHOW GRANTS ON TABLE — carries ObjectType:")
display(spark.sql(f"SHOW GRANTS ON TABLE {DEMO}.s.created_later"))

# COMMAND ----------

print("information_schema.table_privileges — same grant, with inherited_from:")
display(spark.sql(f"""
    SELECT grantee, table_schema, table_name, privilege_type, inherited_from
    FROM {DEMO}.information_schema.table_privileges
    WHERE table_schema = 's'
"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Traversal: the privilege you hold and cannot use
# MAGIC
# MAGIC `USE CATALOG` and `USE SCHEMA` are not read privileges. They are the right to
# MAGIC *see that something exists* and to name it. Without both, `SELECT` does nothing.
# MAGIC
# MAGIC ### First, a spelling trap worth more than it sounds
# MAGIC
# MAGIC You **grant** `USE CATALOG` with a space. `information_schema` **records** it as
# MAGIC `USE_CATALOG` with an underscore. Filter on the form you typed and you match zero
# MAGIC rows — and an access report that matches zero rows does not look broken. It looks
# MAGIC like nobody has access.

# COMMAND ----------

display(spark.sql(f"""
    SELECT DISTINCT privilege_type
    FROM {DEMO}.information_schema.catalog_privileges
    UNION
    SELECT DISTINCT privilege_type
    FROM {DEMO}.information_schema.schema_privileges
    ORDER BY 1
"""))

# COMMAND ----------

auditor = ids["de_prep_auditor"]
spark.sql(f"GRANT SELECT ON CATALOG {DEMO} TO `{auditor}`")

# Give the analyst a complete chain, so the two rows below differ for a reason.
spark.sql(f"GRANT USE CATALOG ON CATALOG {DEMO} TO `{analyst}`")
spark.sql(f"GRANT USE SCHEMA ON SCHEMA {DEMO}.s TO `{analyst}`")
spark.sql(f"GRANT USE CATALOG ON CATALOG {DEMO} TO `{auditor}`")

for who, label in ((analyst, "analyst"), (auditor, "auditor")):
    uc = spark.sql(f"""
        SELECT count(*) c FROM {DEMO}.information_schema.catalog_privileges
        WHERE grantee = '{who}' AND privilege_type = 'USE_CATALOG'
    """).collect()[0]["c"]
    us = spark.sql(f"""
        SELECT count(*) c FROM {DEMO}.information_schema.schema_privileges
        WHERE grantee = '{who}' AND schema_name = 's' AND privilege_type = 'USE_SCHEMA'
    """).collect()[0]["c"]
    sel = spark.sql(f"""
        SELECT count(*) c FROM {DEMO}.information_schema.table_privileges
        WHERE grantee = '{who}' AND table_schema = 's' AND privilege_type = 'SELECT'
    """).collect()[0]["c"]
    print(f"{label:8} SELECT={bool(sel)}  USE CATALOG={bool(uc)}  USE SCHEMA={bool(us)}"
          f"  -> can actually read: {bool(sel and uc and us)}")

# COMMAND ----------

# MAGIC %md
# MAGIC One of them can read it and one cannot, and **`table_privileges` shows a `SELECT`
# MAGIC for both.** The auditor holds the privilege and cannot reach the schema, so an
# MAGIC access report built from that view alone is wrong about them.
# MAGIC
# MAGIC Effective access is a **conjunction across three levels**, and no single view
# MAGIC computes it for you.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Ownership beats everything
# MAGIC
# MAGIC An owner holds all privileges on the object implicitly — nothing appears in
# MAGIC `SHOW GRANTS` to say so. If an access review only reads grants, owners are
# MAGIC invisible in it.

# COMMAND ----------

display(spark.sql(f"""
    SELECT catalog_name, schema_name, schema_owner
    FROM {DEMO}.information_schema.schemata
"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. A worked access audit
# MAGIC
# MAGIC Over the teach catalog, where **every grant sits on the table it names**. That
# MAGIC makes `table_privileges` a complete and truthful answer here.

# COMMAND ----------

display(spark.sql(f"""
    SELECT grantee, table_schema, table_name, privilege_type
    FROM {TEACH}.information_schema.table_privileges
    WHERE table_schema = 'ops'
    ORDER BY grantee, table_name, privilege_type
"""))

# COMMAND ----------

# MAGIC %md
# MAGIC That query is correct for this catalog and only this catalog. Point it at one
# MAGIC where grants sit at several levels and it returns the same shape, the same row
# MAGIC count, and an answer that will not survive an auditor's second question.
# MAGIC
# MAGIC ## Recap
# MAGIC
# MAGIC | Question | Answer it with |
# MAGIC |---|---|
# MAGIC | Does this principal have the privilege? | `information_schema.*_privileges` |
# MAGIC | Where is it granted, so I can revoke it? | `SHOW GRANTS` → `ObjectType`, or `table_privileges.inherited_from` |
# MAGIC | Can they actually reach the table? | `USE CATALOG` **and** `USE SCHEMA` **and** the privilege |
# MAGIC | Who has it without a grant? | the owner — check `*_owner` |

# COMMAND ----------

spark.sql(f"DROP CATALOG IF EXISTS {DEMO} CASCADE")
print("cleaned up")
