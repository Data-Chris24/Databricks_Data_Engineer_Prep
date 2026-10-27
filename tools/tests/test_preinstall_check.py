"""Tests for tools/preinstall_check.py, against a fake `databricks` CLI.

The healthy workspace below mirrors what the maintainer's Free Edition workspace
returned on 2026-10-26 (counts only); each test changes one thing about it.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import preinstall_check as pc  # noqa: E402

METASTORE = "00000000-0000-4000-8000-123456789abc"


def quota(kind, name, qname, count, limit):
    return {"parent_securable_type": kind, "parent_full_name": name,
            "quota_name": qname, "quota_count": count, "quota_limit": limit}


HEALTHY = {
    ("current-user", "me"): {"userName": "user@example.com"},
    ("apps", "list"): [{"name": "de-prep-study"}],
    ("postgres", "get-project", pc.LAKEBASE_PROJECT): {"name": pc.LAKEBASE_PROJECT},
    ("postgres", "get-endpoint", pc.LAKEBASE_ENDPOINT): {"status": {"disabled": False}},
    ("postgres", "list-projects"): [{"name": pc.LAKEBASE_PROJECT}],
    ("warehouses", "list"): [{"name": "Serverless Starter Warehouse", "cluster_size": "2X-Small"}],
    ("pipelines", "list-pipelines"): [],
    ("schemas", "list", "workspace"): [{"name": n} for n in
                                       ("de_prep", "de_prep_staging", "default", "information_schema")],
    ("tables", "list", "workspace", "de_prep", "--omit-columns", "--omit-properties"):
        [{"name": f"t{i}"} for i in range(62)],
    ("resource-quotas", "list-quotas"): [
        quota("CATALOG", "workspace", "schema-quota", 4, 50),
        quota("SCHEMA", "workspace.de_prep", "table-quota", 62, 100),
        quota("METASTORE", METASTORE, "table-quota", 108, 500),
        quota("METASTORE", METASTORE, "volume-quota", 20, 50),
        quota("METASTORE", METASTORE, "catalog-quota", 4, 50),
        quota("METASTORE", METASTORE, "share-quota", 1, 50),
        quota("METASTORE", METASTORE, "recipient-quota", 1, 50),
        quota("METASTORE", METASTORE, "connection-quota", 0, 50),
    ],
}


def fake_cli(responses):
    """A CLI that answers from `responses`; an Exception value is returned as a failure."""
    def cli(args):
        value = responses.get(tuple(args), RuntimeError("Error: unexpected call " + " ".join(args)))
        if isinstance(value, Exception):
            return False, str(value)
        return True, value
    return cli


def workspace(changes=None):
    """The healthy workspace with `changes` ({cli args: response}) applied."""
    responses = copy.deepcopy(HEALTHY)
    responses.update(changes or {})
    return responses


def run(responses):
    return pc.run_checks(fake_cli(responses))


def statuses(report, area):
    return [(s, f) for s, a, f, _ in report.results if a == area]


def set_quota(responses, kind, name, qname, count, limit):
    rows = [q for q in responses[("resource-quotas", "list-quotas")]
            if (q["parent_securable_type"], q["parent_full_name"], q["quota_name"]) != (kind, name, qname)]
    rows.append(quota(kind, name, qname, count, limit))
    responses[("resource-quotas", "list-quotas")] = rows


def test_healthy_redeploy_passes_everything():
    r = run(workspace())
    assert r.count(pc.FAIL) == 0 and r.count(pc.WARN) == 0, r.results
    assert any("re-deploy" in f for _, f in statuses(r, "apps"))


def test_auth_failure_stops_and_fails(monkeypatch, capsys):
    monkeypatch.setattr(pc, "make_cli", lambda profile: fake_cli(
        {("current-user", "me"): RuntimeError("Error: cannot configure default credentials")}))
    assert pc.main([]) == 1
    out = capsys.readouterr().out
    assert "[FAIL] auth" in out and "1 checks" in out


def test_three_other_apps_fail():
    r = run(workspace({("apps", "list"): [{"name": "a"}, {"name": "b"}, {"name": "c"}]}))
    assert statuses(r, "apps")[0][0] == pc.FAIL


def test_two_other_apps_leave_room():
    r = run(workspace({("apps", "list"): [{"name": "a"}, {"name": "b"}]}))
    assert statuses(r, "apps") == [(pc.OK, "2 of 3 apps used; the study app takes one more")]


def test_second_deployers_app_warns():
    r = run(workspace({("apps", "list"): [{"name": "de-prep-study"}, {"name": "dev-someone-de-prep-study"}]}))
    assert [s for s, _ in statuses(r, "apps")] == [pc.OK, pc.WARN]


def test_missing_lakebase_project_fails_with_the_create_command():
    r = run(workspace({("postgres", "get-project", pc.LAKEBASE_PROJECT): RuntimeError("Error: NOT_FOUND"),
                         ("postgres", "list-projects"): []}))
    (status, area, finding, remedy), = [x for x in r.results if x[1] == "lakebase"]
    assert status == pc.FAIL and "create-project de-prep" in remedy


def test_another_lakebase_project_holds_the_slot():
    r = run(workspace({("postgres", "get-project", pc.LAKEBASE_PROJECT): RuntimeError("Error: NOT_FOUND"),
                         ("postgres", "list-projects"): [{"name": "projects/other"}]}))
    status, finding = statuses(r, "lakebase")[0]
    assert status == pc.FAIL and "1 other project" in finding


def test_unreadable_lakebase_project_only_warns():
    # A principal without access must not block the deploy on a guess.
    r = run(workspace({("postgres", "get-project", pc.LAKEBASE_PROJECT):
                         RuntimeError("Error: PERMISSION_DENIED")}))
    assert statuses(r, "lakebase")[0][0] == pc.WARN
    assert r.count(pc.FAIL) == 0


def test_disabled_endpoint_warns():
    r = run(workspace({("postgres", "get-endpoint", pc.LAKEBASE_ENDPOINT): {"status": {"disabled": True}}}))
    assert [s for s, _ in statuses(r, "lakebase")] == [pc.OK, pc.WARN]


def test_no_warehouse_warns():
    r = run(workspace({("warehouses", "list"): []}))
    assert statuses(r, "warehouse")[0][0] == pc.WARN


def test_running_pipeline_warns():
    r = run(workspace({("pipelines", "list-pipelines"): [{"name": "x", "state": "RUNNING"},
                                                           {"name": "y", "state": "IDLE"}]}))
    assert statuses(r, "pipelines")[0][0] == pc.WARN


def test_full_schema_quota_fails_on_first_install():
    responses = workspace({("schemas", "list", "workspace"): [{"name": "default"}]})
    set_quota(responses, "CATALOG", "workspace", "schema-quota", 49, 50)
    status, finding = statuses(run(responses), "schemas")[0]
    assert status == pc.FAIL and "de_prep, de_prep_staging" in finding


def test_full_schema_quota_passes_when_ours_exist():
    responses = workspace()
    set_quota(responses, "CATALOG", "workspace", "schema-quota", 50, 50)
    assert statuses(run(responses), "schemas")[0][0] == pc.OK


def test_schema_table_count_falls_back_to_listing():
    # list-quotas omits a schema well below its limit (seen for workspace.de_prep).
    responses = workspace()
    responses[("resource-quotas", "list-quotas")] = [
        q for q in responses[("resource-quotas", "list-quotas")] if q["parent_full_name"] != "workspace.de_prep"]
    responses[("tables", "list", "workspace", "de_prep", "--omit-columns", "--omit-properties")] = \
        [{"name": f"t{i}"} for i in range(90)]
    status, finding = statuses(run(responses), "tables")[0]
    assert status == pc.WARN and "90 of 100" in finding


@pytest.mark.parametrize("used, expected", [
    (300, "room for every unit"),
    (480, "one unit at a time"),
    (495, "not enough for the largest unit"),
])
def test_metastore_table_headroom(used, expected):
    responses = workspace()
    set_quota(responses, "METASTORE", METASTORE, "table-quota", used, 500)
    _, finding = statuses(run(responses), "tables")[1]
    assert expected in finding


def test_short_of_shares_warns_but_never_fails():
    responses = workspace()
    set_quota(responses, "METASTORE", METASTORE, "share-quota", 49, 50)
    r = run(responses)
    assert (pc.WARN, "49 of 50 shares used, 1 free; PRO-S4: up to 3") in statuses(r, "sharing")
    assert r.count(pc.FAIL) == 0


def test_unreadable_quotas_warn():
    r = run(workspace({("resource-quotas", "list-quotas"): RuntimeError("Error: PERMISSION_DENIED")}))
    assert statuses(r, "quotas")[0][0] == pc.WARN and r.count(pc.FAIL) == 0


def test_output_names_no_metastore_user_or_other_app(capsys):
    responses = workspace({("apps", "list"): [{"name": "de-prep-study"}, {"name": "someone-elses-app"}]})
    pc.print_report(run(responses), "test")
    out = capsys.readouterr().out
    for secret in (METASTORE, "user@example.com", "someone-elses-app"):
        assert secret not in out


def test_errors_hide_the_host():
    err = ("Warn: [hostmetadata] failed for https://" + "example.cloud.databricks.com\n"
           "Error: cannot reach https://" + "example.cloud.databricks.com/api")
    assert pc.short(err) == "Error: cannot reach <host>"
