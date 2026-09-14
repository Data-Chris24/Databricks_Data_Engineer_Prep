# Databricks notebook source
# MAGIC %md
# MAGIC # ASSOC-S7 assignment — your work goes here
# MAGIC
# MAGIC The task and the output contract are in the next cell (the same text as `README.md` in the repo).
# MAGIC
# MAGIC **The lesson's single mask will not satisfy this. One of the requirements cannot be met by masking at all.**
# MAGIC
# MAGIC When you are done, go back to the study app and press **Grade my assignment**.
# MAGIC Each failing check says what it expected and why.

# COMMAND ----------

# MAGIC %md
# MAGIC <!-- task:begin  generated from README.md by tools/sync_assignment_tasks.py; edit the README, then re-run it -->
# MAGIC ## Assignment — `ASSOC-S7` Governance and Security
# MAGIC
# MAGIC **Objectives:** `ASSOC-S7-O1`, `O2`, `O3`, `O4`
# MAGIC
# MAGIC ### Before you start
# MAGIC
# MAGIC Work the two lessons in `notebooks/lessons/associate/S7/`, and generate the data
# MAGIC (`databricks bundle run generate_datasets_assoc_s7 -t free`).
# MAGIC
# MAGIC > **The lesson's single mask will not satisfy this.** It had one sensitive column and
# MAGIC > one audience. This has three kinds of sensitivity and three audiences, and one of
# MAGIC > the requirements cannot be met by masking at all.
# MAGIC
# MAGIC ### The task
# MAGIC
# MAGIC `workspace.de_prep.s7_assess_employees` holds employee records. Publish a governed
# MAGIC table that HR can use fully, regional managers can use for their own region, and
# MAGIC everyone else can use for headcount analysis without seeing anything personal.
# MAGIC
# MAGIC | Column | Sensitivity | Required treatment |
# MAGIC |---|---|---|
# MAGIC | `national_id` | direct identifier | **Must not exist in the published table.** Publish an irreversible hash instead |
# MAGIC | `case_note` | free text, may contain anything | Suppressed outside HR |
# MAGIC | `salary` | aggregate-safe, row-unsafe | Null outside HR |
# MAGIC | `region` | scoping attribute | Rows restricted to the viewer's region |
# MAGIC
# MAGIC ### The output contract
# MAGIC
# MAGIC **`workspace.de_prep.s7_governed_employees`**
# MAGIC
# MAGIC | Column | Type |
# MAGIC |---|---|
# MAGIC | `employee_id` | `STRING` |
# MAGIC | `full_name` | `STRING` |
# MAGIC | `national_id_hash` | `STRING` |
# MAGIC | `region` | `STRING` |
# MAGIC | `department` | `STRING` |
# MAGIC | `salary` | `DOUBLE` |
# MAGIC | `case_note` | `STRING` |
# MAGIC | `hired_on` | `DATE` |
# MAGIC
# MAGIC #### Requirements
# MAGIC
# MAGIC 1. **`national_id` must not appear in the published table.** A mask is not enough —
# MAGIC    masks can be dropped by anyone who can alter the table. Hash it irreversibly.
# MAGIC 2. **`salary` and `case_note` must carry column masks** that reveal them only to HR.
# MAGIC 3. **A row filter must scope rows by region**, so a regional manager sees only theirs.
# MAGIC 4. **Do not lock yourself out.** Every rule must keep a break-glass principal;
# MAGIC    a policy that excludes everyone is unauditable and unrecoverable.
# MAGIC 5. Column order matters — the tests compare the whole schema.
# MAGIC
# MAGIC ### Grading
# MAGIC
# MAGIC ```bash
# MAGIC databricks bundle run grade_assoc_s7 -t free --profile FREE
# MAGIC ```
# MAGIC
# MAGIC ### Hints
# MAGIC
# MAGIC <details><summary>Which group function do I use?</summary>
# MAGIC
# MAGIC `is_account_group_member('x')` tests an **account**-level group; `is_member('x')`
# MAGIC tests a **workspace**-level one. They are different, and on Free Edition a workspace
# MAGIC admin belongs to no account group of that name. Pick wrong and your policy denies
# MAGIC everyone.
# MAGIC </details>
# MAGIC
# MAGIC <details><summary>My table shows no rows at all</summary>
# MAGIC
# MAGIC Requirement 4. Your row filter excluded you too.
# MAGIC </details>
# MAGIC
# MAGIC <details><summary>Can I just mask national_id?</summary>
# MAGIC
# MAGIC Requirement 1. Ask what happens when someone runs `ALTER TABLE ... DROP MASK`. A hash
# MAGIC removes the value from the data; a mask only hides it.
# MAGIC </details>
# MAGIC <!-- task:end -->

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
