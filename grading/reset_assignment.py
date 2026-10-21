# Databricks notebook source
# MAGIC %md
# MAGIC # Reset an assignment's outputs
# MAGIC
# MAGIC Triggered by the study app when a learner resets a section. Two things happen,
# MAGIC both driven by what the repo declares rather than by anyone's identity:
# MAGIC
# MAGIC 1. The section's **deployed assignment notebooks** are restored from the clean
# MAGIC    starters the build embedded (`app/shared/content/starters.json`, generated
# MAGIC    from `notebooks/assignments/<SECTION>/*.py` at the deployed commit). A
# MAGIC    learner who edited the deployed notebook directly gets the repo's copy back.
# MAGIC 2. The objects the section's `outputs.json` names - the tables (and for PRO-S4
# MAGIC    the share and recipient) the assignment produces - are dropped, so a fresh
# MAGIC    attempt starts from nothing and a stale grade cannot pass on old work.
# MAGIC    Assess inputs are never listed and never touched.
# MAGIC
# MAGIC Runs as whoever deployed the bundle, which owns the deployed notebooks.
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

import base64

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.workspace import ImportFormat, Language

ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
here = "/Workspace" + os.path.dirname(ctx.notebookPath().get())
files_root = here.split("/files/")[0] + "/files"
w = WorkspaceClient()

with open(os.path.join(files_root, "app", "shared", "content", "starters.json")) as f:
    starters = json.load(f)

# COMMAND ----------

results = []


def restore_deployed_notebooks(section, failed):
    """Put the repo's starter back into the deployed assignment notebooks."""
    restored = []
    for starter in starters.get(section, []):
        path = f"{files_root}/notebooks/assignments/{section}/{starter['name']}"
        try:
            w.workspace.import_(
                path=path,
                format=ImportFormat.SOURCE,
                language=Language.PYTHON,
                overwrite=True,
                content=base64.b64encode(starter["source"].encode("utf-8")).decode("ascii"),
            )
            restored.append(path)
        except Exception as e:
            failed.append({"object": path, "error": str(e)[:300]})
    return restored


def reset_section(section):
    with open(os.path.join(here, section, "outputs.json")) as f:
        outputs = json.load(f)
    dropped, failed = [], []
    restored = restore_deployed_notebooks(section, failed)

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

    print(f"{section}: restored {len(restored)} notebook(s), dropped {len(dropped)}, failed {len(failed)}")
    for r in restored:
        print("  restored", r)
    for d in dropped:
        print("  dropped", d)
    for fl in failed:
        print("  FAILED", fl["object"], "-", fl["error"])
    return {"section": section, "restored": restored, "dropped": dropped, "failed": failed}


for section in sections:
    results.append(reset_section(section))

dbutils.notebook.exit(json.dumps({"sections": results}))
