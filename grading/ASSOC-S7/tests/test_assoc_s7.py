"""Graded tests for the ASSOC-S7 assignment. Authoritative.

These check *structure and policy*, not row values, because what a caller sees is by
design a function of who they are. The suite runs as a workspace admin (the
break-glass principal requirement 4 asks for), so it can see rows at all.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import DateType, DoubleType, StringType, StructField, StructType
from pyspark.testing import assertSchemaEqual

TABLE = "workspace.de_prep.s7_governed_employees"
SOURCE = "workspace.de_prep.s7_assess_employees"

EXPECTED_SCHEMA = StructType([
    StructField("employee_id", StringType(), True),
    StructField("full_name", StringType(), True),
    StructField("national_id_hash", StringType(), True),
    StructField("region", StringType(), True),
    StructField("department", StringType(), True),
    StructField("salary", DoubleType(), True),
    StructField("case_note", StringType(), True),
    StructField("hired_on", DateType(), True),
])


def _fixtures() -> dict:
    env = os.environ.get("ASSOC_S7_FIXTURES")
    if env and Path(env).exists():
        return json.loads(Path(env).read_text())
    for parent in Path(__file__).resolve().parents:
        c = parent / "grading" / "ASSOC-S7" / "expected.json"
        if c.exists():
            return json.loads(c.read_text())
    pytest.fail("expected.json not found; set ASSOC_S7_FIXTURES")


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


def test_national_id_is_absent(df, expected):
    """Requirement 1 - a mask is not enough; the value must not be in the table."""
    for col in expected["forbidden_columns"]:
        assert col not in df.columns, (
            f"'{col}' is still present. Masking it is not sufficient - a mask can be "
            "dropped by anyone who can alter the table. Publish a hash instead."
        )


def test_hash_is_irreversible_and_unique(df, expected):
    lengths = df.select(F.length("national_id_hash").alias("n")).distinct().collect()
    assert [r["n"] for r in lengths] == [expected["hash_length"]], (
        f"expected every hash to be {expected['hash_length']} characters (sha2-256), "
        f"got lengths {[r['n'] for r in lengths]}"
    )
    distinct = df.select("national_id_hash").distinct().count()
    assert distinct == expected["distinct_hashes"], (
        f"expected {expected['distinct_hashes']} distinct hashes, got {distinct}. "
        "Collisions or a constant value would destroy the link the hash must preserve."
    )


def test_all_source_rows_published(df, expected):
    """Requirement 4 in effect - a break-glass caller sees everything."""
    n = df.count()
    assert n == expected["visible_rows_admin"], (
        f"expected {expected['visible_rows_admin']} rows visible to a break-glass "
        f"caller, got {n}. Zero means the row filter excluded everyone, including you."
    )


def test_masks_are_attached(spark, expected):
    """Requirement 2 - checked against the catalog, not by inspecting values."""
    cols = spark.sql(f"DESCRIBE EXTENDED {TABLE}").collect()
    text = " ".join(str(r.asDict()) for r in cols).lower()
    for col in expected["masked_columns"]:
        assert col in text, f"{col} missing from the table description"
    masked = spark.sql(f"""
        SELECT column_name, mask_name
        FROM system.information_schema.column_masks
        WHERE table_name = 's7_governed_employees'
    """).collect() if _has_info_schema(spark) else []
    if masked:
        got = sorted(r["column_name"] for r in masked)
        assert got == expected["masked_columns"], (
            f"expected masks on {expected['masked_columns']}, found on {got}"
        )


def test_row_filter_is_attached(spark):
    """Requirement 3."""
    if not _has_info_schema(spark):
        pytest.skip("system.information_schema not readable here")
    rows = spark.sql("""
        SELECT filter_name FROM system.information_schema.row_filters
        WHERE table_name = 's7_governed_employees'
    """).collect()
    assert rows, "no row filter attached to the governed table (requirement 3)"


def test_regions_intact(df, expected):
    got = sorted(r["region"] for r in df.select("region").distinct().collect())
    assert got == expected["regions"], f"expected regions {expected['regions']}, got {got}"


def test_row_count_matches_source(spark, df, expected):
    src = spark.table(SOURCE).count()
    assert src == expected["source_rows"]
    assert df.count() == src, "governing the data must not drop rows for a break-glass caller"


def _has_info_schema(spark) -> bool:
    try:
        spark.sql("SELECT 1 FROM system.information_schema.column_masks LIMIT 1").collect()
        return True
    except Exception:
        return False
