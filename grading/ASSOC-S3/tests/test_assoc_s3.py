"""Graded tests for the ASSOC-S3 assignment. Authoritative."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    BooleanType, DateType, DoubleType, StringType, StructField, StructType,
)
from pyspark.testing import assertSchemaEqual

TABLE = "workspace.de_prep.s3_gold_billing_enriched"

EXPECTED_SCHEMA = StructType([
    StructField("billing_id", StringType(), True),
    StructField("account_id", StringType(), True),
    StructField("plan_id", StringType(), True),
    StructField("event_date", DateType(), True),
    StructField("event_type", StringType(), True),
    StructField("amount", DoubleType(), True),
    StructField("signed_amount", DoubleType(), True),
    StructField("plan_name", StringType(), True),
    StructField("tier", StringType(), True),
    StructField("plan_missing", BooleanType(), True),
])


def _fixtures() -> dict:
    env = os.environ.get("ASSOC_S3_FIXTURES")
    if env and Path(env).exists():
        return json.loads(Path(env).read_text())
    for parent in Path(__file__).resolve().parents:
        c = parent / "grading" / "ASSOC-S3" / "expected.json"
        if c.exists():
            return json.loads(c.read_text())
    pytest.fail("expected.json not found; set ASSOC_S3_FIXTURES")


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
        pytest.fail(f"Could not read {TABLE}. Have you created it? {e}")


def test_schema_matches_the_contract(df):
    """Column names, types and order match the README's output contract exactly."""
    assertSchemaEqual(df.schema, EXPECTED_SCHEMA)


def test_one_row_per_billing_event(df, expected):
    """Requirement 1: one output row per billing event. plan_id repeats in the dimension, so a naive equi-join multiplies rows; an inner join drops the events whose plan is missing."""
    n = df.count()
    assert n == expected["row_count"], (
        f"expected {expected['row_count']} rows, got {n}. "
        f"{expected['naive_join_rows']} means a naive equi-join fanned out - plan_id is "
        f"not unique in the dimension. {expected['matched_rows']} means an inner join "
        "dropped the events whose plan is missing."
    )


def test_billing_id_is_unique(df):
    """billing_id is unique in the output: the join must not fan out."""
    total, distinct = df.count(), df.select("billing_id").distinct().count()
    assert total == distinct, f"{total - distinct} duplicate billing_id(s)"


def test_orphan_events_kept_and_flagged(df, expected):
    """Requirement 2: events whose plan is missing are kept and flagged plan_missing = true, with no plan details filled in."""
    orphans = df.filter("plan_missing").count()
    assert orphans == expected["orphan_rows"], (
        f"expected {expected['orphan_rows']} events with a missing plan, got {orphans}. "
        "Zero usually means an inner join dropped them."
    )
    assert df.filter("plan_missing AND plan_name IS NOT NULL").count() == 0, (
        "plan_missing is true but plan_name is populated - the flag disagrees with the data"
    )


def test_matched_rows_have_plan_details(df, expected):
    """Rows flagged plan_missing = false carry plan_name and tier."""
    matched = df.filter("plan_missing = false")
    assert matched.count() == expected["matched_rows"]
    assert matched.filter("plan_name IS NULL OR tier IS NULL").count() == 0, (
        "a row is flagged as matched but has no plan details"
    )


def test_amounts_are_in_currency_units(df, expected):
    """Requirement 4: amount is in currency units. The source holds minor units (cents); summing them unconverted gives a total 100 times too large."""
    total = df.agg(F.round(F.sum("amount"), 2)).collect()[0][0]
    assert total == pytest.approx(expected["total_amount"], abs=0.5), (
        f"total amount is {total}, expected about {expected['total_amount']}. "
        f"Roughly {expected['total_amount'] * 100:.0f} means amount_cents was summed "
        "without converting from minor units."
    )


def test_refunds_are_negative(df, expected):
    """Refunds carry a negative signed_amount and the signed total matches the reference."""
    assert df.filter("event_type = 'refund' AND signed_amount > 0").count() == 0, (
        "a refund has a positive signed_amount"
    )
    total = df.agg(F.round(F.sum("signed_amount"), 2)).collect()[0][0]
    assert total == pytest.approx(expected["total_signed"], abs=0.5)


@pytest.mark.parametrize("billing_id", ["BILL-000001", "BILL-000300", "BILL-000600"])
def test_known_rows(df, expected, billing_id):
    """Spot-check of specific billing_ids: the plan version in effect on the event date, the converted amount and the flag."""
    want = expected["probes"][billing_id]
    rows = df.filter(F.col("billing_id") == billing_id).collect()
    assert len(rows) == 1, f"expected one row for {billing_id}, got {len(rows)}"
    got = rows[0]
    assert got["plan_id"] == want["plan_id"]
    assert got["plan_name"] == want["plan_name"]
    assert got["amount"] == pytest.approx(want["amount"], abs=0.01)
    assert got["signed_amount"] == pytest.approx(want["signed_amount"], abs=0.01)
    assert bool(got["plan_missing"]) is bool(want["plan_missing"])
