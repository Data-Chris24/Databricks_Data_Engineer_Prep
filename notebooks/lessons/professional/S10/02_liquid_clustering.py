# Databricks notebook source
# MAGIC %md
# MAGIC # PRO-S10 · Liquid clustering, and what it replaces
# MAGIC
# MAGIC **Objectives:** `PRO-S10-O2`, `PRO-S10-O3`
# MAGIC
# MAGIC Partitioning is a *directory layout* decision you make once, at create time, and
# MAGIC live with. Liquid clustering is a *property of the table* that the engine
# MAGIC maintains, and that you can change later without rewriting the world.
# MAGIC
# MAGIC Everything below runs; the claims are printed from the table itself rather than
# MAGIC asserted in prose.

# COMMAND ----------

from pyspark.sql import functions as F

spark.sql("USE CATALOG workspace")
spark.sql("USE SCHEMA de_prep")
# the fact table lesson 01 built - already denormalised with segment and region
sales = spark.table("pro_s10_teach_fact_sales")
print(sales.count(), "sales rows")
sales.printSchema()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Why partitioning goes wrong
# MAGIC
# MAGIC Partitioning splits the table into one directory per distinct value. That is only
# MAGIC a good trade when each directory holds enough data to be worth opening.
# MAGIC
# MAGIC The rule of thumb Databricks publishes: **don't partition below about 1 GB per
# MAGIC partition.** Look at what partitioning by day would produce here.

# COMMAND ----------

per_day = (sales.groupBy("sold_on").count()
           .agg(F.min("count").alias("min_rows"),
                F.avg("count").alias("avg_rows"),
                F.max("count").alias("max_rows"),
                F.count("*").alias("distinct_days")).collect()[0])
print(f"partition by sold_on -> {per_day['distinct_days']} partitions, "
      f"{per_day['avg_rows']:.1f} rows each on average "
      f"(min {per_day['min_rows']}, max {per_day['max_rows']})")
