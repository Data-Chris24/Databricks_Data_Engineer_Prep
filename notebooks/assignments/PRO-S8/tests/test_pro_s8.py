"""Graded tests for the PRO-S8 assignment. Authoritative.

Two things are checked: that the report says where each privilege actually lives,
and that it distinguishes a privilege held from a privilege usable.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    BooleanType, IntegerType, StringType, StructField, StructType,
)
from pyspark.testing import assertSchemaEqual

REPORT = "workspace.de_prep.pro_s8_access_report"
DOCS = "workspace.de_prep.pro_s8_documentation"

REPORT_SCHEMA = StructType([
    StructField("principal", StringType(), True),
    StructField("table_schema", StringType(), True),
    StructField("table_name", StringType(), True),
    StructField("privilege", StringType(), True),
    StructField("granted_at_level", StringType(), True),
    StructField("has_use_catalog", BooleanType(), True),
    StructField("has_use_schema", BooleanType(), True),
    StructField("is_effective", BooleanType(), True),
])

DOCS_SCHEMA = StructType([
    StructField("table_schema", StringType(), True),
    StructField("table_name", StringType(), True),
    StructField("has_table_comment", BooleanType(), True),
    StructField("column_count", IntegerType(), True),
    StructField("documented_columns", IntegerType(), True),
    StructField("tag_count", IntegerType(), True),
    StructField("has_pii_column", BooleanType(), True),
    StructField("is_documented", BooleanType(), True),
])


def _fixtures() -> dict:
    env = os.environ.get("PRO_S8_FIXTURES")
    if env and Path(env).exists():
        return json.loads(Path(env).read_text())
    for parent in Path(__file__).resolve().parents:
        c = parent / "solutions" / "PRO-S8" / "expected.json"
        if c.exists():
            return json.loads(c.read_text())
    pytest.fail("expected.json not found; set PRO_S8_FIXTURES")


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
def report(spark):
    try:
        return spark.table(REPORT)
    except Exception as e:
        pytest.fail(f"Could not read {REPORT}. {e}")


@pytest.fixture(scope="session")
def docs(spark):
    try:
        return spark.table(DOCS)
    except Exception as e:
        pytest.fail(f"Could not read {DOCS}. {e}")


# --------------------------------------------------------------------- contract

def test_report_schema_matches_the_contract(report):
    assertSchemaEqual(report.schema, REPORT_SCHEMA)


def test_documentation_schema_matches_the_contract(docs):
    assertSchemaEqual(docs.schema, DOCS_SCHEMA)


# --------------------------------------------------------- the grants were found

def test_report_covers_every_privilege(report, expected):
    assert report.count() == expected["report_rows"], (
        "One row per (principal, table, privilege) that applies - inherited ones "
        "included. Inheritance means a grant on the catalog applies to every table "
        "under it, whether or not that table existed when the grant was made."
    )


def test_rows_per_principal(report, expected):
    got = _counts(report, "principal")
    assert got == expected["rows_by_principal"], (
        f"got {got}, expected {expected['rows_by_principal']}"
    )


def test_principals_are_named_not_ids(report):
    ids = report.filter(F.col("principal").rlike("^[0-9a-f-]{36}$")).count()
    assert ids == 0, (
        f"{ids} rows identify the principal by application id. The contract asks for "
        "the display name - an access report nobody can read is not an access report."
    )


# ------------------------------------------------------ where the grant really is

def test_grant_level_is_resolved(report, expected):
    got = _counts(report, "granted_at_level")
    assert got == expected["rows_by_level"], (
        f"Levels do not match.\n  got:      {got}\n  expected: {expected['rows_by_level']}\n"
        "Only one of these privileges is granted on a table. The rest are inherited "
        "from the schema or the catalog, and `information_schema.table_privileges` "
        "carries that in `inherited_from` - a column the obvious SELECT leaves out."
    )


def test_levels_are_from_the_allowed_set(report):
    bad = report.filter(~F.col("granted_at_level").isin("TABLE", "SCHEMA", "CATALOG"))
    n = bad.count()
    assert n == 0, (
        f"{n} rows carry a level outside TABLE/SCHEMA/CATALOG"
        + (f" (e.g. {bad.first()['granted_at_level']!r} - `inherited_from` says NONE "
           "for a grant that really is on the table; the report wants 'TABLE')" if n else "")
    )


# ------------------------------------------- held versus usable (the real check)

def test_traversal_is_computed(report, expected):
    got = _counts(report.filter("is_effective"), "principal")
    assert got == expected["effective_by_principal"], (
        f"Effective privileges per principal do not match.\n  got:      {got}\n"
        f"  expected: {expected['effective_by_principal']}\n"
        "A SELECT is inert without USE CATALOG on the catalog and USE SCHEMA on the "
        "schema. Note how information_schema spells those two."
    )


def test_the_inert_privileges_are_identified(report, expected):
    n = report.filter("NOT is_effective").count()
    assert n == expected["ineffective_rows"], (
        f"{n} rows are marked unusable; expected {expected['ineffective_rows']}. "
        "One principal holds SELECT across the whole catalog and can reach none of it."
    )


def test_is_effective_is_the_conjunction(report):
    wrong = report.filter(
        F.col("is_effective") != (F.col("has_use_catalog") & F.col("has_use_schema"))
    ).count()
    assert wrong == 0, (
        f"{wrong} rows where is_effective disagrees with the traversal columns beside it."
    )


def test_report_matches_row_for_row(report, expected):
    got = sorted([[r["principal"], r["table_schema"], r["table_name"], r["privilege"],
                   r["granted_at_level"], r["has_use_catalog"], r["has_use_schema"],
                   r["is_effective"]] for r in report.collect()])
    exp = sorted(expected["report"])
    assert got == exp, (
        "The report differs from the reference. First difference:\n"
        + next((f"  got:      {g}\n  expected: {e}"
                for g, e in zip(got, exp) if g != e),
               f"  row counts differ: {len(got)} vs {len(exp)}")
    )


# ------------------------------------------------------------- documentation half

def test_documentation_covers_every_table(docs, expected):
    assert docs.count() == expected["doc_rows"]


def test_pii_columns_are_found(docs, expected):
    got = sorted(r["table_name"] for r in docs.filter("has_pii_column").collect())
    assert got == expected["pii_tables"], (
        f"got {got}, expected {expected['pii_tables']}. PII is recorded as a column "
        "tag, so `column_tags` is where this lives - not `table_tags`."
    )


def test_documented_is_not_just_has_a_comment(docs, expected):
    documented = docs.filter("is_documented").count()
    commented = docs.filter("has_table_comment").count()
    assert commented == expected["with_table_comment"]
    assert documented == expected["documented"], (
        f"{documented} tables marked documented; expected {expected['documented']}. "
        "One table records its purpose in a tag rather than a comment, so counting "
        "`tables.comment` alone under-reports."
    )
    assert documented != commented, (
        "is_documented and has_table_comment agree exactly, which means the definition "
        "in the README was not applied."
    )


def test_documentation_matches_row_for_row(docs, expected):
    got = sorted([[r["table_schema"], r["table_name"], r["has_table_comment"],
                   r["column_count"], r["documented_columns"], r["tag_count"],
                   r["has_pii_column"], r["is_documented"]] for r in docs.collect()])
    assert got == sorted(expected["documentation"])
