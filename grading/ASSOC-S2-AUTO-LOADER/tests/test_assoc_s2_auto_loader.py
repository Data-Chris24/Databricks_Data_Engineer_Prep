"""Graded tests for the optional ASSOC-S2-AUTO-LOADER assignment.

Authoritative: this suite decides pass or fail. The optional AI reviewer is
advisory and cannot overturn it.

What it can see, and what it uses it for:

* Each table's Delta history: `STREAMING UPDATE` is what an Auto Loader stream
  writes, so a batch `saveAsTable` with the right rows still fails.
* Each stream's two folders: a checkpoint holds `offsets/` and `commits/`, a schema
  location holds `_schemas/`. Swapping them, the reader-vs-writer confusion the
  lesson is about, is visible from the outside.
* The expected values come from a committed fixture file, not from the reference
  solution, so the suite never needs the answer present.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    DecimalType, DoubleType, IntegerType, LongType, StringType, StructField,
    StructType, TimestampType,
)
from pyspark.testing import assertSchemaEqual

DB = "workspace.de_prep"
WORK = "/Volumes/workspace/de_prep/raw/s2_al_work"
TABLES = ["ferry_tickets", "ferry_vessels", "ferry_manifests", "ferry_crossings", "ferry_scans"]

SCHEMAS = {
    "ferry_tickets": StructType([
        StructField("ticket_no", StringType(), True),
        StructField("route", StringType(), True),
        StructField("vessel", StringType(), True),
        StructField("departs", TimestampType(), True),
        StructField("fare_gbp", DecimalType(8, 2), True),
        StructField("passengers", IntegerType(), True),
        StructField("remarks", StringType(), True),
        StructField("_rescued_data", StringType(), True),
    ]),
    "ferry_crossings": StructType([
        StructField("crossing", StringType(), True),
        StructField("vessel", StringType(), True),
        StructField("departed_at", TimestampType(), True),
        StructField("load_pct", DoubleType(), True),
    ]),
    "ferry_scans": StructType([
        StructField("path", StringType(), True),
        StructField("modificationTime", TimestampType(), True),
        StructField("length", LongType(), True),
    ]),
}

# Checked by name and type, in any order: JSON and XML inference sort fields by
# name, so the order depends on how a learner renames them (measured: with
# attributePrefix "" the attributes sort in among the elements).
MANIFEST_COLUMNS = {
    "crossing": "string",
    "route": "string",
    "cars": "bigint",
    "freight_units": "bigint",
    "hazardous": "boolean",
    "_rescued_data": "string",
}

VESSEL_COLUMNS = {
    "vessel_code": "string",
    "name": "string",
    "built": "bigint",
    "decks": "bigint",
    "engine": "struct<kw:bigint,make:string>",
    "imo_number": "string",
}


def _load_fixtures() -> dict:
    """Locate expected.json: the env var the grading notebook sets, else the repo."""
    env_path = os.environ.get("ASSOC_S2_AUTO_LOADER_FIXTURES")
    if env_path and Path(env_path).exists():
        return json.loads(Path(env_path).read_text())
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "grading" / "ASSOC-S2-AUTO-LOADER" / "expected.json"
        if candidate.exists():
            return json.loads(candidate.read_text())
    pytest.fail("expected.json fixtures not found. Set ASSOC_S2_AUTO_LOADER_FIXTURES to its path.")


@pytest.fixture(scope="session")
def spark():
    return SparkSession.builder.getOrCreate()


@pytest.fixture(scope="session")
def expected():
    return _load_fixtures()


@pytest.fixture(scope="session")
def tables(spark):
    """Every contracted table that exists. A missing one fails only the tests that need it."""
    return {t: spark.table(f"{DB}.{t}") for t in TABLES if spark.catalog.tableExists(f"{DB}.{t}")}


def table(tables, name):
    if name not in tables:
        pytest.fail(f"{DB}.{name} does not exist yet. Create it with an Auto Loader stream.")
    return tables[name]


def _ls(path: str) -> list[str] | None:
    """Names in a volume folder; None if it does not exist. Skips if the grader may not look."""
    from databricks.sdk.runtime import dbutils

    try:
        return sorted(f.name.rstrip("/") for f in dbutils.fs.ls(path))
    except Exception as e:  # noqa: BLE001 - a missing folder and a denied one both raise
        msg = str(e)
        if "PERMISSION_DENIED" in msg or "INSUFFICIENT_PERMISSIONS" in msg:
            pytest.skip(f"the grading job may not read {path}: {msg[:120]}")
        return None


def _utc_naive(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).replace(tzinfo=None)


# ---------------------------------------------------------------- every table


@pytest.mark.parametrize("name", TABLES)
def test_written_by_auto_loader(spark, tables, name):
    """Requirement 1: the table was written by a streaming query. Auto Loader commits show as STREAMING UPDATE in the table's history; a batch read and saveAsTable does not."""
    table(tables, name)
    ops = {r.operation for r in spark.sql(f"DESCRIBE HISTORY {DB}.{name}").collect()}
    assert "STREAMING UPDATE" in ops, (
        f"{name}'s history shows {sorted(ops)}, no STREAMING UPDATE. Load it with "
        "spark.readStream.format('cloudFiles') ... .writeStream ... .toTable()."
    )


