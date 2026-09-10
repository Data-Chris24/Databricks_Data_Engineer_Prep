# Databricks notebook source
# MAGIC %md
# MAGIC # PRO-S8 · Making data findable
# MAGIC
# MAGIC **Objective:** `PRO-S8-O1`
# MAGIC
# MAGIC A table nobody can find is a table nobody uses, and a table nobody trusts gets
# MAGIC rebuilt beside itself. Unity Catalog gives you three places to record what
# MAGIC something is — **comments**, **tags**, and **ownership** — and one place to read
# MAGIC all of it back: `information_schema`.

# COMMAND ----------

from pyspark.sql import functions as F

TEACH = "pro_s8_teach"
spark.sql(f"USE CATALOG {TEACH}")
spark.sql("USE SCHEMA ops")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Comments: prose, for a human reading the catalog
# MAGIC
# MAGIC Every securable takes one — catalog, schema, table, column, volume, function.
# MAGIC They are set at create time or altered later.

# COMMAND ----------

display(spark.sql(f"""
    SELECT table_name, comment
    FROM {TEACH}.information_schema.tables
    WHERE table_schema = 'ops'
    ORDER BY table_name
"""))

# COMMAND ----------

spark.sql("COMMENT ON TABLE facilities IS "
          "'Depot reference data, one row per facility. Sourced nightly from the WMS.'")
spark.sql("ALTER TABLE facilities ALTER COLUMN name COMMENT "
          "'Depot short name as printed on labels'")

display(spark.sql(f"""
    SELECT column_name, data_type, comment
    FROM {TEACH}.information_schema.columns
    WHERE table_schema = 'ops' AND table_name = 'facilities'
    ORDER BY ordinal_position
"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Tags: structured facts you can query
# MAGIC
# MAGIC A comment is for reading. A tag is for **filtering** — key/value pairs on a table
# MAGIC or a column, which is what makes "show me everything holding PII" a query rather
# MAGIC than a conversation.

# COMMAND ----------

spark.sql("ALTER TABLE shipments SET TAGS ('domain' = 'logistics', 'certified' = 'true')")
spark.sql("ALTER TABLE shipments ALTER COLUMN name SET TAGS ('pii' = 'false')")

display(spark.sql(f"""
    SELECT schema_name, table_name, tag_name, tag_value
    FROM {TEACH}.information_schema.table_tags
    ORDER BY table_name, tag_name
"""))

# COMMAND ----------

# MAGIC %md
# MAGIC Column tags live in their own view, and this is the one that earns its keep:

# COMMAND ----------

display(spark.sql(f"""
    SELECT schema_name, table_name, column_name, tag_name, tag_value
    FROM {TEACH}.information_schema.column_tags
    ORDER BY table_name, column_name
"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. `information_schema` is per-catalog, and it is filtered
# MAGIC
# MAGIC Two properties worth internalising before you build anything on top of it:
# MAGIC
# MAGIC 1. **It lives inside each catalog.** `pro_s8_teach.information_schema.tables`
# MAGIC    describes that catalog only. There is a `system.information_schema` spanning
# MAGIC    the metastore, but the per-catalog one is what you get everywhere.
# MAGIC 2. **You only see what you are allowed to see.** The views are filtered by the
# MAGIC    caller's privileges, so an inventory built by an admin and the same inventory
# MAGIC    built by an analyst are different inventories. That is a feature, and a trap
# MAGIC    if you forget it.

# COMMAND ----------

display(spark.sql(f"""
    SELECT table_name
    FROM {TEACH}.information_schema.tables
    WHERE table_schema = 'information_schema'
    ORDER BY table_name
"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. A documentation inventory
# MAGIC
# MAGIC The worked example: for every table, how well is it documented? Note that this
# MAGIC version asks only one question — *does the table have a comment* — which is enough
# MAGIC here because that is where all the documentation lives.

# COMMAND ----------

inventory = spark.sql(f"""
    SELECT
        t.table_schema,
        t.table_name,
        t.comment IS NOT NULL           AS has_comment,
        count(c.column_name)            AS column_count,
        count(c.comment)                AS documented_columns
    FROM {TEACH}.information_schema.tables t
    JOIN {TEACH}.information_schema.columns c
      ON c.table_schema = t.table_schema AND c.table_name = t.table_name
    WHERE t.table_schema = 'ops'
    GROUP BY t.table_schema, t.table_name, t.comment
    ORDER BY t.table_name
""")
display(inventory)

# COMMAND ----------

# MAGIC %md
# MAGIC ### Where this breaks
# MAGIC
# MAGIC `has_comment` is a fine measure of documentation **only while comments are the
# MAGIC only place documentation goes.** The moment a team starts recording purpose in a
# MAGIC tag, or describing a table entirely through its column comments, an inventory
# MAGIC built on `tables.comment` reports it as undocumented — confidently, and wrongly.
# MAGIC
# MAGIC The fix is not a cleverer query. It is deciding what "documented" means for your
# MAGIC organisation, writing that definition down, and then querying for *that*.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Ownership
# MAGIC
# MAGIC The owner is metadata too, and the most consequential kind: an owner holds every
# MAGIC privilege on the object implicitly and can grant it to others. "Who owns this"
# MAGIC is the first question of any access review.

# COMMAND ----------

display(spark.sql(f"""
    SELECT table_schema, table_name, table_owner, table_type
    FROM {TEACH}.information_schema.tables
    WHERE table_schema = 'ops'
    ORDER BY table_name
"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Recap
# MAGIC
# MAGIC | Want | Use | Read it back from |
# MAGIC |---|---|---|
# MAGIC | Prose for a human | `COMMENT ON` / `COMMENT` in DDL | `tables.comment`, `columns.comment` |
# MAGIC | A fact you can filter on | `SET TAGS` | `table_tags`, `column_tags` |
# MAGIC | Who is responsible | `ALTER ... OWNER TO` | `tables.table_owner` |
# MAGIC
# MAGIC Comments and tags are not alternatives. Comments say *what this is*; tags say
# MAGIC *what class of thing this is* — and only the second is queryable at scale.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Next
# MAGIC
# MAGIC Continue with the next lesson notebook: [02_inheritance](./02_inheritance).
# MAGIC
# MAGIC When the lessons are done, open the graded assignment: [PRO-S8 assignment notebook](../../../assignments/PRO-S8/assignment) · [the task](../../../assignments/PRO-S8/README.md).
