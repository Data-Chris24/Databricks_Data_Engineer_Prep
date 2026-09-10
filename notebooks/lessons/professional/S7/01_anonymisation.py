# Databricks notebook source
# MAGIC %md
# MAGIC # Anonymisation techniques — `PRO-S7-O3`
# MAGIC
# MAGIC Teach data: `pro_s7_teach_subjects`, where the PII sits in columns you can name.

# COMMAND ----------

from pyspark.sql import functions as F

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")
subjects = spark.table("pro_s7_teach_subjects")
print("rows:", subjects.count())
display(subjects.limit(3))

# COMMAND ----------

# MAGIC %md
# MAGIC ## The four techniques, and what each costs you
# MAGIC
# MAGIC | Technique | Reversible? | Keeps joinability | Keeps analytics |
# MAGIC |---|---|---|---|
# MAGIC | **Hashing** | no | yes — same input, same hash | grouping only |
# MAGIC | **Tokenisation** | yes, with the vault | yes | grouping only |
# MAGIC | **Suppression** | no | no | nothing |
# MAGIC | **Generalisation** | no | no | aggregate patterns survive |
# MAGIC
# MAGIC Choose by what the data still has to do. Hashing an id keeps joins working;
# MAGIC suppressing it does not.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Hashing — irreversible, still joinable

# COMMAND ----------

hashed = subjects.withColumn("email_hash", F.sha2(F.col("email"), 256))
display(hashed.select("subject_id", "email", "email_hash").limit(3))

same = hashed.select("email_hash").distinct().count()
print(f"{same} distinct hashes from {subjects.count()} rows - deterministic, so joins survive")

# COMMAND ----------

# MAGIC %md
# MAGIC **Hashing alone is not anonymisation when the input space is small.** An email
# MAGIC address is high-entropy, but a hashed postcode or date of birth can be brute
# MAGIC forced by hashing every possible value. Salt those, and keep the salt somewhere
# MAGIC the data does not live.

# COMMAND ----------

SALT = "per-dataset-salt-kept-in-a-secret-scope"
salted = subjects.withColumn("email_hash_salted", F.sha2(F.concat(F.lit(SALT), F.col("email")), 256))
display(salted.select("email", "email_hash_salted").limit(2))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Suppression — the value is gone

# COMMAND ----------

suppressed = subjects.withColumn("phone", F.lit(None).cast("string"))
print("phones remaining:", suppressed.filter(F.col("phone").isNotNull()).count())

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Generalisation — precision traded for privacy
# MAGIC
# MAGIC A birth date becomes a decade; a postcode becomes a region. Individual identity
# MAGIC weakens while aggregate patterns survive.

# COMMAND ----------

generalised = (subjects
    .withColumn("created_month", F.date_format("created_on", "yyyy-MM"))
    .withColumn("email_domain", F.regexp_extract("email", "@(.+)$", 1))
    .drop("email", "created_on"))
display(generalised.groupBy("created_month").count().orderBy("created_month").limit(5))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. A masked pipeline over known columns
# MAGIC
# MAGIC The whole job, when you know where the PII is.

# COMMAND ----------

deidentified = (subjects
    .withColumn("subject_hash", F.sha2(F.concat(F.lit(SALT), F.col("subject_id")), 256))
    .withColumn("email_domain", F.regexp_extract("email", "@(.+)$", 1))
    .withColumn("created_month", F.date_format("created_on", "yyyy-MM"))
    .select("subject_hash", "email_domain", "created_month"))

deidentified.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable("pro_s7_teach_deidentified")
display(spark.table("pro_s7_teach_deidentified").limit(5))

# COMMAND ----------

# MAGIC %md
# MAGIC ## What to carry forward
# MAGIC
# MAGIC - Choose the technique by what the data still has to do.
# MAGIC - Salt hashes of low-entropy values; keep the salt out of the dataset.
# MAGIC - Suppression removes; generalisation reduces precision.
# MAGIC
# MAGIC **All of this assumes you know which columns hold PII.** The assignment's source
# MAGIC has email addresses and phone numbers inside a free-text field, where a
# MAGIC column-by-column approach will not find them.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Next
# MAGIC
# MAGIC Continue with the next lesson notebook: [02_retention_and_purging](./02_retention_and_purging).
# MAGIC
# MAGIC When the lessons are done, open the graded assignment: [PRO-S7 assignment notebook](../../../assignments/PRO-S7/assignment) · [the task](../../../assignments/PRO-S7/README.md).
