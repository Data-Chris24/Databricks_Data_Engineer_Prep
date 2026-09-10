# Databricks notebook source
# MAGIC %md
# MAGIC # PRO-S8 assignment — reference solution
# MAGIC
# MAGIC Two questions the catalog will not answer in one query:
# MAGIC **where does each privilege actually live**, and **can the principal reach the
# MAGIC table at all**.

# COMMAND ----------

import json

from databricks.sdk import WorkspaceClient
from pyspark.sql import functions as F

ASSESS = "pro_s8_assess"
spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")

w = WorkspaceClient()
names = {sp.application_id: sp.display_name for sp in w.service_principals.list()
         if sp.display_name and sp.display_name.startswith("de_prep_")}
print(names)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Which privileges apply, and where they come from
# MAGIC
# MAGIC `inherited_from` is the column that turns "this applies" into "this is granted
# MAGIC here". `NONE` means the grant really is on the table.

# COMMAND ----------

privs = spark.sql(f"""
    SELECT grantee, table_schema, table_name, privilege_type, inherited_from
    FROM {ASSESS}.information_schema.table_privileges
    WHERE table_schema <> 'information_schema'
""")
display(privs.groupBy("inherited_from").count())

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. The traversal chain
# MAGIC
# MAGIC `USE CATALOG` on the catalog and `USE SCHEMA` on the schema. Both, or the
# MAGIC privilege is inert.
# MAGIC
# MAGIC > **Mind the spelling.** You *grant* `USE CATALOG` with a space; the catalog
# MAGIC > *records* it as `USE_CATALOG` with an underscore. Filtering on the form you
# MAGIC > typed matches nothing, and an audit that matches nothing reports that nobody
# MAGIC > has access — confidently.

# COMMAND ----------

print("privilege names as information_schema records them:")
display(spark.sql(f"""
    SELECT DISTINCT privilege_type FROM {ASSESS}.information_schema.catalog_privileges
    UNION SELECT DISTINCT privilege_type FROM {ASSESS}.information_schema.schema_privileges
    ORDER BY 1
"""))

# COMMAND ----------

use_cat = spark.sql(f"""
    SELECT grantee FROM {ASSESS}.information_schema.catalog_privileges
    WHERE privilege_type = 'USE_CATALOG'
""").distinct().withColumn("has_use_catalog", F.lit(True))

use_sch = spark.sql(f"""
    SELECT grantee, schema_name FROM {ASSESS}.information_schema.schema_privileges
    WHERE privilege_type = 'USE_SCHEMA'
""").distinct().withColumn("has_use_schema", F.lit(True))

display(use_sch)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Compose the report

# COMMAND ----------

name_map = F.create_map(*[x for kv in names.items() for x in (F.lit(kv[0]), F.lit(kv[1]))])

base = (privs
        .withColumn("principal", name_map[F.col("grantee")])
        .filter("principal IS NOT NULL"))

report = (base
    .join(use_cat, "grantee", "left")
    .join(use_sch.withColumnRenamed("grantee", "sch_grantee"),
          (F.col("grantee") == F.col("sch_grantee")) &
          (F.col("table_schema") == F.col("schema_name")), "left")
    .select(
        F.col("principal"),
        F.col("table_schema"),
        F.col("table_name"),
        F.col("privilege_type").alias("privilege"),
        F.when(F.col("inherited_from") == "NONE", F.lit("TABLE"))
         .otherwise(F.col("inherited_from")).alias("granted_at_level"),
        F.coalesce(F.col("has_use_catalog"), F.lit(False)).alias("has_use_catalog"),
        F.coalesce(F.col("has_use_schema"), F.lit(False)).alias("has_use_schema"),
    )
    .withColumn("is_effective",
                F.col("has_use_catalog") & F.col("has_use_schema")))

report.write.mode("overwrite").option("overwriteSchema", "true") \
      .saveAsTable("pro_s8_access_report")
r = spark.table("pro_s8_access_report")
print(r.count(), "rows")
display(r.orderBy("principal", "table_schema", "table_name", "privilege"))

# COMMAND ----------

# MAGIC %md
# MAGIC ### The finding an audit exists to produce

# COMMAND ----------

