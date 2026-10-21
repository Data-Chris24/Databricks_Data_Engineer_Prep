# Databricks notebook source
# MAGIC %md
# MAGIC # Deploying, and the failures that do not raise — `PRO-S9-O4`, `PRO-S9-O5`

# COMMAND ----------

from pyspark.sql import functions as F

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Deploying with bundles — `PRO-S9-O4`
# MAGIC
# MAGIC **This notebook was deployed by the bundle it is describing.** Its workspace path
# MAGIC records who deployed it.

# COMMAND ----------

ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
path = ctx.notebookPath().get()
print("this notebook:", path)
who = path.split("/Users/")[1].split("/")[0] if "/Users/" in path else "unknown"
print("deployed by  :", who)
print()
print("An email means a human deployed it; an application id means CI did.")

# COMMAND ----------

# MAGIC %md
# MAGIC ```bash
# MAGIC databricks bundle validate --strict -t prod   # config only, never runs code
# MAGIC databricks bundle deploy -t prod
# MAGIC databricks bundle run my_job -t prod
# MAGIC ```
# MAGIC
# MAGIC CI authenticates as a **service principal** over OAuth M2M, never as a person.
# MAGIC
# MAGIC > A trap worth knowing: if `DATABRICKS_CONFIG_PROFILE` is set, the CLI resolves
# MAGIC > that profile and **ignores** `DATABRICKS_CLIENT_ID`/`SECRET`. A local test of CI
# MAGIC > auth then runs as *you* and appears to succeed. Use
# MAGIC > `env -u DATABRICKS_CONFIG_PROFILE` to test it honestly.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Git-based CI/CD — `PRO-S9-O5`
# MAGIC
# MAGIC ```
# MAGIC branch → PR → checks → merge → deploy
# MAGIC ```
# MAGIC
# MAGIC The deploy step re-runs validation and tests, because two individually-valid pull
# MAGIC requests can merge into a broken `main`.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. The failure mode that has no error
# MAGIC
# MAGIC Everything in notebook 1 assumed something raised. The dangerous failures do not:
# MAGIC
# MAGIC | Silent failure | Run state | How it shows |
# MAGIC |---|---|---|
# MAGIC | An upstream source stops arriving | SUCCESS | row count drops |
# MAGIC | A join starts dropping rows | SUCCESS | row count drops |
# MAGIC | A cast starts failing | SUCCESS | null rate rises |
# MAGIC | A filter's assumption breaks | SUCCESS | count moves either way |
# MAGIC
# MAGIC None of these raise. The run is green, the alert never fires, and the data is
# MAGIC wrong until somebody downstream notices.

# COMMAND ----------

# MAGIC %md
# MAGIC ### The only reliable detector is a trend
# MAGIC
# MAGIC A single run tells you nothing — you need the run before it to compare against.
# MAGIC For a table rebuilt on a schedule, `DESCRIBE HISTORY` is that record.

# COMMAND ----------

display(spark.sql("DESCRIBE HISTORY pro_s9_teach_raw").select(
    "version", "timestamp", "operation",
    F.col("operationMetrics")["numOutputRows"].alias("rows_written")))

# COMMAND ----------

# MAGIC %md
# MAGIC A version that wrote noticeably fewer rows than the one before it, with no error
# MAGIC anywhere, is the shape of a silent regression. That comparison is the whole
# MAGIC technique.

# COMMAND ----------

# MAGIC %md
# MAGIC ## What to carry forward
# MAGIC
# MAGIC - Bundles deploy; the path records who deployed.
# MAGIC - `validate` is a config check, not a test run.
# MAGIC - **A green run is not evidence of correctness.** Compare against the previous
# MAGIC   run, or you will not see a silent regression at all.
# MAGIC
# MAGIC The assignment's pipeline succeeded every day for twelve days and has been wrong
# MAGIC for six of them.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Next
# MAGIC
# MAGIC When the lessons are done, open the graded assignment: [PRO-S9 assignment notebook](../../../assignments/PRO-S9/assignment) · [the task](../../../assignments/PRO-S9/README.md).
