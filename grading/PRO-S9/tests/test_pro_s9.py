"""Graded tests for the PRO-S9 assignment. Authoritative."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import IntegerType, StringType, StructField, StructType
from pyspark.testing import assertSchemaEqual

TABLE = "workspace.de_prep.pro_s9_incident_report"
SOURCE = "workspace.de_prep.pro_s9_assess_daily"

EXPECTED_SCHEMA = StructType([
    StructField("first_bad_date", StringType(), True),
    StructField("missing_source", StringType(), True),
    StructField("degraded_days", IntegerType(), True),
    StructField("rows_lost", IntegerType(), True),
    StructField("detail", StringType(), True),
])


def _fixtures() -> dict:
    env = os.environ.get("PRO_S9_FIXTURES")
    if env and Path(env).exists():
        return json.loads(Path(env).read_text())
    for parent in Path(__file__).resolve().parents:
        c = parent / "grading" / "PRO-S9" / "expected.json"
        if c.exists():
            return json.loads(c.read_text())
    pytest.fail("expected.json not found; set PRO_S9_FIXTURES")


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
def row(df):
    rows = df.collect()
    assert len(rows) == 1, f"the incident report is one row, got {len(rows)}"
    return rows[0]


def test_schema_matches_the_contract(df):
    assertSchemaEqual(df.schema, EXPECTED_SCHEMA)


def test_first_bad_date(row, expected):
    """Requirement 1 - when it started, not merely that it is broken."""
    assert row["first_bad_date"] == expected["first_bad_date"], (
        f"expected the first degraded day to be {expected['first_bad_date']}, got "
        f"{row['first_bad_date']!r}. It is the first date where the source count drops "
        "and does not recover."
    )


def test_missing_source(row, expected):
    assert row["missing_source"] == expected["missing_source"], (
        f"expected {expected['missing_source']}, got {row['missing_source']!r}"
    )


def test_degraded_days(row, expected):
    assert row["degraded_days"] == expected["degraded_days"], (
        f"expected {expected['degraded_days']} degraded days, got {row['degraded_days']}"
    )


def test_rows_lost_estimate(row, expected):
    """Requirement 3 - within 10%, since it is an estimate."""
    want = expected["rows_lost"]
    got = row["rows_lost"]
    assert got == pytest.approx(want, rel=0.10), (
        f"expected roughly {want} rows lost, got {got}. Healthy daily average minus "
        "degraded daily average, times the number of degraded days."
    )


def test_detail_is_actionable(row):
    d = (row["detail"] or "").strip()
    assert len(d) >= 30, f"detail is too thin to act on: {d!r}"
    assert any(ch.isdigit() for ch in d), "detail cites no number"


def test_the_failure_really_was_silent(spark):
    """Guards the premise: if the history contains a failure, the exercise is different."""
    ops = [r["operation"] for r in spark.sql(f"DESCRIBE HISTORY {SOURCE}").collect()]
    assert not [o for o in ops if "FAIL" in o.upper()], (
        "the source history contains a failed operation; this assignment is about "
        "failures that leave no error"
    )


def test_source_not_modified(spark, expected):
    """Requirement 4."""
    t = spark.table(SOURCE)
    assert t.count() == expected["total_rows"], (
        "the source table has been changed. This is graded on diagnosis; backfilling "
        "the missing source destroys the evidence."
    )
    max_sources = (t.groupBy("run_date")
                   .agg(F.countDistinct("source_system").alias("s"))
                   .agg(F.max("s")).collect()[0][0])
    assert max_sources == expected["healthy_sources"]
