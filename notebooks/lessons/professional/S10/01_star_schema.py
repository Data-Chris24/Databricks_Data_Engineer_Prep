# Databricks notebook source
# MAGIC %md
# MAGIC # Dimensional modelling — `PRO-S10-O1`, `PRO-S10-O4`
# MAGIC
# MAGIC Teach data: a static customer dimension and a sales fact.

# COMMAND ----------

from pyspark.sql import functions as F

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")
customers = spark.table("pro_s10_teach_customers")
sales = spark.table("pro_s10_teach_sales")
print(f"{customers.count()} customers, {sales.count()} sales")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Facts and dimensions
# MAGIC
# MAGIC | | Holds | Grain | Grows |
# MAGIC |---|---|---|---|
# MAGIC | **Fact** | measurements and foreign keys | one row per event | continuously |
# MAGIC | **Dimension** | descriptive attributes | one row per entity | slowly |
# MAGIC
# MAGIC The fact's grain is the single most important decision in the model — state it in
# MAGIC words before writing any code. "One row per sale" is a grain; "sales data" is not.

# COMMAND ----------

star = (sales.join(customers, on="customer_id", how="left")
        .select("sale_id", "customer_id", "segment", "region", "amount", "sold_on"))

print("fact rows in :", sales.count())
print("fact rows out:", star.count(), " <- a dimension join must not change the grain")

# COMMAND ----------

display(star.groupBy("segment")
        .agg(F.count("*").alias("sales"), F.round(F.sum("amount"), 2).alias("revenue"))
        .orderBy("segment"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Natural keys and surrogate keys
# MAGIC
# MAGIC | | |
# MAGIC |---|---|
# MAGIC | **Natural key** | the business identifier — `customer_id` |
# MAGIC | **Surrogate key** | a model-generated key identifying **one version** of a row |
# MAGIC
# MAGIC When a dimension is static, the natural key is enough: there is only one version
# MAGIC of each customer, so `customer_id` identifies it unambiguously. Joining on it is
# MAGIC correct, and adding a surrogate key would be ceremony.
# MAGIC
# MAGIC **That stops being true the moment an attribute changes.**

# COMMAND ----------

per_customer = customers.groupBy("customer_id").count()
print("customers with more than one row:", per_customer.filter("count > 1").count())
print("so the natural key uniquely identifies a customer here")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Star vs snowflake
# MAGIC
# MAGIC A **star** keeps dimension attributes denormalised in one table — fewer joins,
# MAGIC some redundancy. A **snowflake** normalises them into sub-dimensions — less
# MAGIC redundancy, more joins.
# MAGIC
# MAGIC Star is the default for analytics. Storage is cheap; a query that needs four
# MAGIC joins to answer "revenue by region" is not.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Layout — `PRO-S10-O2`, `PRO-S10-O3`
# MAGIC
# MAGIC Cluster a fact table on what it is filtered by, usually the date and the
# MAGIC highest-traffic dimension key.

# COMMAND ----------

star.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable("pro_s10_teach_fact_sales")
spark.sql("ALTER TABLE pro_s10_teach_fact_sales CLUSTER BY (sold_on, segment)")
display(spark.sql("DESCRIBE DETAIL pro_s10_teach_fact_sales")
        .select("numFiles", "clusteringColumns"))

# COMMAND ----------

# MAGIC %md
# MAGIC Liquid clustering over partitioning, for the reason that decides most of these:
# MAGIC **clustering keys can be changed later; a partition column cannot** without
# MAGIC rewriting the table. On a fact table that grows for years, that difference
# MAGIC compounds.

# COMMAND ----------

# MAGIC %md
# MAGIC ## What to carry forward
# MAGIC
# MAGIC - State the fact's grain in words first.
# MAGIC - A dimension join must not change the fact's row count.
# MAGIC - A natural key suffices **only while the dimension is static**.
# MAGIC - Star by default; cluster the fact on what filters it.
# MAGIC
# MAGIC The assignment's dimension changes over time, and joining on the natural key
# MAGIC there produces a plausible, wrong answer.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Next
# MAGIC
# MAGIC Continue with the next lesson notebook: [02_liquid_clustering](./02_liquid_clustering).
# MAGIC
# MAGIC When the lessons are done, open the graded assignment: [PRO-S10 assignment notebook](../../../assignments/PRO-S10/assignment) · [the task](../../../assignments/PRO-S10/README.md).
