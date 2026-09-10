"""Graded tests for the PRO-S10 assignment. Authoritative.

These check the *model*, not the code that produced it: that the dimension keys one
version rather than one customer, and that every fact joins to the version that was
current when the fact happened.
"""

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

DIM = "workspace.de_prep.pro_s10_dim_customer"
FACT = "workspace.de_prep.pro_s10_fact_orders"
ORDERS = "workspace.de_prep.pro_s10_assess_orders"
VERSIONS = "workspace.de_prep.pro_s10_assess_customer_versions"

DIM_SCHEMA = StructType([
    StructField("customer_sk", StringType(), True),
    StructField("customer_id", StringType(), True),
    StructField("segment", StringType(), True),
    StructField("region", StringType(), True),
    StructField("valid_from", DateType(), True),
    StructField("valid_to", DateType(), True),
    StructField("is_current", BooleanType(), True),
])

FACT_SCHEMA = StructType([
    StructField("order_id", StringType(), True),
    StructField("customer_sk", StringType(), True),
    StructField("customer_id", StringType(), True),
    StructField("segment_at_order", StringType(), True),
    StructField("region_at_order", StringType(), True),
    StructField("amount", DoubleType(), True),
    StructField("ordered_on", DateType(), True),
])


def _fixtures() -> dict:
    env = os.environ.get("PRO_S10_FIXTURES")
    if env and Path(env).exists():
        return json.loads(Path(env).read_text())
    for parent in Path(__file__).resolve().parents:
        c = parent / "solutions" / "PRO-S10" / "expected.json"
        if c.exists():
            return json.loads(c.read_text())
    pytest.fail("expected.json not found; set PRO_S10_FIXTURES")


@pytest.fixture(scope="session")
def spark():
    return SparkSession.builder.getOrCreate()


@pytest.fixture(scope="session")
def expected():
    return _fixtures()


@pytest.fixture(scope="session")
def dim(spark):
    try:
        return spark.table(DIM)
    except Exception as e:
        pytest.fail(f"Could not read {DIM}. {e}")


@pytest.fixture(scope="session")
def fact(spark):
    try:
        return spark.table(FACT)
    except Exception as e:
        pytest.fail(f"Could not read {FACT}. {e}")


# --------------------------------------------------------------------- contract

def test_dimension_schema_matches_the_contract(dim):
    assertSchemaEqual(dim.schema, DIM_SCHEMA)


def test_fact_schema_matches_the_contract(fact):
    assertSchemaEqual(fact.schema, FACT_SCHEMA)


# ------------------------------------------------------------------- dimension

def test_dimension_keeps_every_version(dim, expected):
    assert dim.count() == expected["dim_rows"], (
        "The dimension must carry one row per customer *version*. Collapsing to the "
        "current row throws away the history the facts need."
    )


def test_surrogate_key_identifies_one_version(dim, expected):
    n = dim.select("customer_sk").distinct().count()
    assert n == expected["distinct_surrogate_keys"], (
        f"{n} distinct surrogate keys for {expected['dim_rows']} versions. A surrogate "
        "key must be unique per version - if it repeats, it is the natural key wearing "
        "a different name."
    )


def test_surrogate_key_is_not_the_natural_key(dim, expected):
    natural = dim.select("customer_id").distinct().count()
    assert natural == expected["customers"]
    assert expected["distinct_surrogate_keys"] > natural, (
        "customer_id alone cannot key this dimension: "
        f"{expected['customers']} customers hold {expected['dim_rows']} versions."
    )


def test_exactly_one_current_row_per_customer(dim, expected):
    bad = (dim.filter("is_current").groupBy("customer_id").count()
              .filter("count <> 1").count())
    assert bad == 0, f"{bad} customers have zero or several rows flagged is_current."


def test_validity_windows_do_not_overlap(spark, dim):
    dim.createOrReplaceTempView("_dim_check")
    overlaps = spark.sql("""
        SELECT count(*) AS n FROM _dim_check a JOIN _dim_check b
          ON a.customer_id = b.customer_id AND a.customer_sk <> b.customer_sk
         WHERE a.valid_from < b.valid_to AND b.valid_from < a.valid_to
    """).collect()[0]["n"]
    assert overlaps == 0, (
        f"{overlaps} overlapping version pairs. Overlapping windows let one order match "
        "two versions, which silently duplicates the fact."
    )


# ------------------------------------------------------------------------ fact

def test_fact_preserves_the_order_grain(fact, expected):
    assert fact.count() == expected["fact_rows"], (
        "The fact table must stay at one row per order. More rows means the join "
        "matched several dimension versions; fewer means orders were dropped."
    )


