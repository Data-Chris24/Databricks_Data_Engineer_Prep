# Databricks notebook source
# MAGIC %md
# MAGIC # Anti-transplant check — PRO-S5
# MAGIC
# MAGIC Applies the **lesson's** fixed threshold to the seasonal metric and asserts the
# MAGIC graded suite FAILS.
# MAGIC
# MAGIC The lesson computed `mean - 3 * stddev` on a stationary metric, which was honest
# MAGIC there. Here it cannot separate the incident from a normal weekend, and this
# MAGIC notebook shows that both ways round.

# COMMAND ----------

from pyspark.sql import functions as F

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")
T = "pro_s5_alert_evaluation"

if spark.catalog.tableExists(T):
    spark.sql(f"CREATE OR REPLACE TABLE {T}_backup AS SELECT * FROM {T}")
    print("backed up the correct evaluation")

# COMMAND ----------

# MAGIC %md
# MAGIC ## The lesson's approach, verbatim

# COMMAND ----------

m = spark.table("pro_s5_assess_metrics")
stats = m.agg(F.avg("rows_processed").alias("mean"),
              F.stddev("rows_processed").alias("sd")).collect()[0]
threshold = stats["mean"] - 3 * stats["sd"]
print(f"mean {stats['mean']:.0f}, stddev {stats['sd']:.0f} -> threshold {threshold:.0f}")

wk_max = m.filter("day_type='weekend'").agg(F.max("rows_processed")).collect()[0][0]
wk_min = m.filter("day_type='weekend'").agg(F.min("rows_processed")).collect()[0][0]
print(f"weekend range {wk_min} - {wk_max}")
print()
if threshold < wk_min:
    print("threshold sits BELOW the weekend floor: it will never fire, degradation or not")
elif threshold > wk_max:
    print("threshold sits ABOVE the weekend ceiling: it fires every single weekend")
else:
    print("threshold sits inside the weekend range: it fires on some weekends and not others")

# COMMAND ----------

naive = (m
    .withColumn("baseline", F.lit(float(stats["mean"])))
    .withColumn("pct_of_baseline",
                F.round(100.0 * F.col("rows_processed") / F.lit(float(stats["mean"])), 1))
    .withColumn("should_alert", F.col("rows_processed") < F.lit(float(threshold)))
    .select("run_date", "day_type", "rows_processed", "baseline",
            "pct_of_baseline", "should_alert"))

naive.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(T)
print(f"\nfixed-threshold evaluation: {spark.table(T).filter('should_alert').count()} alert days")

# COMMAND ----------

# MAGIC %pip install pytest -q
# MAGIC %restart_python

# COMMAND ----------

import io, contextlib, os, shutil, tempfile
import pytest

ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
repo_root = ("/Workspace" + os.path.dirname(ctx.notebookPath().get())).split("/files/")[0] + "/files"
workdir = tempfile.mkdtemp(prefix="transplant_pro_s5_")
shutil.copytree(os.path.join(repo_root, "notebooks", "assignments", "PRO-S5", "tests"),
                os.path.join(workdir, "tests"))
fx = os.path.join(workdir, "expected.json")
shutil.copyfile(os.path.join(repo_root, "solutions", "PRO-S5", "expected.json"), fx)
os.environ["PRO_S5_FIXTURES"] = fx

buf = io.StringIO()
with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
    code = pytest.main([os.path.join(workdir, "tests"), "-q", "--tb=line",
                        "-p", "no:cacheprovider"])
print(buf.getvalue()[-2500:])

# COMMAND ----------

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")
T = "pro_s5_alert_evaluation"
if spark.catalog.tableExists(f"{T}_backup"):
    spark.sql(f"CREATE OR REPLACE TABLE {T} AS SELECT * FROM {T}_backup")
    spark.sql(f"DROP TABLE {T}_backup")
    print("restored the correct evaluation")

if code == 0:
    raise RuntimeError(
        "DESIGN REGRESSION: a fixed threshold PASSED the assignment. Redesign the "
        "pairing before shipping this section."
    )
print(f"anti-transplant property holds - the lesson's approach fails (pytest exit {code})")
