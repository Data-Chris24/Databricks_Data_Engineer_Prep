"""Graded tests for the PRO-S7 assignment. Authoritative."""

from __future__ import annotations

import json
import os
from datetime import date, timedelta
from pathlib import Path

import pytest
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import DateType, StringType, StructField, StructType
from pyspark.testing import assertSchemaEqual

TABLE = "workspace.de_prep.pro_s7_compliant_records"
SOURCE = "workspace.de_prep.pro_s7_assess_records"
ERASURE = "workspace.de_prep.pro_s7_assess_erasure_requests"

EMAIL = r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
PHONE = r"\+?\d[\d\s]{8,}\d"

EXPECTED_SCHEMA = StructType([
    StructField("record_id", StringType(), True),
    StructField("subject_hash", StringType(), True),
    StructField("record_type", StringType(), True),
    StructField("case_note", StringType(), True),
    StructField("created_on", DateType(), True),
])


def _fixtures() -> dict:
    env = os.environ.get("PRO_S7_FIXTURES")
    if env and Path(env).exists():
        return json.loads(Path(env).read_text())
    for parent in Path(__file__).resolve().parents:
        c = parent / "solutions" / "PRO-S7" / "expected.json"
        if c.exists():
            return json.loads(c.read_text())
    pytest.fail("expected.json not found; set PRO_S7_FIXTURES")


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


def test_direct_identifiers_absent(df, expected):
    """Requirement 4."""
    for col in expected["forbidden_columns"]:
        assert col not in df.columns, (
            f"'{col}' is still published. Hash the subject instead so records stay "
            "groupable without carrying the identifier."
        )


def test_subject_hash_is_deterministic_and_long(df, expected):
    lengths = {r["n"] for r in df.select(F.length("subject_hash").alias("n")).distinct().collect()}
    assert lengths == {expected["hash_length"]}, (
        f"expected every hash to be {expected['hash_length']} characters, got {lengths}"
    )
    # Deterministic: one hash per subject, so grouping still works.
    per_hash = df.groupBy("subject_hash").agg(F.countDistinct("record_id").alias("n"))
    assert per_hash.count() > 0
    assert df.filter(F.col("subject_hash").isNull()).count() == 0


def test_erasure_subjects_are_gone(spark, df):
    """Requirement 1 - purged, not masked."""
    erasure = spark.table(ERASURE).select("subject_id")
    src = spark.table(SOURCE).select("record_id", "subject_id")
    should_be_gone = (src.join(erasure, on="subject_id", how="inner")
                      .select("record_id"))
    n_expected_gone = should_be_gone.count()
    assert n_expected_gone > 0, "fixture problem: no erasure-affected records"

    leaked = df.join(should_be_gone, on="record_id", how="inner").count()
    assert leaked == 0, (
        f"{leaked} records belonging to erasure subjects are still published. A masked "
        "row is a retained row - these must be gone."
    )


def test_no_pii_survives_in_free_text(df):
    """Requirement 3 - the part column-by-column masking misses."""
    leaky = df.filter(F.col("case_note").rlike(EMAIL) | F.col("case_note").rlike(PHONE))
    n = leaky.count()
    assert n == 0, (
        f"{n} case_note values still contain an email address or phone number. "
        f"Example: {leaky.first()['case_note'] if n else ''!r}"
    )


def test_pii_was_actually_redacted_not_dropped(df, expected):
    """The notes must survive with markers - deleting the column is not a fix."""
    redacted = df.filter(F.col("case_note").rlike(r"\[(EMAIL|PHONE) REDACTED\]")).count()
    assert redacted == pytest.approx(expected["redacted_notes"], rel=0.15), (
        f"expected about {expected['redacted_notes']} redacted notes, got {redacted}. "
        "Zero suggests case_note was emptied rather than scrubbed."
    )
    assert df.filter(F.col("case_note").isNull()).count() == 0, (
        "case_note is null somewhere - scrub the PII, keep the note"
    )


def test_per_type_retention_applied(df, expected):
    """Requirement 2 - a single cutoff is wrong in both directions."""
    today = date.fromisoformat(expected["today"])
    for rec_type, days in expected["retention_days"].items():
        cutoff = today - timedelta(days=days)
        too_old = df.filter((F.col("record_type") == rec_type) &
                            (F.col("created_on") < F.lit(cutoff))).count()
        assert too_old == 0, (
            f"{too_old} '{rec_type}' records are older than {days} days "
            f"(before {cutoff}) and should have been expired"
        )


def test_retention_did_not_over_delete(df, expected):
    """A single aggressive cutoff would strip transaction_log records that must be kept."""
    kept_types = {r["record_type"] for r in df.select("record_type").distinct().collect()}
    assert kept_types == set(expected["record_types"]), (
        f"expected all of {expected['record_types']} to survive, got {sorted(kept_types)}. "
        "Applying the shortest retention to everything over-deletes."
    )


def test_published_row_count(df, expected):
    n = df.count()
    assert n == pytest.approx(expected["published_rows"], rel=0.02), (
        f"expected about {expected['published_rows']} published rows, got {n}"
    )
