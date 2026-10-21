# Databricks notebook source
# MAGIC %md
# MAGIC # PRO-S8 — generate the `teach` and `assess` governance structures
# MAGIC
# MAGIC Unity Catalog metadata and the permission inheritance model. The pairing differs
# MAGIC in **where the grants live**.
# MAGIC
# MAGIC ## What makes the assignment un-copyable
# MAGIC
# MAGIC 1. **Teach grants everything at the table.** So `information_schema.table_privileges`
# MAGIC    is a complete and truthful picture, and an audit written against it is correct.
# MAGIC 2. **Assess scatters grants across catalog, schema and table.** `table_privileges`
# MAGIC    still lists every one of them against the table — inheritance is *materialised*
# MAGIC    there, with nothing to say where the grant actually lives. The same query
# MAGIC    returns the same shape and a different truth.
# MAGIC 3. **Some principals hold a privilege they cannot exercise.** A `SELECT` inherited
# MAGIC    from the catalog is inert without `USE CATALOG` and `USE SCHEMA`. No view says
# MAGIC    so; you have to compose the traversal chain yourself.
# MAGIC 4. **Documentation is split.** Teach puts every description in a table comment.
# MAGIC    Assess spreads it across table comments, column comments and tags, so counting
# MAGIC    `tables.comment` under-reports what is actually documented.

# COMMAND ----------

from databricks.sdk import WorkspaceClient
from databricks.sdk.service import iam

w = WorkspaceClient()

TEACH, ASSESS = "pro_s8_teach", "pro_s8_assess"
PRINCIPALS = ["de_prep_analyst", "de_prep_engineer", "de_prep_auditor", "de_prep_intern"]

# COMMAND ----------

# MAGIC %md
# MAGIC ## Principals
# MAGIC
# MAGIC Unity Catalog will not grant to a workspace-local group — it needs an account-level
# MAGIC principal. Service principals are account-level, so four of them stand in for the
# MAGIC four roles. Creating them is idempotent.

# COMMAND ----------

existing = {sp.display_name: sp for sp in w.service_principals.list()}
ids = {}
for name in PRINCIPALS:
    sp = existing.get(name) or w.service_principals.create(display_name=name)
    ids[name] = sp.application_id
    print(f"{name:18} {sp.application_id}")

def grant(privs, obj_type, obj, principal):
    p = ids.get(principal, principal)
    spark.sql(f"GRANT {', '.join(privs)} ON {obj_type} {obj} TO `{p}`")

# COMMAND ----------

# MAGIC %md
# MAGIC ## `teach` — every grant sits on the object it names

# COMMAND ----------

spark.sql(f"DROP CATALOG IF EXISTS {TEACH} CASCADE")
spark.sql(f"CREATE CATALOG {TEACH} COMMENT 'Teaching catalog for PRO-S8'")
spark.sql(f"CREATE SCHEMA {TEACH}.ops COMMENT 'Operational tables'")

TEACH_TABLES = {
    "shipments": "One row per shipment, from booking to delivery",
    "facilities": "Depot reference data, one row per facility",
    "carriers": "Carrier reference data",
}
for t, comment in TEACH_TABLES.items():
    spark.sql(f"""
        CREATE TABLE {TEACH}.ops.{t}
        (id INT COMMENT 'surrogate key', name STRING COMMENT 'display name')
        COMMENT '{comment}'
    """)
    spark.sql(f"ALTER TABLE {TEACH}.ops.{t} SET TAGS ('domain' = 'logistics')")

# Traversal for everyone, then table-level SELECT. Flat and legible.
for p in PRINCIPALS:
    grant(["USE CATALOG"], "CATALOG", TEACH, p)
    grant(["USE SCHEMA"], "SCHEMA", f"{TEACH}.ops", p)
for t in TEACH_TABLES:
    for p in ("de_prep_analyst", "de_prep_engineer", "de_prep_auditor"):
        grant(["SELECT"], "TABLE", f"{TEACH}.ops.{t}", p)
grant(["MODIFY"], "TABLE", f"{TEACH}.ops.shipments", "de_prep_engineer")

print("teach built")

# COMMAND ----------

# MAGIC %md
# MAGIC ## `assess` — grants at three different levels, and gaps in the traversal chain

# COMMAND ----------

spark.sql(f"DROP CATALOG IF EXISTS {ASSESS} CASCADE")
spark.sql(f"CREATE CATALOG {ASSESS} COMMENT 'Assessment catalog for PRO-S8'")
spark.sql(f"CREATE SCHEMA {ASSESS}.sales COMMENT 'Revenue and orders'")
spark.sql(f"CREATE SCHEMA {ASSESS}.hr")   # deliberately undocumented

# COMMAND ----------

