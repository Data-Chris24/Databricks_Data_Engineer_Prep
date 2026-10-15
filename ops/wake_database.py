# Databricks notebook source
# MAGIC %md
# MAGIC # Wake the study app's database
# MAGIC
# MAGIC Free Edition **disables** a Lakebase endpoint after a few days without a
# MAGIC connection (measured 2026-09-14 and again 2026-10-15), and a disabled endpoint
# MAGIC stays off until someone with rights on the project turns it back on. The study
# MAGIC app then cannot read anyone's progress.
# MAGIC
# MAGIC The app's own principal can only connect to the database, not manage it, so the
# MAGIC app runs this job instead. It runs as whoever deployed the bundle - the person
# MAGIC who created the Lakebase project, or a CI principal holding CAN_MANAGE on it -
# MAGIC and re-enables the endpoint. Nothing else is touched, and an enabled endpoint is
# MAGIC left alone, so running it by hand ("Run now") is always safe.
# MAGIC
# MAGIC Parameter: `endpoint`, the full resource name, e.g.
# MAGIC `projects/de-prep/branches/production/endpoints/primary`.

# COMMAND ----------

import time

from databricks.sdk import WorkspaceClient

dbutils.widgets.text("endpoint", "")
endpoint = dbutils.widgets.get("endpoint").strip()
if not endpoint.startswith("projects/"):
    raise ValueError("job parameter 'endpoint' must be a full name like projects/<p>/branches/<b>/endpoints/<e>")

# The REST API directly, not w.postgres: the SDK on serverless may predate the
# postgres module, and this call has been stable (it is what the CLI sends).
api = WorkspaceClient().api_client
path = f"/api/2.0/postgres/{endpoint}"


def status() -> dict:
    return api.do("GET", path).get("status", {})


before = status()
print(f"before: disabled={before.get('disabled')} state={before.get('current_state')}")
if before.get("disabled"):
    api.do("PATCH", path, query={"update_mask": "spec.disabled"}, body={"spec": {"disabled": False}})
    # Wait for the change to land so the app's next query finds it enabled.
    deadline = time.time() + 300
    while status().get("disabled") and time.time() < deadline:
        time.sleep(5)

after = status()
print(f"after:  disabled={after.get('disabled')} state={after.get('current_state')}")
if after.get("disabled"):
    raise RuntimeError(f"{endpoint} is still disabled after 5 minutes")
