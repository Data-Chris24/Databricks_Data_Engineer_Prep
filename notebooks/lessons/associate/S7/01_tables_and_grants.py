# Databricks notebook source
# MAGIC %md
# MAGIC # Managed tables and grants — `ASSOC-S7-O1`, `ASSOC-S7-O2`

# COMMAND ----------

CATALOG, SCHEMA = "workspace", "de_prep"
spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Managed vs external — the difference is lifecycle
# MAGIC
# MAGIC A **managed** table's storage is owned by Unity Catalog, so `DROP TABLE` deletes
# MAGIC the data. An **external** table points at storage you manage, so dropping it
# MAGIC removes only the registration.
# MAGIC
# MAGIC That single difference is what most exam questions on this objective turn on.

# COMMAND ----------

display(spark.sql("DESCRIBE EXTENDED s7_teach_customers").filter(
    "col_name IN ('Type', 'Location', 'Provider', 'Catalog', 'Database')"))

# COMMAND ----------

# MAGIC %md
# MAGIC `Type: MANAGED` means Unity Catalog owns the layout — which is also what lets
# MAGIC predictive optimization compact, cluster and vacuum it for you. Prefer managed
# MAGIC unless something outside Databricks needs to own the files.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Traversal privileges
# MAGIC
# MAGIC Reaching an object needs privileges on **every container above it**:
# MAGIC
# MAGIC ```
# MAGIC USE CATALOG  →  USE SCHEMA  →  SELECT
# MAGIC ```
# MAGIC
# MAGIC A grant on the table alone leaves a user unable to get to it. This is the most
# MAGIC common Unity Catalog puzzle, and the error rarely names the missing traversal
# MAGIC privilege.

# COMMAND ----------

display(spark.sql(f"SHOW GRANTS ON SCHEMA {CATALOG}.{SCHEMA}"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Inheritance is dynamic
# MAGIC
# MAGIC Privileges flow metastore → catalog → schema → table, and objects created
# MAGIC **later** are covered too. A broad grant at catalog level silently covers
# MAGIC everything anyone adds afterwards — which is why least privilege usually means
# MAGIC granting at schema or table level.

# COMMAND ----------

# Current user's effective privileges on this schema.
display(spark.sql(f"SHOW GRANTS `{spark.sql('SELECT current_user()').collect()[0][0]}` ON SCHEMA {CATALOG}.{SCHEMA}"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. A view as a governance boundary
# MAGIC
# MAGIC The simplest way to expose a permitted subset: select the columns you allow,
# MAGIC grant on the view, withhold on the table. No duplicate data, always current.

# COMMAND ----------

spark.sql("""
    CREATE OR REPLACE VIEW s7_teach_customers_safe AS
    SELECT customer_id, region, lifetime_value
    FROM s7_teach_customers
""")
display(spark.sql("SELECT * FROM s7_teach_customers_safe LIMIT 5"))
print("email and full_name are simply not reachable through this view")

# COMMAND ----------

# MAGIC %md
# MAGIC A view stops being enough when different users need **different slices of the
# MAGIC same rows** — that is what masks and row filters are for. Next notebook.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Next
# MAGIC
# MAGIC Continue with the next lesson notebook: [02_masking_and_filters](./02_masking_and_filters).
# MAGIC
# MAGIC When the lessons are done, open the graded assignment: [ASSOC-S7 assignment notebook](../../../assignments/ASSOC-S7/assignment) · [the task](../../../assignments/ASSOC-S7/README.md).
