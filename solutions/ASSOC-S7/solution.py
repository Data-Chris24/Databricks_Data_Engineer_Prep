# Databricks notebook source
# MAGIC %md
# MAGIC # ASSOC-S7 assignment — reference solution
# MAGIC
# MAGIC Three kinds of sensitive column and three audiences. The lesson's single mask
# MAGIC cannot express this.

# COMMAND ----------

from pyspark.sql import functions as F

CATALOG, SCHEMA = "workspace", "de_prep"
spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")
SRC = "s7_assess_employees"
GOVERNED = "s7_governed_employees"

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. A governed copy, not a modified source
# MAGIC
# MAGIC The published table carries the protections. `national_id` is **hashed
# MAGIC irreversibly** rather than masked, because a mask can be lifted by anyone who can
# MAGIC alter the table, while a hash removes the value from the data entirely.

# COMMAND ----------

emp = spark.table(SRC)

governed = emp.select(
    "employee_id",
    "full_name",
    # sha2 is one-way: the original national_id is not recoverable from the table.
    F.sha2(F.col("national_id"), 256).alias("national_id_hash"),
    "region",
    "department",
    "salary",
    "case_note",
    "hired_on",
)
governed.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(GOVERNED)
print("governed rows:", spark.table(GOVERNED).count())

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. A mask per sensitivity kind
# MAGIC
# MAGIC Different columns need different treatment, which is why one mask will not do:
# MAGIC
# MAGIC | Column | Treatment | Why |
# MAGIC |---|---|---|
# MAGIC | `salary` | null outside HR | aggregate-safe, row-unsafe |
# MAGIC | `case_note` | suppressed outside HR | free text may contain anything |

# COMMAND ----------

# Two things worth noticing here.
#
# 1. Every rule keeps a break-glass principal. A policy that excludes *everyone* -
#    the owner included - is a real and common mistake: the data becomes unauditable
#    and you cannot even verify your own work.
#
# 2. `is_account_group_member` and `is_member` are NOT the same function.
#      is_account_group_member('admins')  -> account-level group
#      is_member('admins')                -> workspace-level group
#    A user can be a workspace admin and not be in any account group of that name,
#    which is exactly the case on Free Edition. Use the account-level check for
#    portable UC policies, and know the workspace-level one exists - picking the
#    wrong one silently denies everyone.
spark.sql("""
    CREATE OR REPLACE FUNCTION s7_mask_salary(salary DOUBLE)
    RETURN CASE
        WHEN is_account_group_member('hr') OR is_member('admins')
        THEN salary ELSE NULL END
""")
spark.sql("""
    CREATE OR REPLACE FUNCTION s7_mask_case_note(note STRING)
    RETURN CASE
        WHEN is_account_group_member('hr') OR is_member('admins')
        THEN note ELSE '[REDACTED]' END
""")

spark.sql(f"ALTER TABLE {GOVERNED} ALTER COLUMN salary SET MASK s7_mask_salary")
spark.sql(f"ALTER TABLE {GOVERNED} ALTER COLUMN case_note SET MASK s7_mask_case_note")
print("masks applied to salary and case_note")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. A row filter for regional scoping
# MAGIC
# MAGIC Masking a value does not remove a row. Regional managers must not see other
# MAGIC regions at all, which is a filter.

# COMMAND ----------

spark.sql("""
    CREATE OR REPLACE FUNCTION s7_filter_employee_region(region STRING)
    RETURN is_account_group_member('hr')
        OR is_member('admins')
        OR is_account_group_member('global_readers')
        OR is_account_group_member(concat('region_', region))
""")
spark.sql(f"ALTER TABLE {GOVERNED} SET ROW FILTER s7_filter_employee_region ON (region)")
print("row filter applied on region")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. What the current session sees
# MAGIC
# MAGIC This session is a workspace admin, so it sees everything — which is the point
# MAGIC of keeping a break-glass group. A non-admin outside `hr` would see redacted
# MAGIC notes, null salaries, and only their own region's rows.

# COMMAND ----------

display(spark.sql(f"SELECT * FROM {GOVERNED} LIMIT 5"))
print("visible rows for this session:", spark.table(GOVERNED).count())

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Fixtures
# MAGIC
# MAGIC The graded suite reads the **underlying** table for structural facts and the
# MAGIC governed table for what a least-privileged caller sees.

# COMMAND ----------

import json
src = spark.table(SRC)
raw_governed = spark.sql(f"SELECT * FROM {GOVERNED}")

fixtures = {
    "source_rows": src.count(),
    "visible_rows_unprivileged": raw_governed.count(),
    "distinct_hashes": spark.sql(
        f"SELECT count(DISTINCT national_id_hash) AS n FROM {GOVERNED}").collect()[0]["n"],
    "hash_length": len(spark.sql(
        f"SELECT national_id_hash FROM {GOVERNED} LIMIT 1").collect()[0][0]) if raw_governed.count() else 64,
    "regions": sorted(r["region"] for r in src.select("region").distinct().collect()),
}
print(json.dumps(fixtures, indent=2))