@pytest.mark.parametrize("name", TABLES)
def test_checkpoint_and_schema_location_are_where_the_contract_says(tables, name):
    """Requirement 2: the stream's checkpoint is s2_al_work/<table>/_checkpoint and its schema location s2_al_work/<table>/_schema. A checkpoint holds offsets/ and commits/; a schema location holds _schemas/."""
    table(tables, name)
    cp, sl = _ls(f"{WORK}/{name}/_checkpoint"), _ls(f"{WORK}/{name}/_schema")
    if cp is not None and "_schemas" in cp and sl is not None and "offsets" in sl:
        pytest.fail(
            f"{name}: the two locations are swapped. cloudFiles.schemaLocation (a reader option) "
            "points at _checkpoint and checkpointLocation (a writer option) at _schema."
        )
    assert cp is not None and {"offsets", "commits"} <= set(cp), (
        f"{name}: {WORK}/{name}/_checkpoint is {'missing' if cp is None else cp}; "
        "it should be the stream's checkpointLocation, holding offsets/ and commits/."
    )
    assert sl is not None and "_schemas" in sl, (
        f"{name}: {WORK}/{name}/_schema is {'missing' if sl is None else sl}; "
        "it should be the reader's cloudFiles.schemaLocation, holding _schemas/."
    )


@pytest.mark.parametrize("name", sorted(SCHEMAS))
def test_schema_matches_the_contract(tables, name):
    """Requirement 7: column names, types and order match the README's table exactly (assertSchemaEqual) for ferry_tickets, ferry_crossings and ferry_scans."""
    assertSchemaEqual(table(tables, name).schema, SCHEMAS[name])


@pytest.mark.parametrize("name", TABLES)
def test_row_count(tables, expected, name):
    """One row per ticket, vessel, manifest, crossing and scan image: the counts the seeded source holds, no more and no fewer."""
    want = expected[name.removeprefix("ferry_")]["rows"]
    got = table(tables, name).count()
    assert got == want, f"{name}: expected {want} rows, got {got}."


# ---------------------------------------------------------------- tickets


def test_tickets_departs_parsed_on_every_row(tables, expected):
    """Requirement 3: departs is never null. The export writes 01/04/2026 08:15, which neither inference nor a TIMESTAMP hint parses without a timestampFormat."""
    t = table(tables, "ferry_tickets")
    nulls = t.where("departs IS NULL").count()
    assert nulls == 0, (
        f"{nulls} tickets have no departs. If _rescued_data holds the original text, the "
        "values are there but the reader does not know how they are written."
    )
    lo, hi = t.agg(F.min("departs"), F.max("departs")).first()
    assert (lo, hi) == (_utc_naive(expected["tickets"]["min_departs"]), _utc_naive(expected["tickets"]["max_departs"])), (
        f"departs runs from {lo} to {hi}; day and month may be the wrong way round."
    )


