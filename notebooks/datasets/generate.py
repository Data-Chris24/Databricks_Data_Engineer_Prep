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
dbutils.notebook.exit(json.dumps({"section": section, "child_result": (result or "")[:500]}))