print()
print("Each of those becomes a directory holding one tiny file. The query planner then")
print("opens hundreds of files to read a few thousand rows - the small-file problem,")
print("and it is caused by the layout, not by the data volume.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Clustering instead
# MAGIC
# MAGIC `CLUSTER BY` records the columns on the table. There are no directories: the
# MAGIC engine groups rows into files by those columns, and file-level statistics let it
# MAGIC skip the files that cannot match.

# COMMAND ----------

spark.sql("DROP TABLE IF EXISTS pro_s10_sales_clustered")
spark.sql("""
    CREATE TABLE pro_s10_sales_clustered
    CLUSTER BY (sold_on, segment)
    AS SELECT * FROM pro_s10_teach_fact_sales
""")

d = spark.sql("DESCRIBE DETAIL pro_s10_sales_clustered").collect()[0]
print("clusteringColumns:", d["clusteringColumns"])
print("partitionColumns :", d["partitionColumns"], " <- empty; no directory layout")
print("numFiles         :", d["numFiles"])

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. The three things clustering can do that partitioning cannot
# MAGIC
# MAGIC ### a. Change the keys later
# MAGIC
# MAGIC Query patterns change. Changing a partition column means recreating the table and
# MAGIC rewriting every file. Changing clustering keys is a metadata operation - existing
# MAGIC data stays where it is, and future writes and `OPTIMIZE` use the new keys.

# COMMAND ----------

spark.sql("ALTER TABLE pro_s10_sales_clustered CLUSTER BY (region, sold_on)")
print("after ALTER:",
      spark.sql("DESCRIBE DETAIL pro_s10_sales_clustered").collect()[0]["clusteringColumns"])
print()
print("Note what this does NOT do: it does not rewrite existing files. The new keys")
print("apply to writes from here on, and to OPTIMIZE. Old data is reclustered")
print("incrementally, not in one stop-the-world rewrite.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### b. Survive skew
# MAGIC
# MAGIC A partition is exactly as big as its key value says. If one region is ten times
# MAGIC the others, that directory is ten times the others and the task reading it is the
# MAGIC straggler. Clustering targets *file* size, so a hot key is spread across files
# MAGIC instead of concentrated in one directory.

# COMMAND ----------

display(sales.groupBy("region").count().orderBy(F.desc("count")))

# COMMAND ----------

# MAGIC %md
# MAGIC ### c. Be maintained for you
# MAGIC
# MAGIC `CLUSTER BY AUTO` lets Databricks choose and revise the keys from the query
# MAGIC history. It is the honest default when you do not yet know the access pattern -
# MAGIC and not knowing is the normal state at table-creation time.

# COMMAND ----------

spark.sql("ALTER TABLE pro_s10_sales_clustered CLUSTER BY AUTO")
d = spark.sql("DESCRIBE DETAIL pro_s10_sales_clustered").collect()[0]
print("clusterByAuto    :", d["clusterByAuto"])
print("clusteringColumns:", d["clusteringColumns"])
print()
print("Read those two together. AUTO is a separate flag, not an empty key list: the")
print("keys you last set stay in place, and Databricks may revise them from the query")
print("history. So `clusteringColumns` alone never tells you whether a table is under")
print("manual or automatic clustering - check `clusterByAuto`.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. OPTIMIZE means something different here
# MAGIC
# MAGIC On a plain table, `OPTIMIZE` compacts small files, and `ZORDER BY` re-sorts them.
# MAGIC `ZORDER` is **not incremental** - it re-sorts everything it touches every time.
# MAGIC
# MAGIC On a clustered table, `OPTIMIZE` clusters the new data only. Runs stay cheap as
# MAGIC the table grows, which is the property that makes it maintainable.

# COMMAND ----------

r = spark.sql("OPTIMIZE pro_s10_sales_clustered").collect()[0]
metrics = r["metrics"]
print("files added  :", metrics["numFilesAdded"])
print("files removed:", metrics["numFilesRemoved"])

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. They are mutually exclusive
# MAGIC
# MAGIC A table is partitioned or clustered, never both. Trying is a good way to find out
# MAGIC that Delta treats them as the same decision.

# COMMAND ----------

try:
    spark.sql("""
        CREATE OR REPLACE TABLE pro_s10_sales_both
        PARTITIONED BY (region)
        CLUSTER BY (sold_on)
        AS SELECT * FROM pro_s10_teach_fact_sales
    """)
    print("unexpectedly accepted")
except Exception as e:
    print("rejected, as it should be:")
    print(" ", str(e).splitlines()[0][:200])
    print()
    print("The error class is SPECIFY_CLUSTER_BY_WITH_PARTITIONED_BY_IS_NOT_ALLOWED -")
    print("Delta treats layout as one decision with one answer.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. When partitioning is still right
# MAGIC
# MAGIC The exam asks for the *benefits* of liquid clustering, but "always cluster" is not
# MAGIC the lesson. Partitioning still wins when:
# MAGIC
# MAGIC - Partitions are large — comfortably above ~1 GB each.
# MAGIC - You need to **drop or overwrite** whole slices cheaply. `REPLACE WHERE` on a
# MAGIC   partition column is a metadata operation; there is no clustering equivalent.
# MAGIC - An external consumer depends on the directory layout.
# MAGIC
# MAGIC | | Partitioning | ZORDER | Liquid clustering |
# MAGIC |---|---|---|---|
# MAGIC | Set at | create time, fixed | each OPTIMIZE | any time, `ALTER TABLE` |
# MAGIC | Physical form | directories | sort order within files | file grouping |
# MAGIC | Incremental | n/a | **no** — re-sorts each run | **yes** — new data only |
# MAGIC | Skew | one big partition | tolerated | spread across files |
# MAGIC | Small files | the classic cause | doesn't fix the layout | targets file size |
# MAGIC | Change your mind | rewrite the table | free, but pay the sort | metadata change |

# COMMAND ----------

spark.sql("DROP TABLE IF EXISTS pro_s10_sales_clustered")
spark.sql("DROP TABLE IF EXISTS pro_s10_sales_both")
print("cleaned up")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Next
# MAGIC
# MAGIC When the lessons are done, open the graded assignment: [PRO-S10 assignment notebook](../../../assignments/PRO-S10/assignment) · [the task](../../../assignments/PRO-S10/README.md).
