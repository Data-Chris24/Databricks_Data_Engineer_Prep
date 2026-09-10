# Databricks notebook source
# MAGIC %md
# MAGIC # PRO-S4 · Lakehouse Federation
# MAGIC
# MAGIC **Objective:** `PRO-S4-O2`
# MAGIC
# MAGIC Delta Sharing sends your data out. Federation brings someone else's data **in** —
# MAGIC without copying it either. You register a connection to a foreign system, mount it
# MAGIC as a catalog, and query it as if it were yours. Unity Catalog governs it the same
# MAGIC way it governs everything else.
# MAGIC
# MAGIC | | Two nouns |
# MAGIC |---|---|
# MAGIC | **Connection** | credentials plus an address for a foreign system |
# MAGIC | **Foreign catalog** | one database on that system, mounted into UC |
# MAGIC
# MAGIC > **What this workspace can and cannot do.** Every statement below runs. The
# MAGIC > *query path* does not — this metastore cannot open an outbound JDBC connection
# MAGIC > from the federation engine, including to its own SQL warehouse. The measured
# MAGIC > error is printed at the end rather than described.

# COMMAND ----------

from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
CONN = "pro_s4_lesson_conn"
FCAT = "pro_s4_lesson_foreign"

spark.sql(f"DROP CATALOG IF EXISTS {FCAT}")
spark.sql(f"DROP CONNECTION IF EXISTS {CONN}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. A connection is a securable, not a config file
# MAGIC
# MAGIC This is the governance point of the whole feature. The credential lives **once**,
# MAGIC inside Unity Catalog, owned by whoever created it. Nobody who queries through the
# MAGIC connection ever sees it, and there is no per-notebook secret to leak.
# MAGIC
# MAGIC Supported types include `postgresql`, `mysql`, `sqlserver`, `redshift`,
# MAGIC `snowflake`, `bigquery`, `databricks`, `oracle`, `teradata` and Hive Metastore.

# COMMAND ----------

spark.sql(f"""
    CREATE CONNECTION {CONN} TYPE postgresql
    OPTIONS (host 'upstream.example.invalid', port '5432',
             user 'reader', password 'not-a-real-password')
    COMMENT 'Lesson connection - deliberately unreachable'
""")

display(spark.sql("""
    SELECT connection_name, connection_type, url, created_by
    FROM system.information_schema.connections
    WHERE connection_name LIKE 'pro_s4%'
"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ### Nothing was checked
# MAGIC
# MAGIC That host does not exist, the password is a placeholder, and the statement
# MAGIC succeeded. **Federation DDL is lazy** — a connection is metadata until something
# MAGIC tries to use it.
# MAGIC
# MAGIC Which means a green deployment tells you nothing about whether your federation
# MAGIC works. Only a query does.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. A foreign catalog mounts one database

# COMMAND ----------

spark.sql(f"""
    CREATE FOREIGN CATALOG {FCAT}
    USING CONNECTION {CONN}
    OPTIONS (database 'analytics')
""")
display(spark.sql("SHOW CATALOGS LIKE 'pro_s4*'"))

# COMMAND ----------

# MAGIC %md
# MAGIC Created, again without contacting anything. Foreign schemas and tables appear
# MAGIC beneath it and are **discovered on demand** — you do not declare them, and they
# MAGIC follow the source when it changes.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Governance: it is a catalog like any other
# MAGIC
# MAGIC The inheritance model from `PRO-S8` applies unchanged. Grant on the foreign
# MAGIC catalog and it applies to every foreign table under it — including ones the
# MAGIC upstream team creates tomorrow.
# MAGIC
# MAGIC The connection carries its own privilege, `USE CONNECTION`, which is the right to
# MAGIC **build a foreign catalog over it** — separate from reading data through one.

# COMMAND ----------

ids = {sp.display_name: sp.application_id for sp in w.service_principals.list()
       if sp.display_name and sp.display_name.startswith("de_prep_")}

if ids:
    analyst = ids.get("de_prep_analyst")
    spark.sql(f"GRANT USE CONNECTION ON CONNECTION {CONN} TO `{analyst}`")
    spark.sql(f"GRANT USE CATALOG, SELECT ON CATALOG {FCAT} TO `{analyst}`")
    display(spark.sql(f"SHOW GRANTS ON CONNECTION {CONN}"))
    display(spark.sql(f"SHOW GRANTS ON CATALOG {FCAT}"))
else:
    print("run the PRO-S8 generator first to create the de_prep_* principals")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Dependencies are enforced
# MAGIC
# MAGIC A connection cannot be dropped while a foreign catalog is built on it. That is
# MAGIC the guardrail against pulling a credential out from under live queries.

# COMMAND ----------

try:
    spark.sql(f"DROP CONNECTION {CONN}")
    print("dropped")
except Exception as e:
    print("refused, as it should be:")
    print(" ", str(e).split("SQLSTATE")[0][:200].strip())

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Where it actually fails
# MAGIC
# MAGIC Everything so far succeeded against a host that does not exist. The first thing
# MAGIC to touch the source is the first thing to fail.

# COMMAND ----------

try:
    spark.sql(f"SHOW SCHEMAS IN {FCAT}").count()
    print("metadata fetched")
except Exception as e:
    print("first contact with the source:")
    print(" ", str(e).split("SQLSTATE")[0][:220].strip())

# COMMAND ----------

# MAGIC %md
# MAGIC `FAILED_JDBC.CONNECTION`, and note the URL is redacted in the error — UC will not
# MAGIC print a credential back at you even in a stack trace.
# MAGIC
# MAGIC **On this workspace that error is unavoidable**, including for a `databricks`-type
# MAGIC connection pointed at this workspace's own SQL warehouse. The federation engine
# MAGIC has no outbound JDBC path here. Measured, not assumed — the connection, the
# MAGIC foreign catalog and the grants all succeed; only the data path does not.
# MAGIC
# MAGIC ## 5. Federation versus a copy
# MAGIC
# MAGIC | | Federation | Ingest a copy |
# MAGIC |---|---|---|
# MAGIC | Freshness | live, always | as fresh as the last run |
# MAGIC | Load on the source | every query hits it | one read per run |
# MAGIC | Performance | bounded by the source and the network | Delta-native |
# MAGIC | Governance | UC, on the foreign catalog | UC, on your table |
# MAGIC | Good for | exploration, small dimensions, joins against something you do not own | anything hot, big, or repeatedly scanned |
# MAGIC
# MAGIC The trap is treating a foreign catalog as free. It is a live connection to
# MAGIC somebody's production database, and a careless join can put your Spark job in
# MAGIC their incident review. Federate to discover; ingest to serve.
# MAGIC
# MAGIC ## Recap
# MAGIC
# MAGIC | | |
# MAGIC |---|---|
# MAGIC | Register a source | `CREATE CONNECTION c TYPE <type> OPTIONS (...)` |
# MAGIC | Mount a database | `CREATE FOREIGN CATALOG fc USING CONNECTION c OPTIONS (database '...')` |
# MAGIC | Who may build on it | `GRANT USE CONNECTION ON CONNECTION c TO ...` |
# MAGIC | Who may read it | `GRANT USE CATALOG, SELECT ON CATALOG fc TO ...` |
# MAGIC | Inspect | `system.information_schema.connections` |
# MAGIC | Remember | none of the DDL validates anything |

# COMMAND ----------

spark.sql(f"DROP CATALOG IF EXISTS {FCAT}")
spark.sql(f"DROP CONNECTION IF EXISTS {CONN}")
print("cleaned up")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Next
# MAGIC
# MAGIC When the lessons are done, open the graded assignment: [PRO-S4 assignment notebook](../../../assignments/PRO-S4/assignment) · [the task](../../../assignments/PRO-S4/README.md).
