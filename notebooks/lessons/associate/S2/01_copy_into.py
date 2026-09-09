# Databricks notebook source
# MAGIC %md
# MAGIC # `COPY INTO` — incremental loading from a volume
# MAGIC
# MAGIC **Objective `ASSOC-S2-O2`** — use `COPY INTO` to incrementally load files from
# MAGIC cloud object storage into a Unity Catalog table.
# MAGIC
# MAGIC Dataset: `s2_teach` — flat retail orders as CSV. Run
# MAGIC `notebooks/datasets/generate_ASSOC-S2.py` first if the volume is empty.
# MAGIC
# MAGIC The one idea to take away: **`COPY INTO` remembers which files it has already
# MAGIC loaded.** Running it twice does not double your data. That is what makes it
# MAGIC *incremental* rather than merely a bulk insert, and it is the property the exam
# MAGIC keeps asking about.

# COMMAND ----------

CATALOG = "workspace"
SCHEMA = "de_prep"
RAW = f"/Volumes/{CATALOG}/{SCHEMA}/raw/s2_teach"

spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")
print(f"loading from {RAW}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. A target table must exist first
# MAGIC
# MAGIC `COPY INTO` loads *into* a table; it will not invent one. Declaring the schema
# MAGIC yourself is the point — this is **schema enforcement**. A file whose columns do
# MAGIC not fit is rejected rather than quietly reshaping your table.
# MAGIC
# MAGIC **Every column is `STRING`, deliberately.** CSV has no types — each field is
# MAGIC text until something interprets it — so a bronze table that mirrors the source
# MAGIC exactly is the honest representation. Typing happens on the way to silver, where
# MAGIC a bad value becomes a visible null you can count rather than a load failure.
# MAGIC
# MAGIC Declare `unit_price DOUBLE` here instead and the load fails outright with
# MAGIC `DELTA_FAILED_TO_MERGE_FIELDS`: `COPY INTO` will not silently coerce CSV text
# MAGIC into your declared types. That error is worth causing once on purpose.

# COMMAND ----------

spark.sql("DROP TABLE IF EXISTS bronze_orders")
spark.sql("""
    CREATE TABLE bronze_orders (
        order_id     STRING,
        store        STRING,
        product_sku  STRING,
        quantity     STRING,
        unit_price   STRING,
        discount_pct STRING,
        ordered_at   STRING
    )
    COMMENT 'Raw retail orders, loaded incrementally with COPY INTO'
""")
print("bronze_orders created (empty)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. The first load
# MAGIC
# MAGIC `FILEFORMAT` is required. `header = 'true'` skips the header row;
# MAGIC `inferSchema` is deliberately *not* used — the table's declared schema wins.

# COMMAND ----------

result = spark.sql(f"""
    COPY INTO bronze_orders
    FROM '{RAW}'
    FILEFORMAT = CSV
    FORMAT_OPTIONS ('header' = 'true', 'nullValue' = '')
""")
display(result)

# COMMAND ----------

print("rows now:", spark.table("bronze_orders").count())

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Run it again — this is the part that matters
# MAGIC
# MAGIC Identical statement, no filtering, no "only new files" flag. The row count does
# MAGIC not move, because `COPY INTO` tracks the files it has already ingested in the
# MAGIC table's metadata and skips them.
# MAGIC
# MAGIC This is why you can safely put `COPY INTO` on a schedule: a run that finds
# MAGIC nothing new is a no-op, and a retry after a failure will not duplicate rows.

# COMMAND ----------

again = spark.sql(f"""
    COPY INTO bronze_orders
    FROM '{RAW}'
    FILEFORMAT = CSV
    FORMAT_OPTIONS ('header' = 'true', 'nullValue' = '')
""")
display(again)
print("rows after re-running:", spark.table("bronze_orders").count())

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Bronze to silver — the cleaning the source forced on us
# MAGIC
# MAGIC Two problems the raw data hands us, both typical:
# MAGIC
# MAGIC - Everything is text. Cast each column to what it actually is, and let a value
# MAGIC   that will not cast become null so you can count it.
# MAGIC - `discount_pct` is empty on roughly 15% of rows. An empty here means *no
# MAGIC   discount*, not *unknown*, so `coalesce` to 0.0 is correct. Decide which of the
# MAGIC   two your nulls mean before filling them — filling an unknown with a default
# MAGIC   invents data.

# COMMAND ----------

spark.sql("DROP TABLE IF EXISTS silver_orders")
spark.sql("""
    CREATE TABLE silver_orders
    COMMENT 'Cleaned, typed orders'
    AS
    SELECT
        order_id,
        store,
        product_sku,
        CAST(quantity AS INT)                          AS quantity,
        CAST(unit_price AS DOUBLE)                     AS unit_price,
        COALESCE(CAST(discount_pct AS DOUBLE), 0.0)    AS discount_pct,
        CAST(ordered_at AS TIMESTAMP)                  AS ordered_at,
        ROUND(CAST(quantity AS INT) * CAST(unit_price AS DOUBLE)
              * (1 - COALESCE(CAST(discount_pct AS DOUBLE), 0.0)), 2) AS net_amount
    FROM bronze_orders
""")
display(spark.sql("SELECT * FROM silver_orders ORDER BY order_id LIMIT 5"))

# COMMAND ----------

display(spark.sql("""
    SELECT
        count(*)                                    AS rows,
        sum(CASE WHEN quantity IS NULL THEN 1 ELSE 0 END)   AS bad_quantity_casts,
        round(sum(net_amount), 2)                   AS total_net
    FROM silver_orders
"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## What to remember
# MAGIC
# MAGIC | | |
# MAGIC |---|---|
# MAGIC | `COPY INTO` needs an existing table | It enforces that table's schema |
# MAGIC | It is idempotent per file | Re-running does not duplicate |
# MAGIC | Good for | Bounded, periodic file loads into a known schema |
# MAGIC | Reach for Auto Loader instead when | Files arrive continuously, or at a volume where tracking them file-by-file becomes the bottleneck, or the schema changes over time |
# MAGIC
# MAGIC That last row is the next lesson.
