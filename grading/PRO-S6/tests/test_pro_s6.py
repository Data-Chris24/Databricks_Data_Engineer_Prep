"""Graded tests for the PRO-S6 assignment. Authoritative."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import DoubleType, StringType, StructField, StructType
from pyspark.testing import assertSchemaEqual

TABLE = "workspace.de_prep.pro_s6_optimization_report"
SOURCE = "workspace.de_prep.pro_s6_assess_orders"

EXPECTED_SCHEMA = StructType([
    StructField("finding", StringType(), True),
    StructField("recommendation", StringType(), True),
    StructField("metric", DoubleType(), True),
    StructField("detail", StringType(), True),
])


def _fixtures() -> dict:
    env = os.environ.get("PRO_S6_FIXTURES")
    if env and Path(env).exists():
        return json.loads(Path(env).read_text())
    for parent in Path(__file__).resolve().parents:
        c = parent / "grading" / "PRO-S6" / "expected.json"
        if c.exists():
            return json.loads(c.read_text())
    pytest.fail("expected.json not found; set PRO_S6_FIXTURES")


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


def test_all_three_findings(df, expected):
    got = sorted(r["finding"] for r in df.select("finding").distinct().collect())
    assert got == expected["expected_findings"], (
        f"expected {expected['expected_findings']}, got {got}. Clustering addresses "
        "one of the three causes; the other two are unrelated to layout."
    )
    assert df.count() == expected["findings"]


def test_small_files_finding(rows, expected):
    r = rows.get("small_files")
    assert r is not None
    assert r["metric"] == pytest.approx(expected["n_files"], abs=0.5), (
        f"expected {expected['n_files']} files, got {r['metric']}"
    )
    assert "optimize" in (r["recommendation"] or "").lower(), (
        "the fix for many small files is compaction"
    )


def test_wide_projection_finding(rows, expected):
    r = rows.get("wide_projection")
    assert r is not None
    assert r["metric"] == pytest.approx(expected["n_columns"], abs=0.5), (
        f"expected {expected['n_columns']} columns, got {r['metric']}"
    )


def test_bad_cluster_key_finding(rows, expected):
    """Requirement 2 - naming the wrong choice, not just any column."""
    r = rows.get("bad_cluster_key")
    assert r is not None
    assert expected["bad_key"] in (r["recommendation"] or ""), (
        f"the recommendation must name {expected['bad_key']}, the column that would be "
        f"the wrong clustering choice. Got: {r['recommendation']!r}"
    )
    assert r["metric"] == pytest.approx(expected["bad_card_pct"], abs=2.0), (
        f"expected about {expected['bad_card_pct']}% cardinality, got {r['metric']}"
    )
    assert expected["good_key"] in (r["detail"] or ""), (
        f"the detail must say what to cluster on instead (expected {expected['good_key']})"
    )


def test_details_cite_numbers(df):
    for r in df.collect():
        d = (r["detail"] or "").strip()
        assert len(d) >= 25, f"detail for '{r['finding']}' is too thin: {d!r}"
        assert any(ch.isdigit() for ch in d), (
            f"detail for '{r['finding']}' cites no number"
        )


def test_source_not_optimised(spark, expected):
    """Requirement 3 - the current state is the evidence."""
    d = spark.sql(f"DESCRIBE DETAIL {SOURCE}").collect()[0]
    assert d["numFiles"] == expected["n_files"], (
        f"the source now has {d['numFiles']} files, not {expected['n_files']}. This "
        "assignment is graded on analysis; running OPTIMIZE destroys the evidence."
    )
    assert not d["clusteringColumns"], (
        "clustering has been applied to the source. Recommend it; do not do it."
    )