def test_tickets_bad_fares_are_rescued(tables, expected):
    """Requirement 3: the fares that are not prices are null in fare_gbp, and their original text is in _rescued_data, so nothing is lost."""
    t = table(tables, "ferry_tickets")
    want = expected["tickets"]
    assert t.where("fare_gbp IS NULL").count() == want["null_fares"], "unexpected number of null fares"
    got = sorted(r[0] for r in t.where("_rescued_data IS NOT NULL").select(F.expr("_rescued_data:fare_gbp")).collect())
    assert got == want["rescued_fares"], (
        f"_rescued_data holds fares {got}, expected {want['rescued_fares']}. A declared "
        "schema without a rescue column, or a STRING fare, loses or keeps the wrong values."
    )
    total = t.agg(F.sum("fare_gbp")).first()[0]
    assert total is not None and float(total) == pytest.approx(want["fare_total"], abs=0.01)


def test_tickets_missing_remarks_are_null(tables, expected):
    """Requirement 3: N/A is the export's way of writing a missing value, so a ticket without remarks has NULL, never the text N/A."""
    t = table(tables, "ferry_tickets")
    na = t.where("remarks = 'N/A'").count()
    assert na == 0, f"{na} remarks are the literal text N/A; tell the reader how a null is written."
    assert t.where("remarks IS NULL").count() == expected["tickets"]["null_remarks"]


def test_tickets_multiline_remarks_intact(tables, expected):
    """Requirement 3: a remark that runs over two lines stays one value in one row, which needs the reader told that a quoted field may hold a line break."""
    t = table(tables, "ferry_tickets")
    got = t.where("remarks LIKE '%\n%'").count()
    assert got == expected["tickets"]["multiline_remarks"], (
        f"{got} remarks contain a line break, expected {expected['tickets']['multiline_remarks']}. "
        "Without multiLine each physical line is parsed as its own row."
    )


@pytest.mark.parametrize("ticket", ["T0000001", "T0000006", "T0000120"])
def test_known_tickets(tables, expected, ticket):
    """Spot-check of specific tickets against precomputed values: route, vessel, departure, fare (null where it was rescued), passengers and remarks."""
    want = expected["tickets"]["probes"][ticket]
    rows = table(tables, "ferry_tickets").where(F.col("ticket_no") == ticket).collect()
    assert len(rows) == 1, f"expected one row for {ticket}, got {len(rows)}"
    got = rows[0]
    for col in ("route", "vessel", "passengers", "remarks"):
        assert got[col] == want[col], f"{ticket}.{col}: expected {want[col]!r}, got {got[col]!r}"
    assert got["departs"] == _utc_naive(want["departs"]), f"{ticket}.departs: expected {want['departs']}, got {got['departs']}"
    if want["fare_gbp"] is None:
        assert got["fare_gbp"] is None
    else:
        assert got["fare_gbp"] == Decimal(str(want["fare_gbp"])).quantize(Decimal("0.01"))


# ---------------------------------------------------------------- vessels


def test_vessels_columns_and_types(tables):
    """The vessels table has the contract's columns with the contract's types, in any order; engine is a struct, which needs real type inference for JSON."""
    got = dict(table(tables, "ferry_vessels").dtypes)
    wrong = {c: got.get(c, "missing") for c, t in VESSEL_COLUMNS.items() if got.get(c) != t}
    assert not wrong, (
        f"ferry_vessels: {wrong} (want {[f'{c} {VESSEL_COLUMNS[c]}' for c in wrong]}). "
        "Every JSON field is a STRING until the reader is told to infer types."
    )


def test_vessels_loaded_in_two_runs(spark, tables, expected):
    """Requirement 4: two streaming loads that each wrote rows, batch 1 and then batch 2, so the second run had to evolve the schema rather than seeing both files at once."""
    table(tables, "ferry_vessels")
    loads = (spark.sql(f"DESCRIBE HISTORY {DB}.ferry_vessels")
             .where("operation = 'STREAMING UPDATE'")
             .where("operationMetrics.numOutputRows > 0").count())
    assert loads >= expected["vessels"]["loads"], (
        f"ferry_vessels has {loads} streaming load(s) that wrote rows; expected "
        f"{expected['vessels']['loads']}. Land batch 1, run the stream, then land batch 2 and run it again."
    )


