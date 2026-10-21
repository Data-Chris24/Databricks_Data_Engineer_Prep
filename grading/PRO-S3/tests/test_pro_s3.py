"""Graded tests for the PRO-S3 assignment. Authoritative."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import DoubleType, StringType, StructField, StructType
from pyspark.testing import assertSchemaEqual

TABLE = "workspace.de_prep.pro_s3_quality_findings"
SOURCE = "workspace.de_prep.pro_s3_assess_meter_readings"

EXPECTED_SCHEMA = StructType([
    StructField("finding", StringType(), True),
    StructField("affected_rows", DoubleType(), True),
    StructField("affected_devices", StringType(), True),
    StructField("detail", StringType(), True),
])


def _fixtures() -> dict:
    env = os.environ.get("PRO_S3_FIXTURES")
    if env and Path(env).exists():
        return json.loads(Path(env).read_text())
    for parent in Path(__file__).resolve().parents:
        c = parent / "grading" / "PRO-S3" / "expected.json"
        if c.exists():
            return json.loads(c.read_text())
    pytest.fail("expected.json not found; set PRO_S3_FIXTURES")


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
    """Column names, types and order match the README's output contract exactly."""
    assertSchemaEqual(df.schema, EXPECTED_SCHEMA)


def test_all_three_findings(df, expected):
    """The report names all three findings (meter_backwards, sequence_gap, duplicate_timestamp), one row each. Every row is individually valid; all three defects are between rows."""
    got = sorted(r["finding"] for r in df.select("finding").distinct().collect())
    assert got == expected["expected_findings"], (
        f"expected {expected['expected_findings']}, got {got}. Every row here is "
        "individually valid - all three defects are between rows."
    )
    assert df.count() == expected["findings"]


def test_row_level_checks_really_do_find_nothing(spark, expected):
    """Guards the premise: no source row fails a row-level check (null or negative total, null timestamp), so the defects are only visible between rows."""
    t = spark.table(SOURCE)
    n = t.filter(F.col("meter_total").isNull() | (F.col("meter_total") < 0) |
                 F.col("read_at").isNull()).count()
    assert n == expected["row_level_failures"], (
        f"{n} rows fail a row-level check; this assignment is about defects that only "
        "exist between rows"
    )


def test_backwards_finding(rows, expected):
    """meter_backwards counts readings lower than the previous reading of the same device, and lists the affected devices comma-separated in order."""
    r = rows.get("meter_backwards")
    assert r is not None
    assert r["affected_rows"] == pytest.approx(expected["backwards"], abs=0.5), (
        f"expected {expected['backwards']} backwards readings, got {r['affected_rows']}. "
        "Note a duplicate timestamp with a higher value also makes the next reading "
        "look like a decrease."
    )
    assert r["affected_devices"] == ",".join(expected["backwards_devices"]), (
        f"expected devices {expected['backwards_devices']}, got {r['affected_devices']!r}"
    )


def test_gap_finding(rows, expected):
    """sequence_gap counts readings more than 15 minutes after the previous reading of the same device, and lists the affected devices."""
    r = rows.get("sequence_gap")
    assert r is not None
    assert r["affected_rows"] == pytest.approx(expected["gaps"], abs=0.5)
    assert r["affected_devices"] == ",".join(expected["gap_devices"])


def test_duplicate_finding(rows, expected):
    """duplicate_timestamp counts readings that share a device and timestamp with another reading, and lists the affected devices."""
    r = rows.get("duplicate_timestamp")
    assert r is not None
    assert r["affected_rows"] == pytest.approx(expected["duplicates"], abs=0.5)
    assert r["affected_devices"] == ",".join(expected["duplicate_devices"])


def test_details_cite_numbers(df):
    """Each finding's detail is a sentence a colleague could act on: at least 25 characters and it cites the number behind the finding, e.g. '14 readings on 3 devices went backwards; check meter M-07 first'."""
    for r in df.collect():
        d = (r["detail"] or "").strip()
        assert len(d) >= 25, f"detail for '{r['finding']}' is too thin: {d!r}"
        assert any(ch.isdigit() for ch in d), f"detail for '{r['finding']}' cites no number; put the affected count in the sentence"


def test_source_not_cleaned(spark, expected):
    """Requirement 3: the source is left as found (duplicates still present). This is graded on findings; removing them destroys the evidence."""
    t = spark.table(SOURCE)
    dupes = t.groupBy("device_id", "read_at").count().filter("count > 1").count()
    assert dupes == expected["duplicates"], (
        "the source has been cleaned. This is graded on findings; removing the "
        "duplicates destroys the evidence."
    )
