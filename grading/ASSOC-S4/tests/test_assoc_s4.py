"""Graded tests for the ASSOC-S4 assignment. Authoritative."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import DateType, IntegerType, StringType, StructField, StructType
from pyspark.testing import assertSchemaEqual

PUBLISHED = "workspace.de_prep.s4_gold_regional_orders"
QUARANTINE = "workspace.de_prep.s4_quarantine_orders"

PUBLISHED_SCHEMA = StructType([
    StructField("order_id", StringType(), True),
    StructField("region", StringType(), True),
    StructField("units", IntegerType(), True),
    StructField("ordered_on", DateType(), True),
])
QUARANTINE_SCHEMA = StructType([
    StructField("order_id", StringType(), True),
    StructField("region", StringType(), True),
    StructField("raw_units", StringType(), True),
    StructField("raw_ordered_on", StringType(), True),
    StructField("source_file", StringType(), True),
])


def _fixtures() -> dict:
    env = os.environ.get("ASSOC_S4_FIXTURES")
    if env and Path(env).exists():
        return json.loads(Path(env).read_text())
    for parent in Path(__file__).resolve().parents:
        c = parent / "grading" / "ASSOC-S4" / "expected.json"
        if c.exists():
            return json.loads(c.read_text())
    pytest.fail("expected.json not found; set ASSOC_S4_FIXTURES")


@pytest.fixture(scope="session")
def spark():
    return SparkSession.builder.getOrCreate()


@pytest.fixture(scope="session")
def expected():
    return _fixtures()


@pytest.fixture(scope="session")
def pub(spark):
    try:
        return spark.table(PUBLISHED)
    except Exception as e:
        pytest.fail(f"Could not read {PUBLISHED}. {e}")


@pytest.fixture(scope="session")
def quar(spark):
    try:
        return spark.table(QUARANTINE)
    except Exception as e:
        pytest.fail(f"Could not read {QUARANTINE}. Requirement 2 needs it. {e}")


def test_published_schema(pub):
    assertSchemaEqual(pub.schema, PUBLISHED_SCHEMA)


def test_quarantine_schema(quar):
    assertSchemaEqual(quar.schema, QUARANTINE_SCHEMA)


def test_bad_row_did_not_stop_the_pipeline(pub, expected):
    """Requirements 1 and 3."""
    n = pub.count()
    assert n == expected["published_rows"], (
        f"expected {expected['published_rows']} published rows, got {n}. "
        f"{expected['naive_published_rows']} usually means the poisoned region was "
        "dropped whole and the late arrivals were missed."
    )


def test_nothing_silently_dropped(quar, expected):
    """Requirement 2 - the bad row is kept, not discarded."""
    n = quar.count()
    assert n == expected["quarantined_rows"], (
        f"expected {expected['quarantined_rows']} quarantined row(s), got {n}. "
        "Zero means the bad row was filtered away rather than preserved."
    )
    row = quar.collect()[0]
    assert row["raw_units"] is not None, "the raw value must be preserved for inspection"
    assert row["source_file"], "source_file must record where the bad row came from"


def test_good_rows_from_the_poisoned_region_survived(pub, expected):
    """The whole point of quarantining rather than skipping the file."""
    region = expected["quarantined_region"]
    n = pub.filter(F.col("region") == region).count()
    assert n == expected["rows_by_region"][region], (
        f"expected {expected['rows_by_region'][region]} good rows from '{region}', got "
        f"{n}. Zero means the whole file was skipped because of one bad row."
    )


def test_late_arrivals_included(pub, expected):
    """Requirement 3 - a directory the main glob does not reach."""
    n = pub.filter(F.col("region") == "late_arrivals").count()
    assert n == expected["rows_by_region"]["late_arrivals"], (
        f"expected {expected['rows_by_region']['late_arrivals']} late-arrival rows, got "
        "{n}. They live in a subdirectory of the source."
    )


def test_all_regions_present(pub, expected):
    got = sorted(r["region"] for r in pub.select("region").distinct().collect())
    assert got == expected["regions"], f"expected regions {expected['regions']}, got {got}"


def test_rows_by_region(pub, expected):
    got = {r["region"]: r["n"] for r in
           pub.groupBy("region").agg(F.count("*").alias("n")).collect()}
    assert got == expected["rows_by_region"]


def test_units_total(pub, expected):
    total = pub.agg(F.sum("units")).collect()[0][0]
    assert total == expected["total_units"]


def test_no_nulls_in_published(pub):
    for c in ("order_id", "region", "units", "ordered_on"):
        assert pub.filter(F.col(c).isNull()).count() == 0, (
            f"{c} has nulls - a row that could not be typed belongs in quarantine"
        )
