"""Graded tests for the ASSOC-S2 assignment.

Authoritative: this suite decides pass or fail. The optional AI reviewer is
advisory and cannot overturn it.

Two things worth noticing about how these are written, because they are
themselves an exam objective (`PRO-S1-O11`):

* `assertSchemaEqual` compares the whole schema including column order, which is
  why the contract specifies an order.
* The expected values come from a committed fixture file rather than from the
  reference solution, so the suite never needs the answer to be present.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    DoubleType, StringType, StructField, StructType, TimestampType,
)
from pyspark.testing import assertSchemaEqual

TABLE = "workspace.de_prep.silver_sensor_readings"

EXPECTED_SCHEMA = StructType([
    StructField("event_id", StringType(), True),
    StructField("device_id", StringType(), True),
    StructField("site", StringType(), True),
    StructField("firmware", StringType(), True),
    StructField("recorded_at", TimestampType(), True),
    StructField("temperature_c", DoubleType(), True),
    StructField("humidity_pct", DoubleType(), True),
    StructField("battery_pct", DoubleType(), True),
])


def _load_fixtures() -> dict:
    """Locate expected.json.

    ASSOC_S2_FIXTURES wins when set. The grading notebook copies this suite to
    local disk before running it - the Workspace filesystem does not support the
    __pycache__ writes pytest's assertion rewriting needs - so walking up from
    __file__ will not find the repo from there.
    """
    import os

    env_path = os.environ.get("ASSOC_S2_FIXTURES")
    if env_path and Path(env_path).exists():
        return json.loads(Path(env_path).read_text())

    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "grading" / "ASSOC-S2" / "expected.json"
        if candidate.exists():
            return json.loads(candidate.read_text())
    pytest.fail(
        "expected.json fixtures not found. Set ASSOC_S2_FIXTURES to its path, or "
        "run from within the repository."
    )


@pytest.fixture(scope="session")
def spark():
    return SparkSession.builder.getOrCreate()


@pytest.fixture(scope="session")
def expected():
    return _load_fixtures()


@pytest.fixture(scope="session")
def df(spark):
    try:
        return spark.table(TABLE)
    except Exception as e:
        pytest.fail(
            f"Could not read {TABLE}. Have you created it? Original error: {e}"
        )


# ---------------------------------------------------------------- contract


def test_schema_matches_the_contract(df):
    """Column names, types and order, exactly as the README specifies."""
    assertSchemaEqual(df.schema, EXPECTED_SCHEMA)


def test_row_count(df, expected):
    actual = df.count()
    assert actual == expected["row_count"], (
        f"expected {expected['row_count']} rows, got {actual}. "
        f"The source holds {expected['readings_before_dedup']} readings, so "
        f"getting that number means deduplication has not happened."
    )


def test_event_id_is_unique(df, expected):
    """Requirement 2. The source replays some readings in a later file."""
    distinct = df.select("event_id").distinct().count()
    total = df.count()
    assert distinct == total, (
        f"{total - distinct} duplicate event_id(s). Every reading must appear once."
    )
    assert distinct == expected["distinct_event_ids"]


# ---------------------------------------------------------------- the traps


def test_timestamps_are_plausible(df, expected):
    """Requirement 3 - the epoch-unit trap.

    Casting epoch MILLISECONDS straight to TIMESTAMP reads them as seconds and
    lands ~58,000 years in the future. It raises no error, which is what makes it
    worth a test.
    """
    lo = df.agg(F.min("recorded_at")).collect()[0][0]
    hi = df.agg(F.max("recorded_at")).collect()[0][0]
    assert lo is not None and hi is not None, "recorded_at is entirely null"

    floor = datetime(2026, 1, 1, tzinfo=timezone.utc)
    ceiling = datetime(2027, 1, 1, tzinfo=timezone.utc)
    lo_utc = lo.replace(tzinfo=timezone.utc) if lo.tzinfo is None else lo
    hi_utc = hi.replace(tzinfo=timezone.utc) if hi.tzinfo is None else hi

    assert floor <= lo_utc <= ceiling and floor <= hi_utc <= ceiling, (
        f"recorded_at spans {lo} to {hi}, which is not in 2026. "
        "recorded_at_ms is in MILLISECONDS - divide by 1000 before casting."
    )


def test_battery_column_survived(df, expected):
    """Requirement 4 - the schema-merge trap.

    battery_pct exists in only one source file. A read that samples the others
    drops it silently.
    """
    non_null = df.filter(F.col("battery_pct").isNotNull()).count()
    assert non_null == expected["rows_with_battery"], (
        f"expected {expected['rows_with_battery']} rows with battery_pct, got "
        f"{non_null}. Zero usually means the column was dropped when the files "
        "were read - the schemas differ between batches."
    )


def test_early_readings_have_no_battery(df, expected):
    """The column must be null where the devices did not report it, not zero."""
    nulls = df.filter(F.col("battery_pct").isNull()).count()
    assert nulls == expected["row_count"] - expected["rows_with_battery"], (
        "Readings taken before battery reporting must be null, not filled with a "
        "default. Filling an unknown invents data."
    )


# ---------------------------------------------------------------- known answers


@pytest.mark.parametrize("event_id", ["EVT-0000001", "EVT-0000050", "EVT-0000137"])
def test_known_readings(df, expected, event_id):
    """Spot-checks against precomputed answers, including one battery row."""
    want = expected["probes"][event_id]
    rows = df.filter(F.col("event_id") == event_id).collect()
    assert len(rows) == 1, f"expected exactly one row for {event_id}, got {len(rows)}"
    got = rows[0]

    assert got["device_id"] == want["device_id"]
    assert got["temperature_c"] == pytest.approx(want["temperature_c"], abs=0.01)
    assert got["humidity_pct"] == pytest.approx(want["humidity_pct"], abs=0.01)

    want_ts = datetime.fromisoformat(want["recorded_at"].replace("Z", "+00:00"))
    got_ts = got["recorded_at"]
    got_ts = got_ts.replace(tzinfo=timezone.utc) if got_ts.tzinfo is None else got_ts
    assert got_ts == want_ts, f"{event_id}: expected {want_ts}, got {got_ts}"

    if want["battery_pct"] is None:
        assert got["battery_pct"] is None
    else:
        assert got["battery_pct"] == pytest.approx(want["battery_pct"], abs=0.01)


def test_devices_and_sites_are_populated(df, expected):
    assert df.select("device_id").distinct().count() == expected["distinct_devices"]
    for col in ("device_id", "site", "firmware"):
        assert df.filter(F.col(col).isNull()).count() == 0, (
            f"{col} has nulls - it comes from the document, not the reading, so "
            "it should be populated on every exploded row."
        )
