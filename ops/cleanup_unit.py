# Databricks notebook source
# MAGIC %md
# MAGIC # Clean up a unit's resources
# MAGIC
# MAGIC Triggered by the study app, from a unit's start page: before a unit is set up
# MAGIC (after the learner confirms, for every *other* unit whose resources still
# MAGIC exist), from **Clean up resources**, and from **Remove** on a table the app
# MAGIC does not manage. It removes exactly what `grading/<SECTION>/resources.json`
# MAGIC declares - set-up data, lesson tables, views, functions and scratch folders,
# MAGIC assignment outputs - so the shared `workspace.de_prep` schema stays well clear
# MAGIC of Free Edition's 100 tables per schema.
# MAGIC
# MAGIC It is not the assignment reset (`grading/reset_assignment.py`): it never
# MAGIC touches a notebook, so the learner's copies and their cell outputs stay for
# MAGIC review. Progress and grades live in the app's database and are not touched
# MAGIC either.
# MAGIC
# MAGIC Order matters:
# MAGIC
# MAGIC 1. **Shares and recipients first.** A table in a share cannot be dropped
# MAGIC    (`DELTA_SHARING_SECURABLE_DELETE_BLOCKED.BY_SHARES`); PRO-S4's tables are.
# MAGIC    A table still held by a share the unit does not declare is removed from
# MAGIC    that share before the drop is retried.
# MAGIC 2. Foreign catalogs, then connections (a connection cannot be dropped while
# MAGIC    a foreign catalog uses it).
# MAGIC 3. Functions, views, tables (a `*` name matches every table with that prefix).
# MAGIC 4. Volumes, then raw-volume folders and files. A folder holding an Auto
# MAGIC    Loader checkpoint must go with its table, or a re-set-up lesson's stream
# MAGIC    would resume from the old checkpoint and load nothing.
# MAGIC 5. Catalogs a unit creates (PRO-S8), with `CASCADE`.
# MAGIC
# MAGIC Never removed: the `de_prep` schemas, the `raw` volume, the `workspace`
# MAGIC catalog, and the PRO-S8 service principals (account-level; PRO-S4 uses them).
# MAGIC
# MAGIC Parameters:
# MAGIC - `sections`: comma-separated, e.g. `PRO-S4` or `ASSOC-S1,PRO-S8`.
# MAGIC - `tables`: comma-separated three-part names of tables **no** unit declares
# MAGIC   (the app's "Not managed by the app" list), in `workspace.de_prep`,
# MAGIC   `workspace.de_prep_staging` or `workspace.default`. A declared name is
# MAGIC   refused here: those belong to a unit's clean-up.
# MAGIC
# MAGIC Runs as whoever deployed the bundle, which needs `MANAGE` on the schemas it
# MAGIC drops from (docs/ci-cd.md, step 2c). The run fails, after trying everything,
# MAGIC if anything could not be removed.

# COMMAND ----------

import fnmatch
import glob
import json
import os
import re

dbutils.widgets.text("sections", "")
dbutils.widgets.text("tables", "")
sections = [x.strip().upper() for x in dbutils.widgets.get("sections").split(",") if x.strip()]
strays = [x.strip() for x in dbutils.widgets.get("tables").split(",") if x.strip()]
if not sections and not strays:
    raise ValueError("pass 'sections' (e.g. PRO-S4 or ASSOC-S1,PRO-S8) or 'tables'")
for s in sections:
    if not re.fullmatch(r"(ASSOC|PRO)-S\d{1,2}", s):
        raise ValueError(f"sections must look like ASSOC-S1 or PRO-S10, got {s!r}")

from databricks.sdk import WorkspaceClient

ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
here = "/Workspace" + os.path.dirname(ctx.notebookPath().get())
files_root = here.split("/files/")[0] + "/files"
w = WorkspaceClient()

RAW = "/Volumes/workspace/de_prep/raw"
SCHEMAS = ("workspace.de_prep", "workspace.de_prep_staging")
STRAY_SCHEMAS = SCHEMAS + ("workspace.default",)
NEVER = {"workspace", "workspace.de_prep", "workspace.de_prep_staging", "workspace.default", "workspace.de_prep.raw", RAW}


def resources(section):
    with open(os.path.join(files_root, "grading", section, "resources.json")) as f:
        doc = json.load(f)
    return [r for g in ("setup", "lesson", "assignment") for r in doc.get(g, [])]


declared_everywhere = []
for path in glob.glob(os.path.join(files_root, "grading", "*", "resources.json")):
    declared_everywhere += resources(os.path.basename(os.path.dirname(path)))

# COMMAND ----------

def q(name):
    """Backtick each part of a dotted name."""
    return ".".join(f"`{p}`" for p in name.split("."))


def tables_in(schema):
    cat, sch = schema.split(".")
    try:
        return [t.full_name for t in w.tables.list(catalog_name=cat, schema_name=sch)]
    except Exception:
        return []


def allowed(kind, name):
    if name in NEVER:
        return False
    if kind in ("table", "view", "materialized_view", "function", "volume"):
        return ".".join(name.split(".")[:2]) in SCHEMAS
    if kind in ("folder", "file"):
        return name.startswith(RAW + "/")
    return True


def list_shares():
    # Newer SDKs name it list_shares; older ones list.
    return (getattr(w.shares, "list_shares", None) or w.shares.list)()


def shares_holding(table):
    """(share, shared-as name) for every share that holds `table`."""
    out = []
    for sh in list_shares():
        try:
            full = w.shares.get(sh.name, include_shared_data=True)
        except Exception:
            continue
        for obj in full.objects or []:
            if obj.name == table:
                out.append((sh.name, obj.shared_as or obj.name))
    return out


