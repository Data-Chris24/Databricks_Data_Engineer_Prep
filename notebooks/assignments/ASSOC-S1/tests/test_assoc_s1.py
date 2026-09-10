"""Graded tests for the ASSOC-S1 assignment. Authoritative."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    DateType, DoubleType, IntegerType, StringType, StructField, StructType,
)
from pyspark.testing import assertSchemaEqual

SRC = "workspace.de_prep.s1_assess_catalog"
RECOVERED = "workspace.de_prep.s1_recovered_catalog"
REPORT = "workspace.de_prep.s1_incident_report"

RECOVERED_SCHEMA = StructType([
    StructField("sku", StringType(), True),
    StructField("category", StringType(), True),
    StructField("price", DoubleType(), True),
    StructField("listed_on", DateType(), True),
])
REPORT_SCHEMA = StructType([
    StructField("bad_version", IntegerType(), True),
    StructField("good_version", IntegerType(), True),
    StructField("rows_lost", IntegerType(), True),
    StructField("value_lost", DoubleType(), True),
    StructField("detail", StringType(), True),
])


def _fixtures() -> dict:
    env = os.environ.get("ASSOC_S1_FIXTURES")
    if env and Path(env).exists():
        return json.loads(Path(env).read_text())
    for parent in Path(__file__).resolve().parents:
        c = parent / "solutions" / "ASSOC-S1" / "expected.json"
        if c.exists():
            return json.loads(c.read_text())
    pytest.fail("expected.json not found; set ASSOC_S1_FIXTURES")


@pytest.fixture(scope="session")
def spark():
    return SparkSession.builder.getOrCreate()


@pytest.fixture(scope="session")
def expected():
    return _fixtures()


@pytest.fixture(scope="session")
def rec(spark):
    try:
        return spark.table(RECOVERED)
    except Exception as e:
        pytest.fail(f"Could not read {RECOVERED}. {e}")


@pytest.fixture(scope="session")
def report(spark):
    try:
        return spark.table(REPORT)
    except Exception as e:
        pytest.fail(f"Could not read {REPORT}. {e}")


def test_recovered_schema(rec):
    assertSchemaEqual(rec.schema, RECOVERED_SCHEMA)


def test_report_schema(report):
    assertSchemaEqual(report.schema, REPORT_SCHEMA)


def test_recovered_row_count(rec, expected):
    n = rec.count()
    assert n == expected["recovered_rows"], (
        f"expected {expected['recovered_rows']} recovered rows, got {n}. "
        f"{expected['current_rows']} means you read the current (damaged) version."
    )


def test_recovered_prices_are_intact(rec):
    """The bad load zeroed every price - the recovery must not have."""
    zeros = rec.filter("price = 0.0").count()
    assert zeros == 0, (
        f"{zeros} recovered rows still have price 0.0, so this is the damaged version"
    )


def test_recovered_value(rec, expected):
    total = rec.agg(F.round(F.sum("price"), 2)).collect()[0][0]
    assert total == pytest.approx(expected["recovered_revenue"], abs=1.0)


def test_report_is_one_row(report):
    assert report.count() == 1, "the incident report is one row"


def test_report_identifies_the_versions(report, expected):
    r = report.collect()[0]
    assert r["good_version"] == expected["good_version"], (
        f"expected the last good version to be {expected['good_version']}, got "
        f"{r['good_version']}"
    )
    assert r["bad_version"] == expected["bad_version"]


def test_report_quantifies_the_damage(report, expected):
    r = report.collect()[0]
    assert r["rows_lost"] == expected["rows_lost"], (
        f"expected {expected['rows_lost']} rows lost, got {r['rows_lost']}"
    )
    assert r["value_lost"] == pytest.approx(expected["value_lost"], abs=1.0)


def test_detail_is_actionable(report):
    d = (report.collect()[0]["detail"] or "").strip()
    assert len(d) >= 25, f"detail is too thin to act on: {d!r}"
    assert any(ch.isdigit() for ch in d), "detail cites no number"


def test_source_history_preserved(spark, expected):
    """Requirement 2 - the damaged history is the evidence."""
    cur = spark.table(SRC)
    assert cur.count() == expected["current_rows"], (
        "the source table has been restored in place. The damaged version is the "
        "evidence; recover alongside it, not over it."
    )
    versions = [r["version"] for r in spark.sql(f"DESCRIBE HISTORY {SRC}").collect()]
    assert expected["good_version"] in versions, "the good version is no longer in history"
