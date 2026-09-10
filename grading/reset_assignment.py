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
# MAGIC Parameter: `section`, e.g. `ASSOC-S3`.

# COMMAND ----------

import json
import os

dbutils.widgets.text("section", "")
section = dbutils.widgets.get("section").strip()
if not section:
    raise ValueError("job parameter 'section' is required, e.g. ASSOC-S3")

ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
here = "/Workspace" + os.path.dirname(ctx.notebookPath().get())
manifest = os.path.join(here, section, "outputs.json")
with open(manifest) as f:
    outputs = json.load(f)

# COMMAND ----------

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
for s in outputs.get("shares", []):
    attempt("share", s, f"DROP SHARE IF EXISTS {s}")
for r in outputs.get("recipients", []):
    attempt("recipient", r, f"DROP RECIPIENT IF EXISTS {r}")
for p in outputs.get("paths", []):
    try:
        dbutils.fs.rm(p, True)
        dropped.append(f"path {p}")
    except Exception as e:
        failed.append({"object": p, "error": str(e)[:300]})

print(f"{section}: dropped {len(dropped)}, failed {len(failed)}")
for d in dropped:
    print("  dropped", d)
for f in failed:
    print("  FAILED", f["object"], "-", f["error"])

dbutils.notebook.exit(json.dumps({"section": section, "dropped": dropped, "failed": failed}))
