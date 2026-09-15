# Databricks notebook source
# MAGIC %md
# MAGIC # PRO-S5 assignment — your work goes here
# MAGIC
# MAGIC The task and the output contract are in the next cell (the same text as `README.md` in the repo).
# MAGIC
# MAGIC **The lesson's fixed threshold cannot work here, and you can prove it: no single number separates weekends from degraded weekdays.**
# MAGIC
# MAGIC When you are done, go back to the study app and press **Grade my assignment**.
# MAGIC Each failing check says what it expected and why.

# COMMAND ----------

# MAGIC %md
# MAGIC <!-- task:begin  generated from README.md by tools/sync_assignment_tasks.py; edit the README, then re-run it -->
# MAGIC ## Assignment — `PRO-S5` Monitoring and Alerting
# MAGIC
# MAGIC **Objectives:** `PRO-S5-O1`, `O2`, `O5`, `O6`
# MAGIC
# MAGIC ### Before you start
# MAGIC
# MAGIC Work the two lessons in `notebooks/lessons/professional/S5/`, and generate the data
# MAGIC (the study app generates the data the first time you open this section; `databricks bundle run generate_datasets_pro_s5 -t free` does the same from a terminal).
# MAGIC
# MAGIC > **The lesson's fixed threshold cannot work here, and you can prove it.** The
# MAGIC > weekend range and the degraded weekday range do not overlap the way a single number
# MAGIC > could separate them: any threshold above the weekend maximum fires every weekend,
# MAGIC > and any threshold below the weekend minimum never fires at all.
# MAGIC
# MAGIC ### The task
# MAGIC
# MAGIC `workspace.de_prep.pro_s5_assess_metrics` holds 90 days of daily pipeline metrics.
# MAGIC Somewhere in there a gradual degradation begins. There is also one day of legitimately
# MAGIC high volume — a campaign — which must **not** alert.
# MAGIC
# MAGIC Design an alert and evaluate it against the whole history.
# MAGIC
# MAGIC ### The output contract
# MAGIC
# MAGIC **`workspace.de_prep.pro_s5_alert_evaluation`** — one row per evaluated day.
# MAGIC
# MAGIC | Column | Type | Meaning |
# MAGIC |---|---|---|
# MAGIC | `run_date` | `DATE` | |
# MAGIC | `day_type` | `STRING` | `weekday` or `weekend` |
# MAGIC | `rows_processed` | `INT` | the observed metric |
# MAGIC | `baseline` | `DOUBLE` | what you expected for this day |
# MAGIC | `pct_of_baseline` | `DOUBLE` | observed as a percentage of baseline |
# MAGIC | `should_alert` | `BOOLEAN` | whether your alert fires |
# MAGIC
# MAGIC Days without enough history to form a baseline are excluded.
# MAGIC
# MAGIC #### Requirements
# MAGIC
# MAGIC 1. **The baseline must respect the weekly cycle.** Comparing a Saturday to a Friday is
# MAGIC    comparing a weekend to a weekday.
# MAGIC 2. **No alerts before the degradation begins.** A single false positive in the healthy
# MAGIC    period fails this — an alert that cries wolf is worse than none.
# MAGIC 3. **The campaign spike must not alert.** Alert on direction, not on deviation.
# MAGIC 4. **The degradation must be detected**, and reasonably promptly once it is
# MAGIC    established.
# MAGIC 5. Column order matters — the tests compare the whole schema.
# MAGIC
# MAGIC ### Grading
# MAGIC
# MAGIC ```bash
# MAGIC databricks bundle run grade_pro_s5 -t free --profile FREE
# MAGIC ```
# MAGIC
# MAGIC ### Hints
# MAGIC
# MAGIC <details><summary>How do I build a seasonal baseline?</summary>
# MAGIC
# MAGIC Partition by day of week, then average the previous few occurrences of that same
# MAGIC weekday. Offset the window so today does not contribute to its own baseline.
# MAGIC </details>
# MAGIC
# MAGIC <details><summary>My alert fires every weekend</summary>
# MAGIC
# MAGIC Requirement 1. The baseline is comparing across day types.
# MAGIC </details>
# MAGIC
# MAGIC <details><summary>My alert fires on the campaign day</summary>
# MAGIC
# MAGIC Requirement 3. That day is *above* baseline. Alert on drops.
# MAGIC </details>
# MAGIC
# MAGIC <details><summary>I get scattered single-day alerts</summary>
# MAGIC
# MAGIC Require persistence — several consecutive low days. You trade a day of detection
# MAGIC latency for an alert people believe.
# MAGIC </details>
# MAGIC <!-- task:end -->

# COMMAND ----------

from pyspark.sql import Window
from pyspark.sql import functions as F

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")
SOURCE = "pro_s5_assess_metrics"
TARGET = "pro_s5_alert_evaluation"
metrics = spark.table(SOURCE).orderBy("run_date")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 0 — look at the series
# MAGIC
# MAGIC Plot or list `rows_processed` by date. Where is the weekly cycle, where is the campaign, where does the degradation start?

# COMMAND ----------

# display(metrics)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1 — day_type
# MAGIC
# MAGIC `weekday` or `weekend`. Requirement 1: baselines compare like with like.

# COMMAND ----------

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2 — a baseline from prior history of the same day type
# MAGIC
# MAGIC Only earlier days count (no peeking), and days without enough history are excluded.

# COMMAND ----------

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3 — pct_of_baseline and the alert rule
# MAGIC
# MAGIC Requirement 3: alert on direction, not deviation, so the campaign spike stays quiet. Requirement 2: nothing fires in the healthy period; Requirement 4: the degradation is caught reasonably promptly.

# COMMAND ----------

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 4 — write the evaluation
# MAGIC
# MAGIC One row per evaluated day, contracted column order.

# COMMAND ----------

# COMMAND ----------

# MAGIC %md
# MAGIC ## Check yourself before grading

# COMMAND ----------

