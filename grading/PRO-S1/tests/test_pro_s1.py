"""Graded tests for the PRO-S1 assignment. Authoritative."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window
from pyspark.sql.types import (
    DoubleType, IntegerType, StringType, StructField, StructType, TimestampType,
)
from pyspark.testing import assertSchemaEqual

TABLE = "workspace.de_prep.pro_s1_current_customers"
SOURCE = "workspace.de_prep.pro_s1_assess_changes"

EXPECTED_SCHEMA = StructType([
    StructField("customer_id", StringType(), True),
    StructField("tier", StringType(), True),
    StructField("balance", DoubleType(), True),
    StructField("last_seq", IntegerType(), True),
    StructField("last_event_ts", TimestampType(), True),
])


def _fixtures() -> dict:
    env = os.environ.get("PRO_S1_FIXTURES")
    if env and Path(env).exists():
        return json.loads(Path(env).read_text())
    for parent in Path(__file__).resolve().parents:
        c = parent / "grading" / "PRO-S1" / "expected.json"
        if c.exists():
            return json.loads(c.read_text())
    pytest.fail("expected.json not found; set PRO_S1_FIXTURES")


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


def test_surviving_row_count(df, expected):
    n = df.count()
    assert n == expected["surviving_rows"], (
        f"expected {expected['surviving_rows']} surviving keys, got {n}. "
        f"{expected['naive_dedup_rows']} means one arbitrary event per key was kept - "
        "tombstones included and sequencing ignored."
    )


def test_keys_are_unique(df):
    assert df.count() == df.select("customer_id").distinct().count()


def test_winning_event_is_highest_sequence(spark, df):
    """Requirement 2 - independent of arrival order."""
    src = spark.table(SOURCE)
    w = Window.partitionBy("customer_id").orderBy(F.desc("seq_num"))
    truth = (src.withColumn("rn", F.row_number().over(w)).filter("rn = 1")
             .filter("op != 'delete'")
             .select("customer_id", F.col("seq_num").alias("want_seq")))

    joined = df.join(truth, on="customer_id", how="inner")
    wrong = joined.filter(F.col("last_seq") != F.col("want_seq")).count()
    assert wrong == 0, (
        f"{wrong} rows do not carry the highest seq_num for their key. The feed is "
        "shuffled, so the last row encountered is not the latest event."
    )


def test_tombstoned_keys_are_absent(spark, df, expected):
    """Requirement 3 - a delete removes the key, it does not flag it."""
    src = spark.table(SOURCE)
    w = Window.partitionBy("customer_id").orderBy(F.desc("seq_num"))
    tombstoned = (src.withColumn("rn", F.row_number().over(w)).filter("rn = 1")
                  .filter("op = 'delete'").select("customer_id"))
    n_tomb = tombstoned.count()
    assert n_tomb == expected["tombstoned_keys"]

    leaked = df.join(tombstoned, on="customer_id", how="inner").count()
    assert leaked == 0, (
        f"{leaked} keys whose latest event is a delete are still present"
    )


def test_resurrected_keys_are_present(spark, df):
    """Requirement 4 - deleted then updated means present, because the update wins."""
    src = spark.table(SOURCE)
    deleted_ever = src.filter("op = 'delete'").select("customer_id").distinct()
    w = Window.partitionBy("customer_id").orderBy(F.desc("seq_num"))
    latest_not_delete = (src.withColumn("rn", F.row_number().over(w)).filter("rn = 1")
                         .filter("op != 'delete'").select("customer_id"))
    resurrected = deleted_ever.join(latest_not_delete, on="customer_id", how="inner")
    n = resurrected.count()
    assert n > 0, "fixture problem: no resurrected keys to test"

    present = df.join(resurrected, on="customer_id", how="inner").count()
    assert present == n, (
        f"only {present} of {n} resurrected keys survived. A key deleted and later "
        "updated must be present - its highest sequence is the update."
    )


def test_no_delete_rows_leaked(df, spark):
    """The result is customers, not events - no op column, no delete artefacts."""
    assert "op" not in df.columns, "the op column belongs to the feed, not to current state"
    assert df.filter(F.col("tier").isNull()).count() == 0, (
        "a null tier suggests a delete event was carried through - deletes have no "
        "tier or balance"
    )


@pytest.mark.parametrize("customer_id", ["CUST-00001", "CUST-00002", "CUST-00004"])
def test_known_rows(df, expected, customer_id):
    want = expected["probes"][customer_id]
    rows = df.filter(F.col("customer_id") == customer_id).collect()
    assert len(rows) == 1, f"expected one row for {customer_id}, got {len(rows)}"
    got = rows[0]
    assert got["tier"] == want["tier"]
    assert got["balance"] == pytest.approx(want["balance"], abs=0.01)
    assert got["last_seq"] == want["last_seq"]
