"""Graded tests for the PRO-S4 assignment. Authoritative.

The deliverable is a configuration, so these tests read the catalog rather than a
table: what is in the share, on what terms, and who can reach it.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from pyspark.sql import SparkSession

SHARE = "pro_s4_partner_share"
RECIPIENT = "pro_s4_partner"
MUST_NOT_SHARE = "workspace.de_prep.pro_s4_assess_salaries"


def _fixtures() -> dict:
    env = os.environ.get("PRO_S4_FIXTURES")
    if env and Path(env).exists():
        return json.loads(Path(env).read_text())
    for parent in Path(__file__).resolve().parents:
        c = parent / "grading" / "PRO-S4" / "expected.json"
        if c.exists():
            return json.loads(c.read_text())
    pytest.fail("expected.json not found; set PRO_S4_FIXTURES")


@pytest.fixture(scope="session")
def spark():
    return SparkSession.builder.getOrCreate()


@pytest.fixture(scope="session")
def expected():
    return _fixtures()


@pytest.fixture(scope="session")
def w():
    from databricks.sdk import WorkspaceClient
    return WorkspaceClient()


@pytest.fixture(scope="session")
def shares(spark):
    # SHOW SHARES names its first column `share`.
    return [r["share"] for r in spark.sql("SHOW SHARES").collect()]


@pytest.fixture(scope="session")
def objects(spark, shares):
    if SHARE not in shares:
        pytest.fail(
            f"share {SHARE!r} does not exist. Shares present: {shares or 'none'}"
        )
    return spark.sql(f"SHOW ALL IN SHARE {SHARE}").collect()


@pytest.fixture(scope="session")
def grants(spark, shares):
    if SHARE not in shares:
        pytest.fail(f"share {SHARE!r} does not exist")
    return spark.sql(f"SHOW GRANTS ON SHARE {SHARE}").collect()


def _rows(objects):
    return sorted([[r["name"], r["type"], r["history_sharing"],
                    bool(r["cdf_shared"]), r["shared_object"]] for r in objects])


# ------------------------------------------------------------- the share exists

def test_the_share_exists(shares):
    assert SHARE in shares


def test_the_share_holds_four_objects(objects, expected):
    assert len(objects) == expected["object_count"], (
        f"{len(objects)} objects in the share, expected {expected['object_count']}: "
        "three tables and a volume."
    )


def test_objects_are_aliased_for_the_recipient(objects):
    unaliased = [r["name"] for r in objects if not r["name"].startswith("partner.")]
    assert not unaliased, (
        f"{unaliased} are shared under your own schema name. The recipient should see "
        "them under `partner.`, set with `AS partner.<name>` when the object is added - "
        "REMOVE TABLE takes the shared name, so this cannot be fixed afterwards by the "
        "source path."
    )


# ------------------------------------------------------ each object's own terms

def test_orders_is_shared_without_history(objects):
    row = next((r for r in objects if r["name"] == "partner.orders"), None)
    assert row is not None, "partner.orders is missing from the share"
    assert row["history_sharing"] == "DISABLED", (
        "partner.orders must be shared WITHOUT HISTORY, and it is "
        f"{row['history_sharing']}. A plain ADD TABLE shares history - it is the "
        "default, and nothing warns you. On this table the explicit clause is refused "
        "until the deletion vectors are gone: turn the property off, then "
        "REORG ... APPLY (PURGE), which is the step that actually rewrites the files."
    )


def test_customers_is_shared_with_history(objects):
    row = next((r for r in objects if r["name"] == "partner.customers"), None)
    assert row is not None, "partner.customers is missing from the share"
    assert row["history_sharing"] == "ENABLED", (
        "partner.customers must keep its history, and it is "
        f"{row['history_sharing']}."
    )


def test_events_shares_the_change_feed(objects):
    row = next((r for r in objects if r["name"] == "partner.events"), None)
    assert row is not None, "partner.events is missing from the share"
    assert bool(row["cdf_shared"]), (
        "partner.events must share its change feed. `WITH CHANGE DATA FEED` is refused "
        "on this metastore (managed-key encryption) and is not what controls it anyway: "
        "cdf_shared follows the table's own delta.enableChangeDataFeed property."
    )


def test_the_volume_is_shared(objects):
    vols = [r for r in objects if r["type"] == "VOLUME"]
    assert len(vols) == 1, f"expected one shared volume, found {len(vols)}"
    assert vols[0]["name"] == "partner.files"


def test_share_contents_match_the_reference(objects, expected):
    got, exp = _rows(objects), sorted(expected["objects"])
    assert got == exp, (
        "The share differs from the reference.\n"
        + "\n".join(f"  got:      {g}\n  expected: {e}"
                    for g, e in zip(got, exp) if g != e)
    )


# ------------------------------------------------------- and what is NOT shared

def test_salaries_is_not_shared_in_this_share(objects):
    leaked = [r["name"] for r in objects if r["shared_object"] == MUST_NOT_SHARE]
    assert not leaked, (
        f"{MUST_NOT_SHARE} is in the share as {leaked}. Nothing errors when you "
        "over-share; that is exactly why the requirement is easy to miss."
    )


def test_salaries_is_not_shared_anywhere(spark, shares):
    leaked = []
    for s in shares:
        for r in spark.sql(f"SHOW ALL IN SHARE {s}").collect():
            if r["shared_object"] == MUST_NOT_SHARE:
                leaked.append(f"{s}.{r['name']}")
    assert not leaked, f"{MUST_NOT_SHARE} is reachable through {leaked}"


# ------------------------------------------------------------------- the recipient

def test_the_recipient_exists_and_is_databricks_to_databricks(w, expected):
    rec = next((r for r in w.recipients.list() if r.name == RECIPIENT), None)
    assert rec is not None, (
        f"recipient {RECIPIENT!r} does not exist. "
        f"Recipients present: {[r.name for r in w.recipients.list()] or 'none'}"
    )
    assert rec.authentication_type.value == expected["recipient_auth"], (
        f"authentication_type is {rec.authentication_type.value}, expected "
        f"{expected['recipient_auth']}. Open-protocol (TOKEN) recipients are disabled "
        "on this metastore, so the recipient must be Databricks-to-Databricks."
    )


def test_the_recipient_targets_this_metastore(w, expected):
    """The sharing identifier is workspace-specific, so it is resolved live."""
    rec = next((r for r in w.recipients.list() if r.name == RECIPIENT), None)
    if rec is None:
        pytest.fail(f"recipient {RECIPIENT!r} does not exist")
    mine = w.metastores.summary().global_metastore_id
    matches = rec.data_recipient_global_metastore_id == mine
    assert matches == expected["recipient_targets_this_metastore"], (
        f"recipient targets {rec.data_recipient_global_metastore_id}, expected this "
        "workspace's own sharing identifier (there is no second metastore to share to "
        "here). Read it from the metastore summary rather than typing it."
    )


def test_the_share_is_granted_to_exactly_that_recipient(grants, expected):
    got = sorted([[r["recipient"], r["privilege"]] for r in grants])
    assert got == sorted(expected["grants"]), (
        f"grants are {got}, expected {sorted(expected['grants'])}. Until the GRANT "
        "runs the share reaches nobody; and any extra recipient is an over-share."
    )
