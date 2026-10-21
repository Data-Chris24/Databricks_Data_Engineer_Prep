# Databricks notebook source
# MAGIC %md
# MAGIC # Bundles, variables and promotion — `ASSOC-S5-O2`, `ASSOC-S5-O3`
# MAGIC
# MAGIC **This repository is the worked example.** You are reading a notebook that was
# MAGIC deployed by the very bundle it describes, so everything here is real rather than
# MAGIC illustrative.

# COMMAND ----------

CATALOG, SCHEMA = "workspace", "de_prep"
spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. What a bundle is
# MAGIC
# MAGIC A Declarative Automation Bundle packages jobs, pipelines and their configuration
# MAGIC as version-controlled code, so the same definition is promoted across
# MAGIC environments with only its **configuration** differing.
# MAGIC
# MAGIC ```yaml
# MAGIC bundle:
# MAGIC   name: databricks-de-prep
# MAGIC
# MAGIC variables:
# MAGIC   catalog:
# MAGIC     default: workspace
# MAGIC   schema:
# MAGIC     default: de_prep
# MAGIC
# MAGIC targets:
# MAGIC   free:
# MAGIC     default: true
# MAGIC     mode: development
# MAGIC   classic:
# MAGIC     mode: development
# MAGIC ```
# MAGIC
# MAGIC Two copies of a bundle diverge, and the moment they do, dev stops predicting
# MAGIC prod. One definition with per-target overrides is the whole point.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. `mode: development` renames what it deploys
# MAGIC
# MAGIC Resources get prefixed with your username, so your experiments cannot collide
# MAGIC with anyone else's or with production. Look at the job names below — the CI
# MAGIC service principal's deployments and your own sit side by side.

# COMMAND ----------

import re
jobs = spark.sql("SELECT 1").collect()  # placeholder so the cell has an action
print("Job names carry the deploying identity, e.g.:")
print("  [dev <your name>]      [DE prep] Generate ASSOC-S5 datasets   <- deployed by hand")
print("  [dev github_actions_ci] [DE prep] Generate ASSOC-S5 datasets  <- deployed by CI")
print()
print("Same definition, same bundle, different deployer - and they cannot overwrite")
print("each other, which is what makes a dev deploy safe.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Where this notebook actually is
# MAGIC
# MAGIC A bundle deploy uploads the repository to a path owned by whoever deployed it.
# MAGIC That path is the clearest evidence of who ran the deployment.

# COMMAND ----------

ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
path = ctx.notebookPath().get()
print("this notebook lives at:")
print(" ", path)
print()
print("The '.bundle/<bundle name>/<target>' segment is created by `bundle deploy`.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. The CLI commands that matter
# MAGIC
# MAGIC ```bash
# MAGIC databricks bundle validate --strict -t free   # configuration check only
# MAGIC databricks bundle deploy -t free              # upload + create/update resources
# MAGIC databricks bundle run my_job -t free          # trigger a job in that target
# MAGIC databricks bundle destroy -t free             # remove what this bundle deployed
# MAGIC ```
# MAGIC
# MAGIC **`validate` never runs your code.** It catches malformed YAML, unresolved
# MAGIC variables and bad references before anything is uploaded — so a bundle can
# MAGIC validate cleanly and still fail at runtime. That is why a real pipeline runs
# MAGIC tests as well as validation.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. A job reading its own environment
# MAGIC
# MAGIC The lesson's job hardcodes its destination, which is fine for one environment
# MAGIC and is exactly what the assignment will make you fix.

# COMMAND ----------

src = spark.table("s5_source_transactions")
summary = spark.sql("""
    SELECT channel, count(*) AS txns, round(sum(amount), 2) AS revenue
    FROM s5_source_transactions
    GROUP BY channel
""")
summary.write.mode("overwrite").saveAsTable("s5_channel_summary")   # hardcoded destination
display(spark.table("s5_channel_summary").orderBy("channel"))
print(f"published {spark.table('s5_channel_summary').count()} rows to {CATALOG}.{SCHEMA}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## What to carry forward
# MAGIC
# MAGIC - One definition, promoted; configuration differs per target, not the code.
# MAGIC - `mode: development` namespaces deployments by deployer.
# MAGIC - `validate` is a configuration check, not a test run.
# MAGIC - **This notebook hardcodes its catalog and schema.** The assignment requires the
# MAGIC   destination to come from a bundle variable overridden per target, so the same
# MAGIC   job writes somewhere different in each environment. Copying this cell will not
# MAGIC   get you there.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Next
# MAGIC
# MAGIC Continue with the next lesson notebook: [02_git_and_ci](./02_git_and_ci).
# MAGIC
# MAGIC When the lessons are done, open the graded assignment: [ASSOC-S5 assignment notebook](../../../assignments/ASSOC-S5/assignment) · [the task](../../../assignments/ASSOC-S5/README.md).
