# Databricks notebook source
# MAGIC %md
# MAGIC # PRO-S10 — Data Modeling assignment
# MAGIC
# MAGIC The task and the output contract are in the next cell (the same text as `README.md` in the repo).
# MAGIC
# MAGIC Produce:
# MAGIC - `workspace.de_prep.pro_s10_dim_customer` — one row per customer **version**
# MAGIC - `workspace.de_prep.pro_s10_fact_orders` — one row per order, joined to the
# MAGIC   version in effect on its own date

# COMMAND ----------

# MAGIC %md
# MAGIC <!-- task:begin  generated from README.md by tools/sync_assignment_tasks.py; edit the README, then re-run it -->
# MAGIC ## Assignment — `PRO-S10` Data Modeling
# MAGIC
# MAGIC **Objectives:** `PRO-S10-O1`, `O2`, `O3`, `O4`
# MAGIC
# MAGIC ### Before you start
# MAGIC
# MAGIC Work the lesson in `notebooks/lessons/professional/S10/`, and generate the data
# MAGIC (`databricks bundle run generate_datasets_pro_s10 -t free`).
# MAGIC
# MAGIC > **The lesson's dimension does not change. This one does.** In the lesson,
# MAGIC > `customer_id` identified a customer *and* a row, so a natural-key join was correct
# MAGIC > and a surrogate key would have been ceremony. Here 34 of 80 customers have more than
# MAGIC > one version, and joining on `customer_id` alone matches every one of them.
# MAGIC
# MAGIC ### The task
# MAGIC
# MAGIC Two tables:
# MAGIC
# MAGIC - `workspace.de_prep.pro_s10_assess_customer_versions` — a Type 2 dimension source.
# MAGIC   Each row is one *version* of a customer, valid over `[valid_from, valid_to)`.
# MAGIC - `workspace.de_prep.pro_s10_assess_orders` — 900 orders across 2026.
# MAGIC
# MAGIC Build a star schema: a customer dimension keyed so a row can be identified, and an
# MAGIC order fact joined to the customer as they were **on the order date**.
# MAGIC
# MAGIC The trap is that the wrong answer is not an error. A join on `customer_id` to the
# MAGIC current version returns 900 rows, no nulls, and a revenue-by-segment breakdown that
# MAGIC looks entirely reasonable — while attributing January's revenue to the segment the
# MAGIC customer was moved into in June.
# MAGIC
# MAGIC ### The output contract
# MAGIC
# MAGIC **`workspace.de_prep.pro_s10_dim_customer`** — one row per customer version.
# MAGIC
# MAGIC | Column | Type | Meaning |
# MAGIC |---|---|---|
# MAGIC | `customer_sk` | `STRING` | surrogate key — identifies **one version** |
# MAGIC | `customer_id` | `STRING` | natural key — identifies the customer |
# MAGIC | `segment` | `STRING` | |
# MAGIC | `region` | `STRING` | |
# MAGIC | `valid_from` | `DATE` | inclusive |
# MAGIC | `valid_to` | `DATE` | exclusive |
# MAGIC | `is_current` | `BOOLEAN` | |
# MAGIC
# MAGIC **`workspace.de_prep.pro_s10_fact_orders`** — one row per order.
# MAGIC
# MAGIC | Column | Type | Meaning |
# MAGIC |---|---|---|
# MAGIC | `order_id` | `STRING` | |
# MAGIC | `customer_sk` | `STRING` | the version in effect on `ordered_on` |
# MAGIC | `customer_id` | `STRING` | kept for convenience, not for joining |
# MAGIC | `segment_at_order` | `STRING` | from that version |
# MAGIC | `region_at_order` | `STRING` | from that version |
# MAGIC | `amount` | `DOUBLE` | |
# MAGIC | `ordered_on` | `DATE` | |
# MAGIC
# MAGIC #### Requirements
# MAGIC
# MAGIC 1. **The surrogate key identifies a version, not a customer.** 80 customers, 114
# MAGIC    versions, 114 distinct keys.
# MAGIC 2. **Make it deterministic.** Rebuilding the dimension must not renumber it, or every
# MAGIC    fact you have already published now points somewhere else. `monotonically_increasing_id()`
# MAGIC    fails this; a hash of the natural key plus `valid_from` does not.
# MAGIC 3. **Join as of the fact's own date.** Put the validity window in the join condition.
# MAGIC 4. **Preserve the grain.** 900 orders in, 900 rows out, no nulls, revenue unchanged.
# MAGIC    A row count that grows means the windows overlap; one that shrinks means a gap.
# MAGIC 5. **Mind the boundary.** `valid_from <= ordered_on < valid_to` — asymmetric, or an
# MAGIC    order placed on a changeover date matches two versions.
# MAGIC 6. Column order matters — the tests compare the whole schema.
# MAGIC
# MAGIC ### Grading
# MAGIC
# MAGIC ```bash
# MAGIC databricks bundle run grade_pro_s10 -t free
# MAGIC ```
# MAGIC
# MAGIC The tests are authoritative. The advisory AI review (`grading/rubrics/PRO-S10.yaml`)
# MAGIC judges whether the key is genuinely deterministic and whether you modelled the grain
# MAGIC deliberately — things a row count cannot see.
# MAGIC <!-- task:end -->

# COMMAND ----------

from pyspark.sql import functions as F

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")

versions = spark.table("pro_s10_assess_customer_versions")
orders = spark.table("pro_s10_assess_orders")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Look before you model
# MAGIC
# MAGIC How many customers, how many versions? The gap between those two numbers is the
# MAGIC whole assignment.

# COMMAND ----------

# TODO: your investigation


# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. The dimension
# MAGIC
# MAGIC Add a surrogate key that identifies one version and survives a rebuild.

# COMMAND ----------

# TODO
# dim.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable("pro_s10_dim_customer")


# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. The fact
# MAGIC
# MAGIC Join each order to the version valid on `ordered_on`. Check the row count before
# MAGIC you write - a join that changes the grain is the failure this section is about.

# COMMAND ----------

# TODO
# fact.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable("pro_s10_fact_orders")


# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Convince yourself
# MAGIC
# MAGIC Compare your revenue-by-segment against the same query run through a
# MAGIC current-version join. If the two agree, one of them is not doing what you think.

# COMMAND ----------

# TODO