def test_every_order_is_present_exactly_once(spark, fact, expected):
    assert fact.select("order_id").distinct().count() == expected["source_orders"]
    missing = spark.table(ORDERS).select("order_id").subtract(fact.select("order_id")).count()
    assert missing == 0, f"{missing} orders from the source are absent from the fact table."


def test_no_order_lost_its_customer(fact):
    nulls = fact.filter("customer_sk IS NULL").count()
    assert nulls == 0, (
        f"{nulls} orders did not match any dimension version. Either the validity "
        "windows leave gaps, or the join condition excludes a boundary date."
    )


def test_fact_references_a_real_surrogate_key(fact, dim, expected):
    joined = fact.join(dim, on="customer_sk", how="inner").count()
    assert joined == expected["fact_rows"], (
        "Every customer_sk in the fact table must exist in the dimension exactly once."
    )


def test_each_fact_joins_to_the_version_valid_at_its_own_date(fact, dim):
    """The whole point of the section, expressed as a single assertion."""
    d = dim.select("customer_sk", F.col("customer_id").alias("d_customer_id"),
                   "valid_from", "valid_to")
    wrong = (fact.join(d, on="customer_sk", how="left")
             .filter(~((F.col("ordered_on") >= F.col("valid_from")) &
                       (F.col("ordered_on") < F.col("valid_to"))))
             .count())
    assert wrong == 0, (
        f"{wrong} orders are attached to a customer version that was not in effect on "
        "the order date. This is the failure that a current-version join produces: it "
        "returns an answer, and the answer is wrong."
    )


def test_attributes_come_from_the_joined_version(fact, dim):
    d = dim.select("customer_sk", F.col("segment").alias("d_segment"),
                   F.col("region").alias("d_region"))
    bad = (fact.join(d, on="customer_sk")
           .filter("segment_at_order <> d_segment OR region_at_order <> d_region")
           .count())
    assert bad == 0, (
        f"{bad} rows carry attributes that do not belong to the version their "
        "surrogate key points at."
    )


# ------------------------------------------------- known answers (the real check)

def test_revenue_by_segment_at_order(fact, expected):
    got = {r["segment_at_order"]: round(r["revenue"], 2) for r in
           fact.groupBy("segment_at_order")
               .agg(F.round(F.sum("amount"), 2).alias("revenue")).collect()}
    assert got == expected["revenue_by_segment_at_order"], (
        "Revenue per segment does not match.\n"
        f"  got:      {got}\n  expected: {expected['revenue_by_segment_at_order']}\n"
        "A current-version join lands close enough to look plausible - close is wrong."
    )


def test_order_counts_by_segment_at_order(fact, expected):
    got = {r["segment_at_order"]: r["n"] for r in
           fact.groupBy("segment_at_order").agg(F.count("*").alias("n")).collect()}
    assert got == expected["orders_by_segment_at_order"], got


def test_total_revenue_is_conserved(fact, expected):
    total = round(fact.agg(F.sum("amount")).collect()[0][0], 2)
    assert total == expected["total_revenue"], (
        f"Fact revenue {total} does not equal source revenue {expected['total_revenue']}. "
        "A join that changes the total has changed the grain."
    )


def test_probe_orders_carry_their_historical_attributes(fact, expected):
    probes = {p["order_id"]: p for p in expected["probe_orders"]}
    rows = {r["order_id"]: r for r in
            fact.filter(F.col("order_id").isin(list(probes))).collect()}
    for oid, p in probes.items():
        assert oid in rows, f"{oid} missing from the fact table"
        r = rows[oid]
        assert r["segment_at_order"] == p["segment_at_order"], (
            f"{oid} ({p['customer_id']}, ordered {p['ordered_on']}) should be "
            f"'{p['segment_at_order']}' - the segment at the time - but is "
            f"'{r['segment_at_order']}'. '{p['current_segment']}' is that customer's "
            "segment *today*, which is the answer a current-version join gives."
        )
        assert r["region_at_order"] == p["region_at_order"]


def test_result_actually_differs_from_the_naive_join(spark, fact, expected):
    """If this passes trivially, the fixtures no longer prove anything."""
    current = spark.table(VERSIONS).filter("is_current").select(
        "customer_id", F.col("segment").alias("current_segment"))
    differ = (fact.join(current, on="customer_id")
              .filter("segment_at_order <> current_segment").count())
    assert differ == expected["orders_misattributed_by_naive_join"], (
        f"{differ} orders differ from what the current-version join would say; the "
        f"reference measured {expected['orders_misattributed_by_naive_join']}."
    )
