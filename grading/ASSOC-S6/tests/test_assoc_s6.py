"""Graded tests for the ASSOC-S6 assignment. Authoritative."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import DoubleType, StringType, StructField, StructType
from pyspark.testing import assertSchemaEqual

TABLE = "workspace.de_prep.s6_health_report"
SOURCE = "workspace.de_prep.s6_assess_orders"

EXPECTED_SCHEMA = StructType([
    StructField("finding", StringType(), True),
    StructField("column_name", StringType(), True),
    StructField("metric", DoubleType(), True),
    StructField("detail", StringType(), True),
])


def _fixtures() -> dict:
    env = os.environ.get("ASSOC_S6_FIXTURES")
    if env and Path(env).exists():
        return json.loads(Path(env).read_text())
    for parent in Path(__file__).resolve().parents:
        c = parent / "grading" / "ASSOC-S6" / "expected.json"
        if c.exists():
            return json.loads(c.read_text())
    pytest.fail("expected.json not found; set ASSOC_S6_FIXTURES")


@pytest.fixture(scope="session")
def spark():
    return SparkSession.builder.getOrCreate()


@pytest.fixture(scope="session")
def expected():
    return _fixtures()


@pytest.fixture(scope="session")
def df(spark):
    try:
        return spark.table(TABLE)
    except Exception as e:
        pytest.fail(f"Could not read {TABLE}. {e}")


@pytest.fixture(scope="session")
def rows(df):
    return {r["finding"]: r for r in df.collect()}


def test_schema_matches_the_contract(df):
    assertSchemaEqual(df.schema, EXPECTED_SCHEMA)


def test_all_three_findings_present(df, expected):
    """The lesson's single query finds one of these."""
    got = sorted(r["finding"] for r in df.select("finding").distinct().collect())
    assert got == expected["expected_findings"], (
        f"expected findings {expected['expected_findings']}, got {got}. "
        "Two of the three leave the row count and distinct-key count looking normal."
    )
    assert df.count() == expected["findings"], "one row per finding"


def test_duplicate_keys_finding(rows, expected):
    r = rows.get("duplicate_keys")
    assert r is not None, "no duplicate_keys finding"
    assert r["column_name"] == "order_id"
    assert r["metric"] == pytest.approx(expected["duplicate_rows"], abs=0.5), (
        f"expected {expected['duplicate_rows']} redelivered rows, got {r['metric']}. "
        "This is count(*) minus count(distinct order_id)."
    )


def test_null_regression_finding(rows, expected):
    r = rows.get("null_regression")
    assert r is not None, "no null_regression finding"
    assert r["column_name"] == "channel"
    assert r["metric"] == pytest.approx(expected["null_channel_after"], abs=0.5), (
        f"expected {expected['null_channel_after']} nulls after the regression, got "
        f"{r['metric']}. The metric is the count AFTER it begins, not the total."
    )


def test_skew_finding(rows, expected):
    r = rows.get("skew")
    assert r is not None, "no skew finding"
    assert r["column_name"] == "region"
    assert r["metric"] == pytest.approx(expected["skew_pct"], abs=1.0), (
        f"expected about {expected['skew_pct']}% for the largest region, got {r['metric']}"
    )


def test_details_are_actionable(df):
    """Requirement 4 - a colleague should know what to do next."""
    for r in df.collect():
        d = (r["detail"] or "").strip()
        assert len(d) >= 25, (
            f"detail for '{r['finding']}' is too thin to act on: {d!r}"
        )
        assert any(ch.isdigit() for ch in d), (
            f"detail for '{r['finding']}' cites no number; a finding without evidence "
            "is an opinion"
        )


def test_source_was_not_modified(spark, expected):
    """Graded on diagnosis, not on a fix - the table must be left as found."""
    t = spark.table(SOURCE)
    total, distinct = t.count(), t.select("order_id").distinct().count()
    assert total - distinct == expected["duplicate_rows"], (
        "the source table has been cleaned. This assignment is graded on diagnosis; "
        "removing the duplicates destroys the evidence."
    )
