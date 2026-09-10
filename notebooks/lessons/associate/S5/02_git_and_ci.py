# Databricks notebook source
# MAGIC %md
# MAGIC # Git workflow and CI — `ASSOC-S5-O1`, `ASSOC-S5-O4`
# MAGIC
# MAGIC Again, this repository is the worked example: every notebook here arrived through
# MAGIC the workflow described below.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Branch, review, merge
# MAGIC
# MAGIC Databricks Git folders put notebooks under normal version control. The workflow
# MAGIC is the ordinary one:
# MAGIC
# MAGIC ```
# MAGIC branch  →  commit  →  push  →  pull request  →  checks  →  merge
# MAGIC ```
# MAGIC
# MAGIC Work on a **branch per change**. Beyond avoiding collisions, that gives every
# MAGIC change a review point and a revert path — the things you want on the day
# MAGIC something breaks in production.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. What CI should check before a deploy
# MAGIC
# MAGIC | Check | Catches |
# MAGIC |---|---|
# MAGIC | `bundle validate --strict` | malformed config, unresolved variables, bad references |
# MAGIC | Unit tests | logic that is wrong but well-formed |
# MAGIC | Content/lint checks | whatever your project considers invalid |
# MAGIC
# MAGIC Validation and tests answer different questions. A bundle can validate cleanly
# MAGIC and still be broken, which is why both belong in the pipeline.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Authenticating CI
# MAGIC
# MAGIC CI authenticates as a **service principal** using OAuth machine-to-machine:
# MAGIC
# MAGIC ```
# MAGIC DATABRICKS_HOST
# MAGIC DATABRICKS_CLIENT_ID
# MAGIC DATABRICKS_CLIENT_SECRET
# MAGIC ```
# MAGIC
# MAGIC Never as a person. A pipeline tied to someone's account breaks when they leave,
# MAGIC and inherits everything they can do rather than what the job needs.
# MAGIC
# MAGIC > **A trap worth knowing.** If `DATABRICKS_CONFIG_PROFILE` is set in the shell,
# MAGIC > the CLI resolves that named profile and **ignores** the M2M variables — so a
# MAGIC > local attempt to test CI auth silently runs as *you* and appears to succeed.
# MAGIC > Use `env -u DATABRICKS_CONFIG_PROFILE` to test it honestly.

# COMMAND ----------

ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
path = ctx.notebookPath().get()
deployer = path.split("/Users/")[1].split("/")[0] if "/Users/" in path else "unknown"
print("this deployment was made by:", deployer)
print()
print("A path under a service principal's application id means CI deployed it.")
print("A path under an email address means a human did.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. What runs after a merge
# MAGIC
# MAGIC ```
# MAGIC PR  →  checks  →  merge to main  →  deploy job  →  bundle deploy
# MAGIC ```
# MAGIC
# MAGIC The deploy re-runs validation and tests before deploying, because two
# MAGIC individually-valid pull requests can merge into a broken `main`.
# MAGIC
# MAGIC ## What to carry forward
# MAGIC
# MAGIC - Branch per change, integrate through review.
# MAGIC - `validate` and tests answer different questions; run both.
# MAGIC - CI authenticates as a service principal, never as a person.
# MAGIC - The deployment path tells you who deployed it.
# MAGIC
# MAGIC Now do the assignment: promote one job definition to **two** environments with a
# MAGIC per-target variable override.
