#!/usr/bin/env python3
"""Check that a Databricks Free Edition workspace has room for this repo, before deploying.

Free Edition caps apps, Lakebase projects and Unity Catalog objects per account
or metastore, and a workspace you already use may have spent some of them. This
asks the workspace what is used and reports, for each thing the bundle and its
content need, PASS, WARN or FAIL:

- FAIL: `bundle deploy` itself would fail, or the app could not work at all.
- WARN: the deploy works, but some unit or lesson would hit a limit later.

    python3 tools/preinstall_check.py --profile <PROFILE>
    python3 tools/preinstall_check.py            # CI: auth from DATABRICKS_* env vars

Exit code 1 when anything FAILs, else 0. A re-deploy passes: the app, the
Lakebase project and the schemas this repo created count as its own.

It is a script, not a bundle job, on purpose: a job would exist only after
`bundle deploy`, which has already taken an app slot by then, and it would spend
serverless quota on what is a handful of API calls.

The output names only this repo's own resources and prints counts for
everything else, never a host, an ID or another resource's name: the deploy
workflow runs it, and a public repo's Actions logs are public.

Requires the Databricks CLI, authenticated (README, "Getting set up").
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from typing import Callable

# What this repo creates. Keep in step with the bundle and the content.
APP_NAME = "de-prep-study"
APP_LIMIT = 3                       # apps per account
LAKEBASE_PROJECT = "projects/de-prep"
LAKEBASE_ENDPOINT = f"{LAKEBASE_PROJECT}/branches/production/endpoints/primary"
CATALOG = "workspace"
SCHEMAS = ("de_prep", "de_prep_staging")   # de_prep_staging: ASSOC-S5
SCHEMA = "de_prep"
SCHEMA_TABLE_LIMIT = 100
# Tables, views and materialized views the largest unit creates (ASSOC-S2 and
# PRO-S10 make about a dozen); with every unit set up at once it is 80 to 100.
LARGEST_UNIT_TABLES = 15
ALL_UNITS_TABLES = 100
VOLUMES_NEEDED = 2                  # de_prep.raw, PRO-S4's assess files
CATALOGS_NEEDED = 4                 # PRO-S8: teach, assess, a demo; PRO-S4: one
SHARES_NEEDED = 3                   # PRO-S4
RECIPIENTS_NEEDED = 4               # PRO-S4
CONNECTIONS_NEEDED = 1              # PRO-S4 federation

OK, WARN, FAIL = "PASS", "WARN", "FAIL"

Cli = Callable[[list], "tuple[bool, object]"]


def make_cli(profile: str | None) -> Cli:
    """Return a function that runs `databricks <args> -o json` and parses the result."""
    def cli(args: list) -> tuple[bool, object]:
        cmd = ["databricks", *args, "-o", "json"]
        if profile:
            cmd += ["--profile", profile]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        except (OSError, subprocess.TimeoutExpired) as e:
            return False, str(e)
        if proc.returncode != 0:
            return False, (proc.stderr or proc.stdout).strip()
        try:
            return True, json.loads(proc.stdout or "null")
        except json.JSONDecodeError:
            return True, proc.stdout
    return cli


def not_found(err: object) -> bool:
    text = str(err)
    return any(s in text for s in ("NOT_FOUND", "does not exist", "not found", "RESOURCE_DOES_NOT_EXIST"))


def short(err: object) -> str:
    """The CLI's error line, with any URL replaced: enough to act on, and no host in the log."""
    lines = [l.strip() for l in str(err).splitlines() if l.strip()]
    line = next((l for l in lines if l.startswith("Error")), lines[-1] if lines else "unknown error")
    return re.sub(r"https?://\S+", "<host>", line)[:200]


class Report:
    def __init__(self) -> None:
        self.results: list[tuple[str, str, str, str]] = []  # status, area, finding, remedy

    def add(self, status: str, area: str, finding: str, remedy: str = "") -> None:
        self.results.append((status, area, finding, remedy))

    def count(self, status: str) -> int:
        return sum(1 for r in self.results if r[0] == status)


# ---------------------------------------------------------------- checks


def check_auth(cli: Cli, r: Report) -> bool:
    ok, data = cli(["current-user", "me"])
    if ok:
        r.add(OK, "auth", "the CLI reaches the workspace")  # no user name: logs are public
        return True
    r.add(FAIL, "auth", f"the CLI cannot reach the workspace: {short(data)}",
          "databricks auth login --host <your-workspace-url> --profile <PROFILE>")
    return False