display(r.groupBy("principal")
        .agg(F.count("*").alias("privileges_held"),
             F.sum(F.col("is_effective").cast("int")).alias("actually_usable"))
        .orderBy("principal"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Documentation coverage
# MAGIC
# MAGIC "Documented" is a definition, not a column. This one: a table comment **or** a
# MAGIC `description` tag, plus at least one documented column.

# COMMAND ----------

tables = spark.sql(f"""
    SELECT table_schema, table_name, comment
    FROM {ASSESS}.information_schema.tables
    WHERE table_schema <> 'information_schema'
""")
cols = spark.sql(f"""
    SELECT table_schema, table_name,
           count(*) AS column_count,
           count(comment) AS documented_columns
    FROM {ASSESS}.information_schema.columns
    WHERE table_schema <> 'information_schema'
    GROUP BY table_schema, table_name
""")
ttags = spark.sql(f"""
    SELECT schema_name AS table_schema, table_name,
           count(*) AS tag_count,
           max(CASE WHEN tag_name = 'description' THEN 1 ELSE 0 END) AS has_desc_tag
    FROM {ASSESS}.information_schema.table_tags
    GROUP BY schema_name, table_name
""")
ctags = spark.sql(f"""
    SELECT DISTINCT schema_name AS table_schema, table_name
    FROM {ASSESS}.information_schema.column_tags
    WHERE tag_name = 'pii' AND tag_value = 'true'
""").withColumn("has_pii_column", F.lit(True))

docs = (tables.join(cols, ["table_schema", "table_name"], "left")
        .join(ttags, ["table_schema", "table_name"], "left")
        .join(ctags, ["table_schema", "table_name"], "left")
        .select(
            "table_schema", "table_name",
            F.col("comment").isNotNull().alias("has_table_comment"),
            F.col("column_count").cast("int").alias("column_count"),
            F.col("documented_columns").cast("int").alias("documented_columns"),
            F.coalesce(F.col("tag_count"), F.lit(0)).cast("int").alias("tag_count"),
            F.coalesce(F.col("has_pii_column"), F.lit(False)).alias("has_pii_column"),
            (( F.col("comment").isNotNull() | (F.coalesce(F.col("has_desc_tag"), F.lit(0)) == 1))
             & (F.col("documented_columns") > 0)).alias("is_documented"),
        ))

docs.write.mode("overwrite").option("overwriteSchema", "true") \
    .saveAsTable("pro_s8_documentation")
d = spark.table("pro_s8_documentation")
display(d.orderBy("table_schema", "table_name"))

# COMMAND ----------

naive = d.filter("has_table_comment").count()
print(f"tables with a table comment : {naive}")
print(f"tables actually documented  : {d.filter('is_documented').count()}")
print("The two numbers differ because one table records its purpose as a tag.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Fixtures

# COMMAND ----------

fixtures = {
    "_generated_by": "solutions/PRO-S8/solution.py, run on Free Edition serverless",
    "report_rows": r.count(),
    "rows_by_principal": {x["principal"]: x["n"] for x in
                          r.groupBy("principal").agg(F.count("*").alias("n")).collect()},
    "rows_by_level": {x["granted_at_level"]: x["n"] for x in
                      r.groupBy("granted_at_level").agg(F.count("*").alias("n")).collect()},
    "effective_by_principal": {x["principal"]: x["n"] for x in
                               r.filter("is_effective")
                                .groupBy("principal").agg(F.count("*").alias("n")).collect()},
    "ineffective_rows": r.filter("NOT is_effective").count(),
    "report": sorted(
        [[x["principal"], x["table_schema"], x["table_name"], x["privilege"],
          x["granted_at_level"], x["has_use_catalog"], x["has_use_schema"],
          x["is_effective"]] for x in r.collect()]),
    "doc_rows": d.count(),
    "documented": d.filter("is_documented").count(),
    "with_table_comment": naive,
    "pii_tables": sorted([x["table_name"] for x in
                          d.filter("has_pii_column").collect()]),
    "documentation": sorted(
        [[x["table_schema"], x["table_name"], x["has_table_comment"], x["column_count"],
          x["documented_columns"], x["tag_count"], x["has_pii_column"],
          x["is_documented"]] for x in d.collect()]),
}
print(json.dumps(fixtures, indent=2)[:2000])
dbutils.fs.put("/Volumes/workspace/de_prep/raw/_pro_s8_expected.json",
               json.dumps(fixtures, indent=2), overwrite=True)