# Table comments: some present, some absent. Documentation also lives in column
# comments and in tags, so counting tables.comment alone under-reports.
spark.sql(f"""
    CREATE TABLE {ASSESS}.sales.orders (
        order_id STRING COMMENT 'natural key from the order system',
        customer_id STRING COMMENT 'FK to sales.customers',
        amount DOUBLE COMMENT 'order value in GBP',
        placed_on DATE)
    COMMENT 'One row per customer order'
""")
spark.sql(f"""
    CREATE TABLE {ASSESS}.sales.customers (
        customer_id STRING COMMENT 'natural key',
        email STRING,
        region STRING COMMENT 'sales region')
""")
spark.sql(f"CREATE TABLE {ASSESS}.sales.order_lines (order_id STRING, sku STRING, qty INT)")
spark.sql(f"""
    CREATE TABLE {ASSESS}.hr.employees (
        employee_id STRING COMMENT 'payroll number',
        full_name STRING,
        salary DOUBLE COMMENT 'annual gross')
    COMMENT 'Employee master'
""")
spark.sql(f"CREATE TABLE {ASSESS}.hr.absences (employee_id STRING, days INT)")

# COMMAND ----------

# Tags: the `customers` table has no comment, but its purpose is recorded as a tag -
# so "undocumented" depends entirely on where you look.
spark.sql(f"ALTER TABLE {ASSESS}.sales.orders SET TAGS ('domain' = 'sales', 'certified' = 'true')")
spark.sql(f"ALTER TABLE {ASSESS}.sales.customers SET TAGS ('domain' = 'sales', 'description' = 'Customer master record')")
spark.sql(f"ALTER TABLE {ASSESS}.hr.employees SET TAGS ('domain' = 'people')")
spark.sql(f"ALTER TABLE {ASSESS}.sales.customers ALTER COLUMN email SET TAGS ('pii' = 'true')")
spark.sql(f"ALTER TABLE {ASSESS}.hr.employees ALTER COLUMN full_name SET TAGS ('pii' = 'true')")
spark.sql(f"ALTER TABLE {ASSESS}.hr.employees ALTER COLUMN salary SET TAGS ('pii' = 'true', 'sensitivity' = 'high')")
print("assess objects built")

# COMMAND ----------

# MAGIC %md
# MAGIC ### The grants
# MAGIC
# MAGIC Read this block as the thing the assignment has to reconstruct from the catalog.

# COMMAND ----------

# analyst: SELECT inherited from the CATALOG, and full traversal. Effective everywhere.
grant(["USE CATALOG", "SELECT"], "CATALOG", ASSESS, "de_prep_analyst")
grant(["USE SCHEMA"], "SCHEMA", f"{ASSESS}.sales", "de_prep_analyst")
grant(["USE SCHEMA"], "SCHEMA", f"{ASSESS}.hr", "de_prep_analyst")

# engineer: SELECT+MODIFY inherited from the SCHEMA sales, traversal only into sales.
grant(["USE CATALOG"], "CATALOG", ASSESS, "de_prep_engineer")
grant(["USE SCHEMA", "SELECT", "MODIFY"], "SCHEMA", f"{ASSESS}.sales", "de_prep_engineer")

# auditor: SELECT inherited from the CATALOG - but NO schema traversal anywhere.
# Every privilege it holds is inert.
grant(["USE CATALOG", "SELECT"], "CATALOG", ASSESS, "de_prep_auditor")

# intern: SELECT granted directly on one TABLE, and traversal into sales only.
grant(["USE CATALOG"], "CATALOG", ASSESS, "de_prep_intern")
grant(["USE SCHEMA"], "SCHEMA", f"{ASSESS}.sales", "de_prep_intern")
grant(["SELECT"], "TABLE", f"{ASSESS}.sales.orders", "de_prep_intern")

print("assess grants applied")

# COMMAND ----------

# MAGIC %md
# MAGIC ## The traps, measured

# COMMAND ----------

from pyspark.sql import functions as F

def origins(catalog):
    """Where each (principal, table, privilege) is really granted, per SHOW GRANTS."""
    rows = []
    for t in spark.sql(
            f"SELECT table_schema, table_name FROM {catalog}.information_schema.tables "
            "WHERE table_schema <> 'information_schema'").collect():
        fq = f"{catalog}.{t['table_schema']}.{t['table_name']}"
        for g in spark.sql(f"SHOW GRANTS ON TABLE {fq}").collect():
            rows.append((g["Principal"], t["table_schema"], t["table_name"],
                         g["ActionType"], g["ObjectType"]))
    return spark.createDataFrame(
        rows, "principal STRING, table_schema STRING, table_name STRING, "
              "privilege STRING, granted_at STRING")

teach_origins = origins(TEACH)
assess_origins = origins(ASSESS)

print("teach  grant origins:", sorted({r["granted_at"] for r in teach_origins.collect()}))
print("assess grant origins:", sorted({r["granted_at"] for r in assess_origins.collect()}))

