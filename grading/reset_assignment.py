# Databricks notebook source
# MAGIC %md
# MAGIC # Reset an assignment's outputs
# MAGIC
# MAGIC Triggered by the study app when a learner resets a section. Drops exactly the
# MAGIC objects that section's `outputs.json` names - the tables (and for PRO-S4 the
# MAGIC share and recipient) the assignment produces - so a fresh attempt starts from
# MAGIC nothing and a stale grade cannot pass on old work. Assess inputs are never
# MAGIC listed and never touched.
# MAGIC
# MAGIC Parameter: `section`, e.g. `ASSOC-S3`, or a comma-separated list such as
# MAGIC `ASSOC-S1,ASSOC-S2` when a learner starts an exam over.

# COMMAND ----------

import json
import os

dbutils.widgets.text("section", "")
sections = [x.strip() for x in dbutils.widgets.get("section").split(",") if x.strip()]
if not sections:
    raise ValueError("job parameter 'section' is required, e.g. ASSOC-S3 or ASSOC-S1,ASSOC-S2")

ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
here = "/Workspace" + os.path.dirname(ctx.notebookPath().get())

# COMMAND ----------

results = []


def reset_section(section):
    with open(os.path.join(here, section, "outputs.json")) as f:
        outputs = json.load(f)
    dropped, failed = [], []

    def attempt(kind, name, sql):
        if "_assess_" in name or name.endswith("_assess"):
            failed.append({"object": name, "error": "refusing to drop an assess input"})
            return
        try:
            spark.sql(sql)
            dropped.append(f"{kind} {name}")
        except Exception as e:  # keep going; report every failure
            failed.append({"object": name, "error": str(e)[:300]})

    for t in outputs.get("tables", []):
        attempt("table", t, f"DROP TABLE IF EXISTS {t}")
    for v in outputs.get("views", []):
        attempt("view", v, f"DROP VIEW IF EXISTS {v}")
    for sh in outputs.get("shares", []):
        attempt("share", sh, f"DROP SHARE IF EXISTS {sh}")
    for r in outputs.get("recipients", []):
        attempt("recipient", r, f"DROP RECIPIENT IF EXISTS {r}")
    for pth in outputs.get("paths", []):
        try:
            dbutils.fs.rm(pth, True)
            dropped.append(f"path {pth}")
        except Exception as e:
            failed.append({"object": pth, "error": str(e)[:300]})

    print(f"{section}: dropped {len(dropped)}, failed {len(failed)}")
    for d in dropped:
        print("  dropped", d)
    for fl in failed:
        print("  FAILED", fl["object"], "-", fl["error"])
    return {"section": section, "dropped": dropped, "failed": failed}


for section in sections:
    results.append(reset_section(section))

dbutils.notebook.exit(json.dumps({"sections": results}))
