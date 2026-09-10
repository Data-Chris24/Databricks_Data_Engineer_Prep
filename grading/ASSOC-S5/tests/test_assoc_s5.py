"""Graded tests for the ASSOC-S5 assignment. Authoritative.

The point of this section is promotion, so the tests compare the *two* environments
rather than inspecting one. Anything that could be produced by a single hardcoded
destination fails.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import DoubleType, LongType, StringType, StructField, StructType
from pyspark.testing import assertSchemaEqual

CATALOG = "workspace"
TABLE = "s5_channel_summary"

EXPECTED_SCHEMA = StructType([
    StructField("channel", StringType(), True),
    StructField("txns", LongType(), False),
    StructField("revenue", DoubleType(), True),
    StructField("environment", StringType(), False),
])


def _fixtures() -> dict:
    env = os.environ.get("ASSOC_S5_FIXTURES")
    if env and Path(env).exists():
        return json.loads(Path(env).read_text())
    for parent in Path(__file__).resolve().parents:
        c = parent / "grading" / "ASSOC-S5" / "expected.json"
        if c.exists():
            return json.loads(c.read_text())
    pytest.fail("expected.json not found; set ASSOC_S5_FIXTURES")


@pytest.fixture(scope="session")
def spark():
    return SparkSession.builder.getOrCreate()


@pytest.fixture(scope="session")
def expected():
    return _fixtures()


def _table(spark, schema):
    try:
        return spark.table(f"{CATALOG}.{schema}.{TABLE}")
    except Exception as e:
        pytest.fail(
            f"Could not read {CATALOG}.{schema}.{TABLE}. Requirement 1: the same job "
            f"must be deployed and run against both targets. {e}"
        )


@pytest.mark.parametrize("schema", ["de_prep", "de_prep_staging"])
def test_schema_matches_contract(spark, schema):
    assertSchemaEqual(_table(spark, schema).schema, EXPECTED_SCHEMA)


@pytest.mark.parametrize("schema", ["de_prep", "de_prep_staging"])
def test_row_count(spark, schema, expected):
    n = _table(spark, schema).count()
    assert n == expected["rows_per_environment"], (
        f"{schema}: expected {expected['rows_per_environment']} rows, got {n}"
    )


def test_both_environments_exist(spark, expected):
    """Requirement 1 - a single hardcoded destination cannot produce both."""
    for schema in expected["environments"]:
        assert _table(spark, schema).count() > 0, f"{schema} received no data"


def test_environment_column_records_where_it_landed(spark, expected):
    """Requirement 3 - the strongest evidence the destination was parameterised.

    A hardcoded notebook stamps the same value in both schemas.
    """
    seen = {}
    for schema in expected["environments"]:
        vals = sorted({r["environment"] for r in
                       _table(spark, schema).select("environment").distinct().collect()})
        assert vals == [schema], (
            f"{CATALOG}.{schema}.{TABLE} records environment={vals}, expected ['{schema}']. "
            "If both schemas show the same value, the stamp is hardcoded rather than "
            "derived from the job parameter."
        )
        seen[schema] = vals[0]
    assert len(set(seen.values())) == len(expected["environments"]), (
        "the two environments are indistinguishable in the data"
    )


def test_numbers_match_across_environments(spark, expected):
    """Promotion means the same definition, so the results must agree."""
    frames = {}
    for schema in expected["environments"]:
        frames[schema] = {
            r["channel"]: (r["txns"], round(r["revenue"], 2))
            for r in _table(spark, schema).collect()
        }
    a, b = (frames[s] for s in expected["environments"])
    assert a == b, (
        "the two environments disagree. Promotion means one definition producing the "
        f"same result in each place.\n  {expected['environments'][0]}: {a}\n"
        f"  {expected['environments'][1]}: {b}"
    )


def test_values_are_correct(spark, expected):
    got = {r["channel"]: (r["txns"], round(r["revenue"], 2))
           for r in _table(spark, "de_prep").collect()}
    want = {k: (v["txns"], v["revenue"]) for k, v in expected["by_channel"].items()}
    assert got == want, f"expected {want}, got {got}"


def test_all_channels_present(spark, expected):
    got = sorted(r["channel"] for r in
                 _table(spark, "de_prep").select("channel").distinct().collect())
    assert got == expected["channels"]
