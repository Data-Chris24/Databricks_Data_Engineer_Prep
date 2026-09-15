# Databricks notebook source
# MAGIC %md
# MAGIC # Generate a section's datasets (dispatcher)
# MAGIC
# MAGIC The study app runs this job with a `section` parameter the first time a learner
# MAGIC opens a section, so nobody needs a terminal. It runs the section's own generator
# MAGIC (`generate_<SECTION>.py`, next to this notebook) as a child notebook run. One job
# MAGIC for all sections because a Databricks App may hold at most 20 resources, and the
# MAGIC seventeen graders plus the reset job and Lakebase already take nineteen.

# COMMAND ----------

import json
import re

dbutils.widgets.text("section", "", "Section id, e.g. ASSOC-S1 or PRO-S10")
section = dbutils.widgets.get("section").strip().upper()
if not re.fullmatch(r"(ASSOC|PRO)-S\d{1,2}", section):
    raise ValueError(f"section must look like ASSOC-S1 or PRO-S10, got {section!r}")

# Relative to this notebook's folder; the generators are deployed alongside it.
result = dbutils.notebook.run(f"generate_{section}", timeout_seconds=1800)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Learners must be able to read what was just built
# MAGIC
# MAGIC The tables are owned by whoever ran this job. When that is a service
# MAGIC principal (the upstream repo's CI deployer, or any team deployment), a learner
# MAGIC who is not the owner has no `SELECT` on them: Unity Catalog ownership does not
# MAGIC pass down from the schema, and a learner's own earlier ownership is gone once
# MAGIC the table is rebuilt (seen 2026-09-15: `PERMISSION_DENIED: User does not have
# MAGIC SELECT on Table 'workspace.de_prep.s1_assess_catalog'`). Schema-level grants
# MAGIC inherit to every current and future table, so grant once here, idempotently,
# MAGIC to every user of the account. `MODIFY` and `CREATE TABLE` are for the
# MAGIC assignments' own output tables; the volume privileges for the file-based
# MAGIC sections. When the learner runs this job themselves the grants are a no-op.

# COMMAND ----------

catalog = spark.conf.get("de_prep.catalog", "workspace")
grants = "USE SCHEMA, SELECT, MODIFY, CREATE TABLE, READ VOLUME, WRITE VOLUME"
granted = []
for schema in ("de_prep", "de_prep_staging"):
    exists = spark.sql(f"SHOW SCHEMAS IN {catalog} LIKE '{schema}'").count() > 0
    if not exists:
        continue
    try:
        spark.sql(f"GRANT {grants} ON SCHEMA {catalog}.{schema} TO `account users`")
        granted.append(schema)
    except Exception as e:  # the deployer may lack MANAGE here; say so rather than fail the data
        print(f"could not grant on {catalog}.{schema}: {type(e).__name__}: {str(e)[:200]}")

dbutils.notebook.exit(json.dumps({"section": section, "child_result": (result or "")[:500], "granted_to_account_users": granted}))