def check_apps(cli: Cli, r: Report) -> None:
    ok, apps = cli(["apps", "list"])
    if not ok:
        r.add(WARN, "apps", f"cannot list apps: {short(apps)}")
        return
    names = [a.get("name") for a in apps or []]
    used = len(names)
    if APP_NAME in names:
        r.add(OK, "apps", f"{APP_NAME} exists (re-deploy): {used} of {APP_LIMIT} apps used")
    elif used < APP_LIMIT:
        r.add(OK, "apps", f"{used} of {APP_LIMIT} apps used; the study app takes one more")
    else:
        r.add(FAIL, "apps", f"all {APP_LIMIT} app slots are used and none is {APP_NAME}",
              "Delete an app you no longer need: databricks apps delete <APP_NAME> --profile <PROFILE>")
    lookalikes = [n for n in names if n != APP_NAME and APP_NAME in (n or "")]
    if lookalikes:
        r.add(WARN, "apps", f"{len(lookalikes)} other app(s) with '{APP_NAME}' in the name: a second deployer?",
              "Deploy from one machine and profile only (README, 'Deploy your own copy')")


def check_lakebase(cli: Cli, r: Report) -> None:
    ok, data = cli(["postgres", "get-project", LAKEBASE_PROJECT])
    if not ok and not not_found(data):
        r.add(WARN, "lakebase", f"cannot read {LAKEBASE_PROJECT}: {short(data)}")
        return
    if not ok:
        ok, projects = cli(["postgres", "list-projects"])
        others = len(projects or []) if ok else 0
        if others:
            r.add(FAIL, "lakebase", f"{LAKEBASE_PROJECT} does not exist and {others} other project(s) "
                  "hold the account's one Lakebase project slot",
                  "Delete that project, or deploy to another account; the app needs its own")
        else:
            r.add(FAIL, "lakebase", f"{LAKEBASE_PROJECT} does not exist yet (the account allows one project)",
                  "databricks postgres create-project de-prep --json @ops/lakebase-project.json --profile <PROFILE>")
        return
    r.add(OK, "lakebase", f"{LAKEBASE_PROJECT} exists (1 of 1 projects)")

    ok, ep = cli(["postgres", "get-endpoint", LAKEBASE_ENDPOINT])
    if not ok:
        r.add(WARN, "lakebase", f"cannot read the endpoint: {short(ep)}")
    elif (ep.get("status") or {}).get("disabled"):
        r.add(WARN, "lakebase", "the endpoint is disabled (Free Edition does this after a few idle days)",
              "databricks bundle run wake_database -t free --profile <PROFILE>, "
              "or on a first deploy: databricks postgres update-endpoint ... (docs/free-edition-constraints.md)")
    else:
        r.add(OK, "lakebase", "the endpoint is enabled")


def check_warehouse(cli: Cli, r: Report) -> None:
    ok, whs = cli(["warehouses", "list"])
    if not ok:
        r.add(WARN, "warehouse", f"cannot list SQL warehouses: {short(whs)}")
    elif whs:
        r.add(OK, "warehouse", f"{len(whs)} SQL warehouse(s); the JDBC and federation lessons use one")
    else:
        r.add(WARN, "warehouse", "no SQL warehouse: the ASSOC-S2 JDBC and PRO-S4 federation lessons need one",
              "Free Edition comes with one (Serverless Starter Warehouse); recreate it under SQL Warehouses")


def check_pipelines(cli: Cli, r: Report) -> None:
    ok, pls = cli(["pipelines", "list-pipelines"])
    if not ok:
        r.add(WARN, "pipelines", f"cannot list pipelines: {short(pls)}")
        return
    running = sum(1 for p in pls or [] if p.get("state") == "RUNNING")
    if running:
        r.add(WARN, "pipelines", f"{running} pipeline(s) running; Free Edition allows one active per type, "
              "and the materialized view in ASSOC-S3 needs one", "Stop it before that lesson")
    else:
        r.add(OK, "pipelines", f"{len(pls or [])} pipeline(s), none running")


def quotas(cli: Cli) -> tuple[bool, object]:
    """All quotas as {(parent_type, parent_name_or_'metastore', quota): (count, limit)}."""
    ok, rows = cli(["resource-quotas", "list-quotas"])
    if not ok:
        return False, rows
    out = {}
    for q in rows or []:
        kind = q.get("parent_securable_type")
        # The metastore is named by its ID; key it generically and never print it.
        name = "metastore" if kind == "METASTORE" else q.get("parent_full_name")
        out[(kind, name, q.get("quota_name"))] = (q.get("quota_count", 0), q.get("quota_limit"))
    return True, out


def headroom(r: Report, area: str, quota: tuple | None, needed: int, what: str, who: str,
             remedy: str = "") -> None:
    if quota is None:
        r.add(OK, area, f"no {what} quota reported (none used yet)")
        return
    used, limit = quota
    free = limit - used
    if free >= needed:
        r.add(OK, area, f"{used} of {limit} {what} used; {who}: up to {needed}")
    else:
        r.add(WARN, area, f"{used} of {limit} {what} used, {free} free; {who}: up to {needed}", remedy)


