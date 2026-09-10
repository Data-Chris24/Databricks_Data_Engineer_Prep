# Databricks notebook source
# MAGIC %md
# MAGIC # ASSOC-S7 assignment — your work goes here
# MAGIC
# MAGIC Read `README.md` in this folder for the task and the output contract.
# MAGIC
# MAGIC **The lesson's single mask will not satisfy this. One of the requirements cannot be met by masking at all.**
# MAGIC
# MAGIC When you are done, go back to the study app and press **Grade my assignment**.
# MAGIC Each failing check says what it expected and why.

# COMMAND ----------

from pyspark.sql import functions as F

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")
SOURCE = "s7_assess_employees"
TARGET = "s7_governed_employees"
employees = spark.table(SOURCE)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 0 — inspect the source
# MAGIC
# MAGIC Which columns are direct identifiers, which are free text, which only scope rows?

# COMMAND ----------

# display(employees.limit(5)); employees.printSchema()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1 — publish the table without the identifier
# MAGIC
# MAGIC Requirement 1: `national_id` must not exist in the published table. A mask can be dropped; an irreversible hash cannot be reversed. Keep the contracted column order.

# COMMAND ----------

# governed = employees.withColumn("national_id_hash", F.sha2(F.col("national_id"), 256)).select(
#     "employee_id", "full_name", "national_id_hash", "region", "department", "salary", "case_note", "hired_on")
# governed.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(TARGET)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2 — column masks for salary and case_note
# MAGIC
# MAGIC Requirement 2: reveal them only to HR. A mask is a SQL function that receives the column value and returns what the viewer may see. Requirement 4: keep a break-glass principal.

# COMMAND ----------

# spark.sql("""CREATE OR REPLACE FUNCTION s7_mask_salary(v DOUBLE) RETURN
#   CASE WHEN is_account_group_member('...') THEN v ELSE NULL END""")
# spark.sql(f"ALTER TABLE {TARGET} ALTER COLUMN salary SET MASK s7_mask_salary")
# ... and the same idea for case_note

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3 — a row filter by region
# MAGIC
# MAGIC Requirement 3: a regional manager sees only their region; HR and the break-glass principal see everything.

# COMMAND ----------

# spark.sql("""CREATE OR REPLACE FUNCTION s7_region_filter(region STRING) RETURN ...""")
# spark.sql(f"ALTER TABLE {TARGET} SET ROW FILTER s7_region_filter ON (region)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Check yourself before grading

# COMMAND ----------

# display(spark.sql(f"DESCRIBE TABLE EXTENDED {TARGET}"))
# display(spark.table(TARGET).limit(5))   # as you: what do you see, and should you?