def test_vessels_schema_evolved(tables):
    """Requirement 4: the schema location recorded a second schema version (_schemas/1) when imo_number arrived, which is what addNewColumns does."""
    table(tables, "ferry_vessels")
    versions = _ls(f"{WORK}/ferry_vessels/_schema/_schemas")
    assert versions is not None and "1" in versions, (
        f"schema versions recorded: {versions}. One version means the stream never met the new "
        "field: did both deliveries land before the first run?"
    )


def test_vessels_imo_only_for_the_second_delivery(tables, expected):
    """Requirement 4: imo_number is filled for the vessels in the second delivery and null for the first, never invented for vessels that did not report it."""
    t = table(tables, "ferry_vessels")
    assert t.where("imo_number IS NOT NULL").count() == expected["vessels"]["with_imo"]
    for code, want in expected["vessels"]["probes"].items():
        rows = t.where(F.col("vessel_code") == code).collect()
        assert len(rows) == 1, f"expected one row for {code}, got {len(rows)}"
        for col, value in want.items():
            assert rows[0][col] == value, f"{code}.{col}: expected {value!r}, got {rows[0][col]!r}"
    make = t.where("vessel_code = 'V01'").select("engine.make").first()[0]
    assert make == expected["vessels"]["engine_make_v01"]


# ---------------------------------------------------------------- manifests, crossings, scans


def test_manifests_columns_and_types(tables):
    """Requirement 5: the manifests table has the contract's columns and types in any order, the attributes named crossing and route, not _crossing and _route."""
    got = dict(table(tables, "ferry_manifests").dtypes)
    wrong = {c: got.get(c, "missing") for c, t in MANIFEST_COLUMNS.items() if got.get(c) != t}
    hint = " XML attributes arrive as _name unless the prefix is changed or the columns renamed." if "_crossing" in got else ""
    assert not wrong, f"ferry_manifests: {wrong} (want {[f'{c} {MANIFEST_COLUMNS[c]}' for c in wrong]}).{hint}"


def test_manifests_known_values(tables, expected):
    """Requirement 5: one row per manifest element, attributes as plain columns: the hazardous count, the cars total and two crossings match."""
    t = table(tables, "ferry_manifests")
    want = expected["manifests"]
    assert t.where("hazardous").count() == want["hazardous"]
    assert t.agg(F.sum("cars")).first()[0] == want["cars_total"]
    for crossing, values in want["probes"].items():
        row = t.where(F.col("crossing") == crossing).first()
        assert row is not None, f"no manifest for {crossing}"
        assert row.asDict() | values == row.asDict(), f"{crossing}: expected {values}, got {row.asDict()}"


def test_crossings_known_values(tables, expected):
    """Two crossings match their precomputed vessel, departure and load: the ORC file's own types, unchanged."""
    t = table(tables, "ferry_crossings")
    for crossing, want in expected["crossings"]["probes"].items():
        row = t.where(F.col("crossing") == crossing).first()
        assert row is not None, f"no crossing {crossing}"
        assert row["vessel"] == want["vessel"]
        assert row["departed_at"] == _utc_naive(want["departed_at"]), f"{crossing}: departed_at {row['departed_at']}"
        assert row["load_pct"] == pytest.approx(want["load_pct"], abs=0.001)


def test_scans_are_images_only(tables, expected):
    """Requirement 6: only the .jpg boarding-card scans are in the table, so the index and notes files in the same folder were filtered out by name."""
    t = table(tables, "ferry_scans")
    others = [r.path for r in t.where("NOT lower(path) LIKE '%.jpg'").collect()]
    assert not others, f"files that are not scans: {others}"
    assert t.agg(F.sum("length")).first()[0] == expected["scans"]["bytes_total"]