def check_unity_catalog(cli: Cli, r: Report) -> None:
    ok, q = quotas(cli)
    if not ok:
        r.add(WARN, "quotas", f"cannot read Unity Catalog quotas: {short(q)}",
              "Check by hand: databricks resource-quotas list-quotas --profile <PROFILE>")
        return

    ok, schemas = cli(["schemas", "list", CATALOG])
    have = {s.get("name") for s in schemas or []} if ok else set()
    missing = [s for s in SCHEMAS if s not in have]
    sq = q.get(("CATALOG", CATALOG, "schema-quota"))
    if not ok:
        r.add(WARN, "schemas", f"cannot list schemas in {CATALOG}: {short(schemas)}")
    elif sq and sq[1] - sq[0] < len(missing):
        r.add(FAIL, "schemas", f"{CATALOG}: {sq[0]} of {sq[1]} schemas used, no room for {', '.join(missing)}",
              f"Drop a schema you no longer need in {CATALOG}")
    else:
        used = f"{sq[0]} of {sq[1]} schemas used" if sq else f"{len(have)} schemas"
        state = "all exist" if not missing else f"will create {', '.join(missing)}"
        r.add(OK, "schemas", f"{CATALOG}: {used}; {', '.join(SCHEMAS)} {state}")

    # Tables. The schema's own row is missing while it is well below its limit
    # (seen for workspace.de_prep), so fall back to counting.
    tq = q.get(("SCHEMA", f"{CATALOG}.{SCHEMA}", "table-quota"))
    if tq:
        in_schema = tq[0]
    elif SCHEMA in have:
        ok, tables = cli(["tables", "list", CATALOG, SCHEMA, "--omit-columns", "--omit-properties"])
        in_schema = len(tables or []) if ok else 0
    else:
        in_schema = 0
    free_schema = SCHEMA_TABLE_LIMIT - in_schema
    if free_schema >= LARGEST_UNIT_TABLES:
        r.add(OK, "tables", f"{CATALOG}.{SCHEMA}: {in_schema} of {SCHEMA_TABLE_LIMIT} tables")
    else:
        r.add(WARN, "tables", f"{CATALOG}.{SCHEMA}: {in_schema} of {SCHEMA_TABLE_LIMIT} tables, "
              f"too few free for the largest unit (~{LARGEST_UNIT_TABLES})",
              "Clean up units you have finished, or reset their assignments")

    mt = q.get(("METASTORE", "metastore", "table-quota"))
    if mt:
        used, limit = mt
        free = limit - used
        all_units = max(ALL_UNITS_TABLES - in_schema, 0)
        if free >= all_units:
            r.add(OK, "tables", f"metastore: {used} of {limit} tables; room for every unit at once")
        elif free >= LARGEST_UNIT_TABLES:
            r.add(WARN, "tables", f"metastore: {used} of {limit} tables, {free} free: enough for one unit "
                  f"at a time, not all ({all_units})", "Set up one unit at a time")
        else:
            r.add(WARN, "tables", f"metastore: {used} of {limit} tables, {free} free: "
                  f"not enough for the largest unit (~{LARGEST_UNIT_TABLES})",
                  "Drop tables you no longer need elsewhere in the metastore")

    headroom(r, "volumes", q.get(("METASTORE", "metastore", "volume-quota")), VOLUMES_NEEDED,
             "volumes", "content", "Drop a volume you no longer need")
    headroom(r, "catalogs", q.get(("METASTORE", "metastore", "catalog-quota")), CATALOGS_NEEDED,
             "catalogs", "PRO-S8 and PRO-S4", "PRO-S8 and PRO-S4 cannot run until catalogs are freed")
    headroom(r, "sharing", q.get(("METASTORE", "metastore", "share-quota")), SHARES_NEEDED,
             "shares", "PRO-S4", "PRO-S4 cannot run until shares are freed")
    headroom(r, "sharing", q.get(("METASTORE", "metastore", "recipient-quota")), RECIPIENTS_NEEDED,
             "recipients", "PRO-S4", "PRO-S4 cannot run until recipients are freed")
    headroom(r, "sharing", q.get(("METASTORE", "metastore", "connection-quota")), CONNECTIONS_NEEDED,
             "connections", "PRO-S4", "PRO-S4's federation lesson needs one")


def run_checks(cli: Cli) -> Report:
    r = Report()
    if check_auth(cli, r):
        check_apps(cli, r)
        check_lakebase(cli, r)
        check_warehouse(cli, r)
        check_pipelines(cli, r)
        check_unity_catalog(cli, r)
    return r


def print_report(r: Report, label: str) -> None:
    print(f"Pre-install check ({label})\n")
    width = max(len(a) for _, a, _, _ in r.results)
    for status, area, finding, remedy in r.results:
        print(f"  [{status}] {area.ljust(width)}  {finding}")
        if remedy and status != OK:
            print(f"         {' ' * width}  -> {remedy}")
    fails, warns = r.count(FAIL), r.count(WARN)
    print(f"\n{len(r.results)} checks: {len(r.results) - fails - warns} passed, "
          f"{warns} warnings, {fails} failures")


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--profile", help="CLI profile; omit to use DATABRICKS_* environment variables (CI)")
    args = ap.parse_args(argv)

    r = run_checks(make_cli(args.profile))
    print_report(r, f"profile {args.profile}" if args.profile else "environment credentials")
    return 1 if r.count(FAIL) else 0


if __name__ == "__main__":
    sys.exit(main())
