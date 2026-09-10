# Databricks notebook source
# MAGIC %md
# MAGIC # Column masks and row filters — `ASSOC-S7-O3`, `ASSOC-S7-O4`
# MAGIC
# MAGIC A view exposes a fixed subset to everyone who can query it. Masks and filters
# MAGIC are evaluated **per querying user**, so one table serves several audiences.

# COMMAND ----------

CATALOG, SCHEMA = "workspace", "de_prep"
spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")
me = spark.sql("SELECT current_user()").collect()[0][0]
print("running as:", me)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. A column mask
# MAGIC
# MAGIC A mask is a **function** attached to a column. It receives the column value and
# MAGIC returns what the querying user is allowed to see.
# MAGIC
# MAGIC `is_account_group_member()` is what makes it per-user — the same query returns
# MAGIC different values for different people.
# MAGIC
# MAGIC > **Two functions, not one.** `is_account_group_member('x')` tests an
# MAGIC > **account**-level group; `is_member('x')` tests a **workspace**-level group. A
# MAGIC > user can be a workspace admin and belong to no account group of that name — the
# MAGIC > case on Free Edition. Pick the wrong one and your policy silently denies
# MAGIC > everyone, including you.

# COMMAND ----------

spark.sql("""
    CREATE OR REPLACE FUNCTION s7_mask_email(email STRING)
    RETURN CASE
        WHEN is_account_group_member('support') THEN email
        ELSE regexp_replace(email, '^[^@]+', '****')
    END
""")
print("mask function created")

# COMMAND ----------

spark.sql("ALTER TABLE s7_teach_customers ALTER COLUMN email SET MASK s7_mask_email")
display(spark.sql("""
    SELECT current_user() AS me,
           is_account_group_member('admins') AS account_group_admins,
           is_member('admins')               AS workspace_group_admins
"""))
display(spark.sql("SELECT customer_id, email, region FROM s7_teach_customers LIMIT 5"))

# COMMAND ----------

# MAGIC %md
# MAGIC The addresses are masked because this session is not in the `support` group. The
# MAGIC **table name is unchanged** — every path to the data inherits the mask, including
# MAGIC views built on top of it, which is what makes this governance rather than
# MAGIC convention.

# COMMAND ----------

display(spark.sql("SELECT * FROM s7_teach_customers_safe LIMIT 3"))
print("a view over the table inherits the mask; it cannot be used to escape it")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. A row filter
# MAGIC
# MAGIC A mask changes a value **within** a row. A filter removes **rows** entirely.
# MAGIC Different mechanisms for different questions.

# COMMAND ----------

spark.sql("""
    CREATE OR REPLACE FUNCTION s7_filter_region(region STRING)
    RETURN is_account_group_member('all_regions') OR region = 'Northeast'
""")
spark.sql("ALTER TABLE s7_teach_customers SET ROW FILTER s7_filter_region ON (region)")

display(spark.sql("SELECT region, count(*) AS rows FROM s7_teach_customers GROUP BY region"))
print("only the permitted region is visible - the others are not hidden, they are absent")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Removing them again
# MAGIC
# MAGIC Worth doing explicitly so the lesson leaves the table as it found it, and so the
# MAGIC syntax is in front of you.

# COMMAND ----------

spark.sql("ALTER TABLE s7_teach_customers DROP ROW FILTER")
spark.sql("ALTER TABLE s7_teach_customers ALTER COLUMN email DROP MASK")
display(spark.sql("SELECT region, count(*) AS rows FROM s7_teach_customers GROUP BY region ORDER BY region"))
print("all regions visible again")

# COMMAND ----------

# MAGIC %md
# MAGIC ## What to carry forward
# MAGIC
# MAGIC | Need | Mechanism |
# MAGIC |---|---|
# MAGIC | Hide or transform a **value** | column mask |
# MAGIC | Remove **rows** | row filter |
# MAGIC | Expose a fixed subset to one audience | a view |
# MAGIC
# MAGIC Masks and filters attach to the **table**, so every query path inherits them.
# MAGIC
# MAGIC **ABAC** (`ASSOC-S7-O4`) takes this one step further: bind the rule to a *tag*
# MAGIC rather than to a named column, and every column tagged as sensitive is covered
# MAGIC the moment it is created. That removes the failure that actually happens — a new
# MAGIC table shipping unprotected because someone forgot.
# MAGIC
# MAGIC Now do the assignment. It has three kinds of sensitive column and three
# MAGIC audiences, and a single mask will not satisfy them.
