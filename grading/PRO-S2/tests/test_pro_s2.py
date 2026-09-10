"""Graded tests for the PRO-S2 assignment. Authoritative.

Every source disagrees with the others in a way that still *runs*. These tests are
written to catch the answers that look fine: columns lined up by position, a CSV
timestamp that quietly became null, a re-delivery that won when it should not have.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    DoubleType, IntegerType, StringType, StructField, StructType, TimestampType,
)
from pyspark.testing import assertSchemaEqual

BRONZE = "workspace.de_prep.pro_s2_scans_bronze"
SILVER = "workspace.de_prep.pro_s2_scans"

FACILITIES = ["LEEDS", "DUBLIN", "PORTO", "MALMO", "LYON"]
CARRIERS = ["northwind", "brightline", "kestrel"]
STATUSES = ["received", "in_transit", "out_for_delivery", "delivered"]
FORMATS = ["json", "parquet", "avro", "csv", "xml"]

SCHEMA = StructType([
    StructField("scan_id", StringType(), True),
    StructField("facility", StringType(), True),
    StructField("carrier", StringType(), True),
    StructField("status", StringType(), True),
    StructField("weight_kg", DoubleType(), True),
    StructField("scanned_at", TimestampType(), True),
    StructField("revision", IntegerType(), True),
    StructField("route_code", StringType(), True),
    StructField("source_format", StringType(), True),
])


def _fixtures() -> dict:
    env = os.environ.get("PRO_S2_FIXTURES")
    if env and Path(env).exists():
        return json.loads(Path(env).read_text())
    for parent in Path(__file__).resolve().parents:
        c = parent / "grading" / "PRO-S2" / "expected.json"
        if c.exists():
            return json.loads(c.read_text())
    pytest.fail("expected.json not found; set PRO_S2_FIXTURES")


def _counts(df, col):
    return {r[col]: r["n"] for r in
            df.groupBy(col).agg(F.count("*").alias("n")).collect() if r[col] is not None}


@pytest.fixture(scope="session")
def spark():
    return SparkSession.builder.getOrCreate()


@pytest.fixture(scope="session")
def expected():
    return _fixtures()


@pytest.fixture(scope="session")
def bronze(spark):
    try:
        return spark.table(BRONZE)
    except Exception as e:
        pytest.fail(f"Could not read {BRONZE}. {e}")


@pytest.fixture(scope="session")
def silver(spark):
    try:
        return spark.table(SILVER)
    except Exception as e:
        pytest.fail(f"Could not read {SILVER}. {e}")


# --------------------------------------------------------------------- contract

def test_bronze_schema_matches_the_contract(bronze):
    assertSchemaEqual(bronze.schema, SCHEMA)


def test_silver_schema_matches_the_contract(silver):
    assertSchemaEqual(silver.schema, SCHEMA)


# --------------------------------------------------- every source actually arrived

def test_bronze_holds_every_delivered_record(bronze, expected):
    assert bronze.count() == expected["bronze_rows"], (
        "Bronze is append-only: every record from every source, re-deliveries "
        "included. Five formats deliver 660 records between them."
    )


def test_every_format_is_represented(bronze, expected):
    got = _counts(bronze, "source_format")
    assert got == expected["bronze_by_source"], (
        f"Records per source format do not match.\n  got:      {got}\n"
        f"  expected: {expected['bronze_by_source']}\n"
        "A missing format usually means its reader needed an option you did not pass."
    )


# ----------------------------------------- the columns went where they were named

def test_facility_column_contains_facilities(bronze):
    bad = bronze.filter(~F.col("facility").isin(FACILITIES))
    n = bad.count()
    assert n == 0, (
        f"{n} rows have a value in `facility` that is not a facility"
        + (f" (e.g. {bad.select('facility').first()[0]!r})" if n else "")
        + ". `union` lines DataFrames up by position; these sources do not agree on "
          "column order. `unionByName` lines them up by name. A CSV read with an "
          "explicit schema does the same thing - check `enforceSchema`."
    )


def test_carrier_column_contains_carriers(bronze):
    n = bronze.filter(~F.col("carrier").isin(CARRIERS)).count()
    assert n == 0, f"{n} rows have a value in `carrier` that is not a carrier."


def test_status_column_contains_statuses(bronze):
    n = bronze.filter(~F.col("status").isin(STATUSES)).count()
    assert n == 0, f"{n} rows have a value in `status` that is not a status."


# --------------------------------------------------------- types survived the read

def test_no_timestamp_was_lost_in_parsing(bronze):
    n = bronze.filter("scanned_at IS NULL").count()
    assert n == 0, (
        f"{n} rows have a null scanned_at. One source writes dd/MM/yyyy HH:mm:ss, "
        "which neither a cast nor a declared TimestampType will parse - it needs an "
        "explicit pattern. Nothing errors; the values just stop existing."
    )


def test_weights_survived_the_read(bronze, expected):
    n = bronze.filter("weight_kg IS NULL").count()
    assert n == 0, f"{n} rows have a null weight_kg."
    total = round(bronze.agg(F.sum("weight_kg")).collect()[0][0], 2)
    assert total == expected["bronze_total_weight"], (
        f"Bronze weight totals {total}, expected {expected['bronze_total_weight']}."
    )


def test_route_code_is_present_only_where_it_was_delivered(bronze, expected):
    n = bronze.filter("route_code IS NOT NULL").count()
    assert n == expected["route_code_not_null"], (
        f"{n} rows carry a route_code; expected {expected['route_code_not_null']}. "
        "Only one source has that column - unionByName needs allowMissingColumns=True "
        "to null it elsewhere instead of refusing the union."
    )
    stray = bronze.filter("route_code IS NOT NULL AND source_format <> 'avro'").count()
    assert stray == 0, f"{stray} non-Avro rows carry a route_code."


# ------------------------------------------------------- the append was idempotent

def test_bronze_kept_the_re_deliveries(spark, bronze):
    dupes = bronze.groupBy("scan_id").count().filter("count > 1").count()
    assert dupes == 60, (
        f"{dupes} scan_ids appear more than once in bronze; expected 60. Bronze is "
        "append-only - it keeps the corrections as well as the originals. "
        "De-duplicating here loses the history."
    )


def test_silver_has_one_row_per_scan(silver, expected):
    assert silver.count() == expected["silver_rows"]
    assert silver.select("scan_id").distinct().count() == expected["silver_rows"], (
        "Silver must hold exactly one row per scan_id."
    )


def test_silver_kept_the_latest_revision(spark, bronze, silver, expected):
    latest = bronze.groupBy("scan_id").agg(F.max("revision").alias("max_rev"))
    wrong = (silver.join(latest, "scan_id")
             .filter(F.col("revision") != F.col("max_rev")).count())
    assert wrong == 0, (
        f"{wrong} scans in silver are not the highest revision delivered for that "
        "scan. A correction arrived after the original; the later one wins."
    )
    assert silver.filter("revision = 2").count() == expected["revision_2_rows"]


def test_silver_source_mix_reflects_which_delivery_won(silver, expected):
    got = _counts(silver, "source_format")
    assert got == expected["silver_by_source"], (
        f"Source mix in silver does not match.\n  got:      {got}\n"
        f"  expected: {expected['silver_by_source']}\n"
        "This is the number that moves when the wrong copy of a re-delivered scan "
        "wins: the corrections came in on a different format from the originals."
    )


# ------------------------------------------------- known answers (the real check)

def test_status_distribution(silver, expected):
    got = _counts(silver, "status")
    assert got == expected["silver_by_status"], (
        f"got {got}, expected {expected['silver_by_status']}. The corrections change "
        "a scan's status, so this is what a wrong revision choice shows up as."
    )


def test_facility_distribution(silver, expected):
    assert _counts(silver, "facility") == expected["silver_by_facility"]


def test_carrier_distribution(silver, expected):
    assert _counts(silver, "carrier") == expected["silver_by_carrier"]


def test_silver_total_weight(silver, expected):
    total = round(silver.agg(F.sum("weight_kg")).collect()[0][0], 2)
    assert total == expected["silver_total_weight"], (
        f"{total} vs expected {expected['silver_total_weight']}."
    )


def test_probe_scans_match_field_for_field(silver, expected):
    probes = {p["scan_id"]: p for p in expected["probe_scans"]}
    rows = {r["scan_id"]: r for r in
            silver.filter(F.col("scan_id").isin(list(probes))).collect()}
    for sid, p in probes.items():
        assert sid in rows, f"{sid} missing from silver"
        r = rows[sid]
        for field in ("facility", "carrier", "status", "revision",
                      "source_format", "route_code", "weight_kg"):
            assert r[field] == p[field], (
                f"{sid}.{field}: got {r[field]!r}, expected {p[field]!r} "
                f"(this scan came in via {p['source_format']})"
            )
        got_ts = r["scanned_at"].strftime("%Y-%m-%d %H:%M:%S")
        assert got_ts == p["scanned_at"], (
            f"{sid}.scanned_at: got {got_ts}, expected {p['scanned_at']}"
        )