# COMMAND ----------

# Trap 1: in teach every grant is on the table, so table_privileges tells the truth.
t_levels = {r["granted_at"] for r in teach_origins.collect()}
assert t_levels == {"TABLE"}, f"teach should be flat, got {t_levels}"

# In assess it is not, so the same query silently misreports the level.
a_levels = {r["granted_at"] for r in assess_origins.collect()}
assert a_levels == {"CATALOG", "SCHEMA", "TABLE"}, f"assess levels: {a_levels}"
inherited = assess_origins.filter("granted_at <> 'TABLE'").count()
print(f"assess (principal, table, privilege) rows granted above the table: {inherited}")
assert inherited > 0

# COMMAND ----------

# Trap 2: table_privileges materialises inheritance against the table. The origin is
# recorded, in `inherited_from` - a column the obvious query does not select.
ip = spark.sql(
    f"SELECT grantee, table_schema, table_name, privilege_type, inherited_from "
    f"FROM {ASSESS}.information_schema.table_privileges "
    f"WHERE table_schema <> 'information_schema'")
print(f"table_privileges rows: {ip.count()}")
print(f"SHOW GRANTS rows     : {assess_origins.count()}")
assert ip.count() == assess_origins.count(), \
    "the two surfaces should agree on which grants exist"

levels = {r["inherited_from"] for r in ip.collect()}
print("inherited_from values present:", sorted(levels))
assert levels == {"NONE", "SCHEMA", "CATALOG"}, levels
not_on_table = ip.filter("inherited_from <> 'NONE'").count()
print(f"{not_on_table} of {ip.count()} rows describe a grant that is NOT on the table")
assert not_on_table > 0

# And in teach every row is a real table grant, so the column is uninformative there.
tp = spark.sql(f"SELECT inherited_from FROM {TEACH}.information_schema.table_privileges "
               "WHERE table_schema = 'ops'")
assert {r["inherited_from"] for r in tp.collect()} == {"NONE"}, \
    "teach should have no inherited grants"
print("teach: every grant is on the table it names")

# COMMAND ----------

# Trap 3: privileges nobody can exercise, because the traversal chain is broken.
def has(priv, obj_type, obj, principal_app_id):
    q = {"CATALOG": f"{obj}.information_schema.catalog_privileges",
         "SCHEMA": f"{obj.split('.')[0]}.information_schema.schema_privileges"}[obj_type]
    where = "" if obj_type == "CATALOG" else f" AND schema_name = '{obj.split('.')[1]}'"
    return spark.sql(
        f"SELECT count(*) c FROM {q} WHERE grantee = '{principal_app_id}' "
        f"AND privilege_type = '{priv}'{where}").collect()[0]["c"] > 0

inert = []
for name in PRINCIPALS:
    app = ids[name]
    uc = has("USE CATALOG", "CATALOG", ASSESS, app)
    for schema in ("sales", "hr"):
        us = has("USE SCHEMA", "SCHEMA", f"{ASSESS}.{schema}", app)
        holds = assess_origins.filter(
            (F.col("principal") == app) & (F.col("table_schema") == schema) &
            (F.col("privilege") == "SELECT")).count()
        if holds and not (uc and us):
            inert.append((name, schema, holds, uc, us))

print(f"{'principal':18} {'schema':8} {'SELECTs held':>13} {'USE CATALOG':>12} {'USE SCHEMA':>11}")
for row in inert:
    print(f"{row[0]:18} {row[1]:8} {row[2]:>13} {str(row[3]):>12} {str(row[4]):>11}")
assert inert, "no principal holds an inert privilege - the traversal trap is missing"
print(f"\n{len(inert)} (principal, schema) pairs hold SELECT they cannot exercise")

# COMMAND ----------

# Trap 4: documentation is not all in one place.
tables = spark.sql(
    f"SELECT table_schema, table_name, comment FROM {ASSESS}.information_schema.tables "
    "WHERE table_schema <> 'information_schema'")
with_comment = tables.filter("comment IS NOT NULL").count()
tagged = spark.sql(
    f"SELECT DISTINCT schema_name, table_name FROM {ASSESS}.information_schema.table_tags"
).count()
col_commented = spark.sql(
    f"SELECT DISTINCT table_schema, table_name FROM {ASSESS}.information_schema.columns "
    "WHERE comment IS NOT NULL AND table_schema <> 'information_schema'").count()

print(f"tables total              : {tables.count()}")
print(f"  with a table comment    : {with_comment}")
print(f"  with at least one tag   : {tagged}")
print(f"  with a column comment   : {col_commented}")
assert with_comment < tables.count(), "every table is commented - no gap to find"
assert tagged > with_comment or col_commented > with_comment, \
    "table comments already cover everything documented elsewhere"
print("\nall traps hold")
