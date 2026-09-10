# Databricks notebook source
# MAGIC %md
# MAGIC # PRO-S10 — Data Modeling assignment
# MAGIC
# MAGIC Read `README.md` first. The contract there is what the tests check.
# MAGIC
# MAGIC Produce:
# MAGIC - `workspace.de_prep.pro_s10_dim_customer` — one row per customer **version**
# MAGIC - `workspace.de_prep.pro_s10_fact_orders` — one row per order, joined to the
# MAGIC   version in effect on its own date

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
