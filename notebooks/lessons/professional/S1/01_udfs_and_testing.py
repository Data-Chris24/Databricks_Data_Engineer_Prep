# Databricks notebook source
# MAGIC %md
# MAGIC # UDFs and testing — `PRO-S1-O3`, `PRO-S1-O11`
# MAGIC
# MAGIC Teach data: `pro_s1_teach_accounts`, a snapshot.

# COMMAND ----------

from pyspark.sql import functions as F
from pyspark.sql.types import StringType
import pandas as pd

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")
accounts = spark.table("pro_s1_teach_accounts")
print("rows:", accounts.count())

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Prefer built-ins; reach for a UDF only when you must
# MAGIC
# MAGIC A built-in runs inside the JVM and the optimiser can see through it. A Python UDF
# MAGIC serialises every row out to a Python process and back, and is opaque to the
# MAGIC optimiser. Same result, very different cost.

# COMMAND ----------

# The built-in way - almost always the right answer.
builtin = accounts.withColumn(
    "band", F.when(F.col("balance") >= 3000, "high")
             .when(F.col("balance") >= 1000, "medium")
             .otherwise("low"))
display(builtin.groupBy("band").count().orderBy("band"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. A scalar Python UDF
# MAGIC
# MAGIC Row-at-a-time. Correct, simple, and the slowest option.

# COMMAND ----------

@F.udf(returnType=StringType())
def band_scalar(balance):
    if balance is None:
        return None
    if balance >= 3000:
        return "high"
    return "medium" if balance >= 1000 else "low"

display(accounts.withColumn("band", band_scalar("balance"))
        .groupBy("band").count().orderBy("band"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. A pandas UDF
# MAGIC
# MAGIC Vectorised: Spark hands over a whole batch as a pandas Series via Arrow, so the
# MAGIC per-row serialisation cost is amortised. This is the one to reach for when a UDF
# MAGIC is genuinely needed.

# COMMAND ----------

@F.pandas_udf(StringType())
def band_pandas(balance: pd.Series) -> pd.Series:
    return pd.cut(
        balance.fillna(-1),
        bins=[-2, 999.99, 2999.99, float("inf")],
        labels=["low", "medium", "high"],
    ).astype(str)

display(accounts.withColumn("band", band_pandas("balance"))
        .groupBy("band").count().orderBy("band"))

# COMMAND ----------

# MAGIC %md
# MAGIC | | Runs | Optimiser sees it | Use when |
# MAGIC |---|---|---|---|
# MAGIC | Built-in | JVM | yes | almost always |
# MAGIC | pandas UDF | Python, vectorised | no | a UDF is needed and volume matters |
# MAGIC | Python UDF | Python, row at a time | no | logic that will not vectorise |

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Testing transformations — `PRO-S1-O11`
# MAGIC
# MAGIC `DataFrame.transform` lets a transformation be a named function, which is what
# MAGIC makes it testable in isolation.

# COMMAND ----------

def add_band(df):
    return df.withColumn(
        "band", F.when(F.col("balance") >= 3000, "high")
                 .when(F.col("balance") >= 1000, "medium")
                 .otherwise("low"))

banded = accounts.transform(add_band)
print("transform applied:", "band" in banded.columns)

# COMMAND ----------

# MAGIC %md
# MAGIC ### `assertSchemaEqual` and `assertDataFrameEqual`
# MAGIC
# MAGIC Test against a tiny hand-built DataFrame, not against production data — a test
# MAGIC whose expected values come from the same pipeline it is testing proves nothing.

# COMMAND ----------

from pyspark.testing import assertDataFrameEqual, assertSchemaEqual

fixture = spark.createDataFrame(
    [("A", "gold", 5000.0), ("B", "silver", 1500.0), ("C", "bronze", 10.0)],
    "account_id STRING, tier STRING, balance DOUBLE")

expected = spark.createDataFrame(
    [("A", "gold", 5000.0, "high"),
     ("B", "silver", 1500.0, "medium"),
     ("C", "bronze", 10.0, "low")],
    "account_id STRING, tier STRING, balance DOUBLE, band STRING")

assertDataFrameEqual(fixture.transform(add_band), expected)
print("assertDataFrameEqual passed")

assertSchemaEqual(fixture.transform(add_band).schema, expected.schema)
print("assertSchemaEqual passed")

# COMMAND ----------

# MAGIC %md
# MAGIC ### A failing assertion is the useful one

# COMMAND ----------

wrong = expected.withColumn("band", F.lit("high"))
try:
    assertDataFrameEqual(fixture.transform(add_band), wrong)
    print("UNEXPECTED: mismatched frames compared equal")
except Exception as e:
    print(f"caught {type(e).__name__} - the assertion reports which rows differ,")
    print("which is why it beats comparing counts")

# COMMAND ----------

# MAGIC %md
# MAGIC ## What to carry forward
# MAGIC
# MAGIC - Built-in > pandas UDF > Python UDF, in that order of preference.
# MAGIC - `DataFrame.transform` makes a transformation a testable unit.
# MAGIC - `assertDataFrameEqual` compares content and reports the difference;
# MAGIC   `assertSchemaEqual` compares structure including column order.
# MAGIC - Expected values come from a fixture you wrote, never from the pipeline.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Next
# MAGIC
# MAGIC Continue with the next lesson notebook: [02_pipelines_and_cdc](./02_pipelines_and_cdc).
# MAGIC
# MAGIC When the lessons are done, open the graded assignment: [PRO-S1 assignment notebook](../../../assignments/PRO-S1/assignment) · [the task](../../../assignments/PRO-S1/README.md).
