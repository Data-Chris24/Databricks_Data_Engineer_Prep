# Databricks notebook source
# MAGIC %md
# MAGIC # Reading a failure — `PRO-S9-O1`, `PRO-S9-O2`
# MAGIC
# MAGIC Teach data: `pro_s9_teach_raw`, one row of which will not cast.
# MAGIC
# MAGIC This failure is **loud**: something raises, the run shows FAILED, and the error
# MAGIC names the cause. That is the easy kind.

# COMMAND ----------

from pyspark.sql import functions as F

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")
raw = spark.table("pro_s9_teach_raw")
print("rows:", raw.count())

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Cause the failure and read what it says

# COMMAND ----------

try:
    raw.select(F.col("qty").cast("int")).collect()
    print("UNEXPECTED: the bad value cast cleanly")
except Exception as e:
    msg = str(e)
    print(f"{type(e).__name__}")
    print(msg[:400])

# COMMAND ----------

# MAGIC %md
# MAGIC The message names the value and usually the fix. Databricks error messages carry
# MAGIC an error class (`CAST_INVALID_INPUT`) and a SQLSTATE — both are searchable, and
# MAGIC the class is stable across versions in a way that the prose is not.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Find the offending rows rather than guessing
# MAGIC
# MAGIC `try_cast` returns null instead of raising, which turns "it failed" into "here
# MAGIC are the three rows responsible".

# COMMAND ----------

bad = raw.filter(F.expr("try_cast(qty AS INT) IS NULL"))
print("rows that will not cast:", bad.count())
display(bad)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Diagnostic sources, in the order worth trying
# MAGIC
# MAGIC | Source | Answers |
# MAGIC |---|---|
# MAGIC | The error message | what broke, often how to fix it |
# MAGIC | Run history | which task, and whether it is new |
# MAGIC | `DESCRIBE HISTORY` | what the table did, and when |
# MAGIC | Query profile | where the time and bytes went |
# MAGIC | Cluster logs | driver/executor detail (classic compute only) |
# MAGIC
# MAGIC Start narrow. Opening logs before checking whether the run is simply slower than
# MAGIC last week wastes the easy answer.

# COMMAND ----------

display(spark.sql("DESCRIBE HISTORY pro_s9_teach_raw").select(
    "version", "operation", "operationMetrics"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Repairing a failed run — `PRO-S9-O2`
# MAGIC
# MAGIC A multi-task job that fails partway does **not** roll back what earlier tasks
# MAGIC committed. Repairing a run re-executes only the failed tasks and their
# MAGIC dependants, which is why idempotent tasks matter: a repaired task runs again
# MAGIC from the start.
# MAGIC
# MAGIC ```bash
# MAGIC databricks jobs list-runs --job-id <id>
# MAGIC databricks jobs repair-run <run-id> --rerun-tasks failed_task
# MAGIC databricks jobs repair-run <run-id> --job-parameters '{"cutoff":"2026-03-01"}'
# MAGIC ```
# MAGIC
# MAGIC Parameter overrides on repair are how you re-run a task against a corrected
# MAGIC input without editing and redeploying the job.

# COMMAND ----------

# MAGIC %md
# MAGIC ## What to carry forward
# MAGIC
# MAGIC - Read the error class, not just the prose.
# MAGIC - `try_cast` converts a failure into a list of culprits.
# MAGIC - Repair re-runs failed tasks; earlier commits stand.
# MAGIC
# MAGIC **All of this assumes something failed.** The assignment's pipeline reports
# MAGIC SUCCESS every day and is wrong anyway — no exception, no error class, nothing in
# MAGIC the run state. Section 2 is about that case.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Next
# MAGIC
# MAGIC Continue with the next lesson notebook: [02_deploying_and_silent_failure](./02_deploying_and_silent_failure).
# MAGIC
# MAGIC When the lessons are done, open the graded assignment: [PRO-S9 assignment notebook](../../../assignments/PRO-S9/assignment) · [the task](../../../assignments/PRO-S9/README.md).
