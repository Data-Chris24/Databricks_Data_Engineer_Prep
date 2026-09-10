"""Graded tests for the PRO-S5 assignment. Authoritative."""

from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

import pytest
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    BooleanType, DateType, DoubleType, IntegerType, StringType, StructField, StructType,
)
from pyspark.testing import assertSchemaEqual

TABLE = "workspace.de_prep.pro_s5_alert_evaluation"
SOURCE = "workspace.de_prep.pro_s5_assess_metrics"

EXPECTED_SCHEMA = StructType([
    StructField("run_date", DateType(), True),
    StructField("day_type", StringType(), True),
    StructField("rows_processed", IntegerType(), True),
    StructField("baseline", DoubleType(), True),
    StructField("pct_of_baseline", DoubleType(), True),
    StructField("should_alert", BooleanType(), True),
])


def _fixtures() -> dict:
    env = os.environ.get("PRO_S5_FIXTURES")
    if env and Path(env).exists():
        return json.loads(Path(env).read_text())
    for parent in Path(__file__).resolve().parents:
        c = parent / "grading" / "PRO-S5" / "expected.json"
        if c.exists():
            return json.loads(c.read_text())
    pytest.fail("expected.json not found; set PRO_S5_FIXTURES")


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


def test_schema_matches_the_contract(df):
    assertSchemaEqual(df.schema, EXPECTED_SCHEMA)


def test_evaluated_most_of_the_history(df, expected):
    n = df.count()
    assert n >= expected["total_days"] * 0.75, (
        f"only {n} days evaluated of {expected['total_days']}. Some warm-up is expected "
        "while the baseline forms, but most of the history should be scored."
    )


def test_no_false_positives_before_the_degradation(df, expected):
    """Requirement 2 - the single most important property of an alert."""
    cutoff = date.fromisoformat(expected["degradation_starts"])
    fp = df.filter(F.col("should_alert") & (F.col("run_date") < F.lit(cutoff)))
    n = fp.count()
    dates = [str(r["run_date"]) for r in fp.select("run_date").limit(5).collect()]
    assert n == 0, (
        f"{n} alerts fired before the degradation began ({cutoff}): {dates}. "
        "An alert that cries wolf in the healthy period is worse than no alert."
    )


def test_the_benign_spike_did_not_alert(df, expected):
    """Requirement 3 - alert on direction, not deviation."""
    spike = date.fromisoformat(expected["spike_date"])
    rows = df.filter(F.col("run_date") == F.lit(spike)).collect()
    if rows:
        assert not rows[0]["should_alert"], (
            f"the campaign day {spike} alerted. It is well ABOVE baseline - a spike is "
            "not an incident."
        )


def test_the_degradation_was_detected(df, expected):
    """Requirement 4."""
    cutoff = date.fromisoformat(expected["degradation_starts"])
    fired = df.filter(F.col("should_alert") & (F.col("run_date") >= F.lit(cutoff)))
    assert fired.count() > 0, (
        "the degradation was never detected. It is gradual and stays inside the overall "
        "range, so an absolute threshold will not see it."
    )


def test_detection_was_reasonably_prompt(df, expected):
    cutoff = date.fromisoformat(expected["degradation_starts"])
    first = (df.filter(F.col("should_alert") & (F.col("run_date") >= F.lit(cutoff)))
             .agg(F.min("run_date")).collect()[0][0])
    assert first is not None
    lag = (first - cutoff).days
    assert lag <= 21, (
        f"first alert came {lag} days after the degradation began. Some latency is the "
        "price of requiring persistence, but three weeks is too long to be useful."
    )


def test_baseline_respects_the_weekly_cycle(df):
    """Requirement 1 - a cross-day-type baseline shows up as systematic bias."""
    means = {r["day_type"]: r["m"] for r in
             df.groupBy("day_type").agg(F.avg("pct_of_baseline").alias("m")).collect()}
    assert set(means) == {"weekday", "weekend"}, f"expected both day types, got {means}"
    gap = abs(means["weekday"] - means["weekend"])
    assert gap < 25, (
        f"weekday and weekend average {means['weekday']:.0f}% and {means['weekend']:.0f}% "
        "of baseline. A baseline that respects the cycle puts both near 100 - this one "
        "is comparing across day types."
    )


def test_baseline_is_positive_where_present(df):
    assert df.filter(F.col("baseline") <= 0).count() == 0
    assert df.filter(F.col("baseline").isNull()).count() == 0, (
        "rows without a baseline should be excluded rather than published with nulls"
    )


def test_source_not_modified(spark, expected):
    assert spark.table(SOURCE).count() == expected["total_days"]
