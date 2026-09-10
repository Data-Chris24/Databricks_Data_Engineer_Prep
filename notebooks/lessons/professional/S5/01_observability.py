# Databricks notebook source
# MAGIC %md
# MAGIC # Observability sources — `PRO-S5-O1`, `PRO-S5-O2`, `PRO-S5-O3`, `PRO-S5-O4`

# COMMAND ----------

from pyspark.sql import functions as F

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Where the signals live
# MAGIC
# MAGIC | Source | Answers | Reach it with |
# MAGIC |---|---|---|
# MAGIC | System tables | cost, usage, audit, lineage | SQL on `system.*` |
# MAGIC | Job run history | which task, how long, how often it fails | Jobs UI, REST API, CLI |
# MAGIC | `DESCRIBE HISTORY` | what a table did and when | SQL |
# MAGIC | Query profile | where time and bytes went in one query | SQL editor |
# MAGIC | Pipeline event log | pipeline-level state and expectations | SQL on the event log table |
# MAGIC
# MAGIC Availability varies by tier, so check rather than assume.

# COMMAND ----------

for t in ["system.information_schema.tables",
          "system.access.audit",
          "system.billing.usage",
          "system.query.history"]:
    try:
        spark.sql(f"SELECT 1 FROM {t} LIMIT 1").collect()
        print(f"{t:42} available")
    except Exception as e:
        print(f"{t:42} not available here ({type(e).__name__})")

# COMMAND ----------

# MAGIC %md
# MAGIC > On Free Edition most `system.*` schemas are absent. The queries below are the
# MAGIC > shape you would write; the exam asks which table answers which question, not
# MAGIC > whether your workspace exposes it.
# MAGIC
# MAGIC ```sql
# MAGIC -- what is this costing, by SKU, this month
# MAGIC SELECT sku_name, sum(usage_quantity) AS dbus
# MAGIC FROM system.billing.usage
# MAGIC WHERE usage_date >= date_trunc('month', current_date())
# MAGIC GROUP BY sku_name ORDER BY dbus DESC;
# MAGIC
# MAGIC -- who read this table in the last week
# MAGIC SELECT user_identity.email, count(*) AS reads
# MAGIC FROM system.access.audit
# MAGIC WHERE action_name = 'getTable' AND event_date >= current_date() - 7
# MAGIC GROUP BY 1 ORDER BY reads DESC;
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. A table's own history is always available

# COMMAND ----------

display(spark.sql("DESCRIBE HISTORY pro_s5_teach_metrics").select(
    "version", "timestamp", "operation",
    F.col("operationMetrics")["numOutputRows"].alias("rows_written")))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Job state via the CLI and API — `PRO-S5-O3`
# MAGIC
# MAGIC ```bash
# MAGIC databricks jobs list-runs --job-id <id> --limit 25
# MAGIC databricks jobs get-run <run-id>
# MAGIC databricks jobs get-run-output <task-run-id>
# MAGIC ```
# MAGIC
# MAGIC The API is how you build monitoring that outlives a person watching a dashboard —
# MAGIC run durations pulled on a schedule become a trend you can alert on.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Alerting on a stable metric — `PRO-S5-O5`, `PRO-S5-O6`
# MAGIC
# MAGIC The teach metric sits near 1000 every day. A fixed threshold is honest here:
# MAGIC pick a floor, alert below it.

# COMMAND ----------

m = spark.table("pro_s5_teach_metrics")
stats = m.agg(F.min("rows_processed").alias("min"),
              F.max("rows_processed").alias("max"),
              F.round(F.avg("rows_processed"), 1).alias("mean"),
              F.round(F.stddev("rows_processed"), 1).alias("stddev")).collect()[0]
print(f"min {stats['min']}, max {stats['max']}, mean {stats['mean']}, stddev {stats['stddev']}")

THRESHOLD = int(stats["mean"] - 3 * stats["stddev"])
print(f"\nthreshold at mean - 3 stddev = {THRESHOLD}")
print("breaches:", m.filter(F.col("rows_processed") < THRESHOLD).count())

# COMMAND ----------

# MAGIC %md
# MAGIC ```sql
# MAGIC -- the query behind a SQL Alert
# MAGIC SELECT count(*) AS breaches
# MAGIC FROM pro_s5_teach_metrics
# MAGIC WHERE run_date = current_date() AND rows_processed < 880;
# MAGIC ```
# MAGIC
# MAGIC Set the alert to fire when `breaches > 0`, and notify a channel rather than a
# MAGIC person — people go on holiday.

# COMMAND ----------

# MAGIC %md
# MAGIC ## What to carry forward
# MAGIC
# MAGIC - Know which source answers which question; that is what the exam tests.
# MAGIC - `DESCRIBE HISTORY` works everywhere, whatever your tier exposes.
# MAGIC - A fixed threshold is honest **only when the metric is stationary**.
# MAGIC
# MAGIC The assignment's metric has a weekly cycle and a degradation that hides inside
# MAGIC normal range. A fixed threshold there either fires every weekend or never fires
# MAGIC at all.