def clean(label, items):
    removed, absent, failed = [], [], []

    def run(kind, name, sql=None, fn=None):
        if not allowed(kind, name):
            failed.append({"object": f"{kind} {name}", "error": "refusing: outside what a unit may remove"})
            return
        try:
            if sql:
                spark.sql(sql)
            else:
                fn()
            removed.append(f"{kind} {name}")
        except Exception as e:
            msg = str(e)
            if kind == "table" and "BY_SHARES" in msg:
                # Held by a share the unit does not declare: take it out, then retry.
                try:
                    for share, alias in shares_holding(name):
                        spark.sql(f"ALTER SHARE `{share}` REMOVE TABLE {alias}")
                    spark.sql(sql)
                    removed.append(f"{kind} {name} (removed from its share first)")
                    return
                except Exception as e2:
                    msg = str(e2)
            failed.append({"object": f"{kind} {name}", "error": msg[:300]})

    by_kind = {}
    for r in items:
        by_kind.setdefault(r["kind"], []).append(r["name"])

    existing = {s: set(tables_in(s)) for s in SCHEMAS}

    def exists_table(name):
        schema = ".".join(name.split(".")[:2])
        return name in existing.get(schema, set())

    def listed(fn):
        try:
            return {x.name for x in fn()}
        except Exception:
            return None  # cannot list: try the drop anyway

    present = {
        "share": listed(list_shares),
        "recipient": listed(w.recipients.list),
        "catalog": listed(w.catalogs.list),
        "connection": listed(w.connections.list),
    }

    def drop_named(kind, name, sql):
        if present[kind] is not None and name not in present[kind]:
            absent.append(f"{kind} {name}")
        else:
            run(kind, name, sql)

    for s in by_kind.get("share", []):
        drop_named("share", s, f"DROP SHARE IF EXISTS `{s}`")
    for r in by_kind.get("recipient", []):
        drop_named("recipient", r, f"DROP RECIPIENT IF EXISTS `{r}`")
    # A unit's catalogs: PRO-S4's foreign catalog must go before its connection.
    for c in by_kind.get("catalog", []):
        if c.startswith("pro_s4_"):
            drop_named("catalog", c, f"DROP CATALOG IF EXISTS `{c}` CASCADE")
    for c in by_kind.get("connection", []):
        drop_named("connection", c, f"DROP CONNECTION IF EXISTS `{c}`")
    for f in by_kind.get("function", []):
        run("function", f, f"DROP FUNCTION IF EXISTS {q(f)}")
    for v in by_kind.get("view", []):
        if exists_table(v):
            run("view", v, f"DROP VIEW IF EXISTS {q(v)}")
        else:
            absent.append(v)
    for v in by_kind.get("materialized_view", []):
        if exists_table(v):
            run("materialized_view", v, f"DROP MATERIALIZED VIEW IF EXISTS {q(v)}")
        else:
            absent.append(v)
    for t in by_kind.get("table", []):
        if "*" in t:
            schema = ".".join(t.split(".")[:2])
            matches = sorted(x for x in existing.get(schema, set()) if fnmatch.fnmatchcase(x, t))
            for m in matches:
                run("table", m, f"DROP TABLE IF EXISTS {q(m)}")
            if not matches:
                absent.append(t)
        elif exists_table(t):
            run("table", t, f"DROP TABLE IF EXISTS {q(t)}")
        else:
            absent.append(t)
    for v in by_kind.get("volume", []):
        run("volume", v, f"DROP VOLUME IF EXISTS {q(v)}")
    for p in by_kind.get("folder", []) + by_kind.get("file", []):
        kind = "folder" if p in by_kind.get("folder", []) else "file"
        try:
            dbutils.fs.ls(p)
        except Exception:
            absent.append(p)
            continue
        run(kind, p, fn=lambda p=p: dbutils.fs.rm(p, True))
    for c in by_kind.get("catalog", []):
        if not c.startswith("pro_s4_"):
            drop_named("catalog", c, f"DROP CATALOG IF EXISTS `{c}` CASCADE")

    print(f"{label}: removed {len(removed)}, already absent {len(absent)}, failed {len(failed)}")
    for x in removed:
        print("  removed", x)
    for x in failed:
        print("  FAILED", x["object"], "-", x["error"])
    return {"unit": label, "removed": removed, "absent": absent, "failed": failed}

# COMMAND ----------

def is_declared(table):
    return any(
        r["kind"] in ("table", "view", "materialized_view") and fnmatch.fnmatchcase(table, r["name"])
        for r in declared_everywhere
    )


results = [clean(s, resources(s)) for s in sections]

if strays:
    items, refused = [], []
    for t in strays:
        parts = t.split(".")
        if len(parts) != 3 or ".".join(parts[:2]) not in STRAY_SCHEMAS or not re.fullmatch(r"[A-Za-z0-9_]+", parts[2]):
            refused.append({"object": t, "error": "not a table in workspace.de_prep, de_prep_staging or default"})
        elif is_declared(t):
            refused.append({"object": t, "error": "a unit declares it; use that unit's clean-up"})
        else:
            try:
                kind = str(w.tables.get(t).table_type or "").upper()
            except Exception as e:
                refused.append({"object": t, "error": str(e)[:300]})
                continue
            items.append({"kind": "view" if kind == "VIEW" else "materialized_view" if "MATERIALIZED" in kind else "table", "name": t})
    SCHEMAS = STRAY_SCHEMAS  # strays may live in workspace.default too
    result = clean("not managed", items)
    result["failed"] += refused
    results.append(result)

failures = [f"{r['unit']}: {x['object']} - {x['error']}" for r in results for x in r["failed"]]
summary = json.dumps({"units": results})
if failures:
    raise RuntimeError(f"{len(failures)} object(s) could not be removed: " + "; ".join(failures)[:900])
dbutils.notebook.exit(summary)
