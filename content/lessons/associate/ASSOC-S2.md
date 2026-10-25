# Data Ingestion and Loading — 21%

Getting data in, incrementally, without duplicating it or losing it when the source
changes shape.

> **Names:** Lakeflow Spark Declarative Pipelines (Delta Live Tables, DLT),
> Lakeflow Jobs (Workflows), Auto Loader file events
> (`cloudFiles.useManagedFileEvents`; classic file notification mode,
> `cloudFiles.useNotifications`), Unity Catalog volumes (DBFS mounts and
> `/FileStore` uploads), Lakehouse Federation (query federation). Old names still
> appear in distractors.

## What the exam asks

- "Files land hourly; re-running the load must never duplicate rows" — `COPY INTO` or Auto Loader, both track what they already loaded (`ASSOC-S2-O1`)
- "A file was corrected in place and must be loaded again" — `COPY_OPTIONS ('force' = 'true')`; a plain re-run skips it (`ASSOC-S2-O2`)
- "Millions of files a day into one directory, and listing is slow and expensive" — switch Auto Loader from directory listing to file notification / file events (`ASSOC-S2-O3`)
- "Upstream added a column and the nightly job now fails once" — `addNewColumns` stops on purpose; a retry picks the column up (`ASSOC-S2-O3`)
- "Ingest from Salesforce or SQL Server without writing extraction code" — a Lakeflow Connect managed connector; SQL Server needs an ingestion gateway (`ASSOC-S2-O4`, `ASSOC-S2-O6`)
- "Flatten an array of line items into one row each" — `explode` (or `variant_explode` on `VARIANT`) on the way to silver (`ASSOC-S2-O7`)

## Defaults and limits

| Setting | Default or limit | Note |
|---|---|---|
| `COPY_OPTIONS ('force')` | `false` | `true` reloads files already loaded |
| `COPY_OPTIONS ('mergeSchema')` | `false` | `true` lets new columns in, and lets a column-less table take its schema from the first load |
| `COPY INTO ... FILES = (...)` | up to 1,000 file names | cannot be combined with `PATTERN` |
| `COPY INTO ... VALIDATE` | all rows | `VALIDATE n ROWS` checks n rows; writes nothing either way |
| `cloudFiles.inferColumnTypes` | `false` | CSV and JSON columns arrive as `STRING`; `read_files` defaults to `true` |
| `cloudFiles.schemaEvolutionMode` | `addNewColumns` without a schema, `none` with one | values: `addNewColumns`, `rescue`, `failOnNewColumns`, `none` (plus the newer `addNewColumnsWithTypeWidening`) |
| `rescuedDataColumn` | on as `_rescued_data` when the schema is inferred | off when you supply a schema or use mode `none`, until you set it |
| `cloudFiles.includeExistingFiles` | `true` | `false` skips files already there when the stream first starts |
| `cloudFiles.maxFilesPerTrigger` | 1,000 | `cloudFiles.maxBytesPerTrigger` has no default |
| Schema inference sample | first 50 GB or 1,000 files | whichever comes first |
| File detection mode | directory listing | file notification (file events) recommended for most workloads |
| Classic file notification streams | 100 per S3 bucket, 500 per ADLS storage account, 100 per GCS bucket | file events use one queue per external location instead |
| File events | run the stream at least every 7 days | otherwise the cache expires and Auto Loader falls back to listing |
| JDBC `numPartitions` | none | it is also the number of concurrent connections; Databricks advises staying under about 50 |
| JDBC `fetchsize` | `0` (the driver's own default) | Oracle's driver default is 10 rows per round trip |
| Managed connector `scd_type` | `SCD_TYPE_1` | `SCD_TYPE_2` keeps history |
| UI upload to a volume | 5 GB per file | larger files go through the SDK or CLI |

## Ingestion patterns — `ASSOC-S2-O1`

What makes ingestion *incremental* is bookkeeping: a record of what has already been
consumed. `COPY INTO` keeps a file list in table metadata; Auto Loader keeps a
checkpoint.

Incremental is **not** the same as continuous. Auto Loader with
`trigger(availableNow=True)` is incremental *and* batch — it processes what has
arrived and stops.

### The five ways to load a file, ranked

The exam contrasts the incremental paths with the ones that read everything every
time. From most to least suited to a recurring load:

| Rank | Path | Remembers what it loaded? | Use it for |
|---|---|---|---|
| 1 | Auto Loader (`cloudFiles`, or `STREAM read_files` in a pipeline) | yes, checkpoint | continuous or growing sources, drifting schemas |
| 2 | `COPY INTO` | yes, table metadata | scheduled SQL loads of thousands of files |
| 3 | `CREATE TABLE ... AS SELECT * FROM read_files(...)` | no | a one-off load or an exploration |
| 4 | ``SELECT * FROM csv.`path` `` / ``json.`path` `` | no | a quick look; no options, so CSV headers are read as data |
| 5 | Add data UI (upload a file, create a table) | no | a small reference file, by hand |

`INSERT OVERWRITE` and `MERGE` are not ingestion paths of their own: they decide
what a load does to the target. `INSERT OVERWRITE` replaces it, `MERGE` upserts into
it, and either can read from `read_files`.

```sql
-- one-off, schema inferred (header and column types on by default in read_files)
CREATE OR REPLACE TABLE bronze_orders AS
SELECT *, _metadata.file_name AS src
FROM read_files('/Volumes/main/raw/landing/orders/', format => 'csv',
                schemaHints => 'amount DOUBLE');

-- full refresh of the same table
INSERT OVERWRITE bronze_orders
SELECT *, _metadata.file_name AS src FROM read_files('/Volumes/main/raw/landing/orders/', format => 'csv');

-- upsert a delivery into an existing table
MERGE INTO customers AS t
USING read_files('/Volumes/main/raw/landing/customers/', format => 'json') AS s
ON t.id = s.id
WHEN MATCHED THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *;

-- direct path query: no options, every column a string named _c0, _c1, ...
SELECT * FROM csv.`/Volumes/main/raw/landing/orders/`;
```

> **Measured on Free Edition:** on the same two CSV files, `SELECT * FROM csv.`
> returned the header lines as data rows in columns `_c0`, `_c1`, `_c2`, while
> `read_files(..., format => 'csv')` with no other options used the header, typed
> `id` as `INT` and `amount` as `DOUBLE`, and added `_rescued_data`.

## `COPY INTO` — `ASSOC-S2-O2`

Loads files into an **existing** table, enforcing that table's schema.

```sql
COPY INTO bronze_orders
FROM '/Volumes/catalog/schema/raw/orders'
FILEFORMAT = CSV
FORMAT_OPTIONS ('header' = 'true', 'nullValue' = '')
```

**It is idempotent per file.** Run it twice and the second run is a no-op — which is
what makes it safe to schedule and safe to retry. To load a file again on purpose,
pass `COPY_OPTIONS ('force' = 'true')`.

It will **not** coerce CSV text into declared numeric types unless asked
(`FORMAT_OPTIONS ('inferSchema' = 'true')` infers them from the file;
`COPY_OPTIONS ('mergeSchema' = 'true')` admits new columns). Declare
`unit_price DOUBLE` against a CSV source and the load fails with
`DELTA_FAILED_TO_MERGE_FIELDS`. Make bronze all `STRING` and cast into silver.

### Transforms, file selection and what it returns

The source can be a `SELECT` over the path, so casts, renames and the `_metadata`
column happen during the load. Any expression a `SELECT` allows is accepted;
aggregation is limited to global aggregates, with no `GROUP BY`.

```sql
CREATE TABLE IF NOT EXISTS bronze_orders;            -- no columns: schemaless target

COPY INTO bronze_orders
FROM (
  SELECT id::INT AS id, upper(store) AS store, amount::DOUBLE AS amount,
         _metadata.file_name AS src
  FROM '/Volumes/main/raw/landing/orders/'
)
FILEFORMAT = CSV                                     -- CSV, JSON, AVRO, ORC, PARQUET, TEXT, BINARYFILE
PATTERN = 'orders_2026-*.csv'                        -- or FILES = ('a.csv', 'b.csv'), up to 1,000
FORMAT_OPTIONS ('header' = 'true')
COPY_OPTIONS ('mergeSchema' = 'true');               -- needed for the schemaless target; 'force' defaults to false

-- dry run: parse and check schema, write nothing
COPY INTO bronze_orders FROM (...) FILEFORMAT = CSV VALIDATE 10 ROWS FORMAT_OPTIONS ('header' = 'true');
```

Every `COPY INTO` returns one row: `num_affected_rows`, `num_inserted_rows`,
`num_skipped_corrupt_files`. A re-run over loaded files returns zeros, which is the
quickest way to see idempotence working.

A column-less `CREATE TABLE` is usable only by `COPY INTO` with `mergeSchema` until
the first load gives it a schema; `INSERT` and `MERGE` into it fail until then.

> **Measured on Free Edition:** the first load into a column-less table returned
> `num_inserted_rows = 3` and the table took the `SELECT`'s types (`id INT`,
> `amount DOUBLE`, `src STRING`); the identical re-run returned `0, 0, 0`;
> `FILES = ('o1.csv')` with `force` reloaded exactly that file's two rows;
> `VALIDATE 5 ROWS` returned the three parsed rows as a preview and the row count
> did not change.

## Auto Loader — `ASSOC-S2-O3`

Structured Streaming underneath, but `availableNow` makes it behave like a batch job.

**Three locations, and confusing two of them is a classic trap:**

| Location | Holds | Delete it and… |
|---|---|---|
| landing path | the source files | nothing to read |
| `cloudFiles.schemaLocation` | inferred schema + versions | schema re-inferred from scratch |
| `checkpointLocation` | which files were processed | **everything is reprocessed** |

"From scratch" means from the files in the landing path *now*: the schema location
keeps no list of files, so nothing reloads, but a type can come back different. One
`"abc"` that `_rescued_data` caught in a `DOUBLE` column makes the re-inferred
column `STRING`.

![Run the stream, drop files, then delete the checkpoint or the schema location](visual:autoloader-checkpoint?h=900)

> **Measured on Free Edition:** two JSON files loaded, the checkpoint deleted, the
> stream re-run: four rows, each file's row twice, no error. With the checkpoint kept
> and only the schema location deleted, the re-run read nothing and wrote a fresh
> `_schemas/0`, in which `amount` had become `STRING` because of an earlier `"abc"`.

The options the exam uses, with their defaults:

```python
(spark.readStream.format("cloudFiles")
    .option("cloudFiles.format", "json")                    # csv, json, xml, parquet, avro, orc, text, binaryFile
    .option("cloudFiles.schemaLocation", schema_path)       # required when the schema is inferred
    .option("cloudFiles.inferColumnTypes", "true")          # default false: CSV/JSON columns are STRING
    .option("cloudFiles.schemaHints", "amount DOUBLE")      # pin some types, infer the rest
    .option("cloudFiles.schemaEvolutionMode", "addNewColumns")  # default without a schema; 'none' with one
    .option("rescuedDataColumn", "_rescued_data")           # automatic when inferring; set it with .schema()
    .option("cloudFiles.includeExistingFiles", "true")      # default true; read only on the first start
    .option("cloudFiles.maxFilesPerTrigger", 1000)          # default 1000 files per micro-batch
    .option("cloudFiles.useManagedFileEvents", "true")      # file events; default is directory listing
    .load(landing_path)
  .writeStream
    .option("checkpointLocation", checkpoint_path)
    .option("mergeSchema", "true")                          # writer side of schema evolution
    .trigger(availableNow=True)                             # drain what is there, then stop
    .toTable("main.bronze.orders"))
```

Which of these go on the reader and which on the writer, and what each does on the
wrong side, is the subject of the reference below this note and of the optional
deep-dive lesson `04_optional_auto_loader_deep_dive`.

**Schema evolution takes two settings, one on each side:**

- `cloudFiles.schemaEvolutionMode` on the **reader** — lets Auto Loader notice a new column
- `mergeSchema` on the **writer** — lets the Delta table accept it

Set only the first and you get `DELTA_METADATA_MISMATCH`. The one that *sounds* like
"the schema evolution option" is half the job.

**`addNewColumns` fails on purpose** the first time it meets a new column:

```
[UNKNOWN_FIELD_EXCEPTION.NEW_FIELDS_IN_FILE] ... which can be fixed by an
automatic retry: true
```

The failure *is* the mechanism — it records the wider schema and stops so a human
learns the source changed. Something must run it again: interactively you re-run the
cell, in a job the retry policy does it. Catching the exception inside one notebook
run does not work.

**`rescuedDataColumn`** captures anything that would not fit the schema, so a
malformed batch costs you a column to inspect rather than lost records. It is on by
default when Auto Loader infers the schema, except under `schemaEvolutionMode =
none`; when you supply a schema, or choose `none`, set `rescuedDataColumn` yourself
so bad values are kept rather than turned into silent NULLs.

### Schema evolution, mode by mode

Three things a source can do, under each `cloudFiles.schemaEvolutionMode` value.
The writer has `mergeSchema` set throughout.

| Mode | Source adds a column | A value does not fit its type (`"abc"` in a `DOUBLE`) | Stream fails? |
|---|---|---|---|
| `addNewColumns` (default, no schema given) | stream stops once, schema widened; the restart adds the column | value NULL, original kept in `_rescued_data` | once per new column; a retry continues |
| `rescue` | column not added; its values go into `_rescued_data` | value NULL, kept in `_rescued_data` | never |
| `failOnNewColumns` | stream stops and keeps stopping until you change the schema or remove the file | value NULL, kept in `_rescued_data` | yes, every run |
| `none` (default when you call `.schema()`) | column ignored, values dropped | value NULL, lost unless you set `rescuedDataColumn` | never |

A type change is never evolved by these four: an `INT` column stays `INT` and the
values that do not fit are rescued. The newer `addNewColumnsWithTypeWidening` mode
also widens safe changes such as `INT` to `BIGINT`.

> **Measured on Free Edition:** each mode was run on three CSV files in turn (a good
> row, a row with `amount = "abc"`, then a file with an extra `channel` column) with
> `availableNow` and a retry. `addNewColumns`, and the default with no mode set,
> failed on the new column then loaded it on the retry; `failOnNewColumns` failed on
> both runs and never loaded the file; `rescue` never failed and put
> `{"channel":"web","_file_path":...}` in `_rescued_data`. Under `none` the table had
> **no** `_rescued_data` column at all, so `"abc"` became a silent NULL, and a stream
> given `.schema(...)` with no other option behaved the same. Without
> `inferColumnTypes`, every CSV column and the nested JSON `user` object arrived as
> `STRING`. With `includeExistingFiles = false`, a file already in the directory at
> the first start was never loaded; only the file added after it was.

### Directory listing vs file notification

Auto Loader has to find new files somehow, and the two ways scale differently.

| | Directory listing (default) | File notification / file events |
|---|---|---|
| How it finds files | lists the input directory each trigger | the cloud pushes an event per new file into a queue |
| Needs | read access to the path only | a queue and subscription (SNS + SQS, Event Grid + Queue Storage, Pub/Sub); with file events Databricks creates them on the external location |
| Cost grows with | the size of the directory and how often you trigger | the number of new files |
| Choose it when | the directory is modest, triggers are infrequent, you cannot set up cloud events | "millions of files", "large directory", "listing is slow / expensive", "near real time", continuous triggers |

```python
# file events (recommended): enable file events on the external location first
.option("cloudFiles.useManagedFileEvents", "true")
# classic file notification: one queue per stream, limits per bucket/account
.option("cloudFiles.useNotifications", "true")
# classic mode only: periodic listing to catch events the cloud dropped
.option("cloudFiles.backfillInterval", "1 day")
```

You can switch between the modes on an existing stream and keep exactly-once
processing, because the checkpoint, not the detection mode, records what was
loaded. Neither mode guarantees the order files are processed in.

The lesson notebooks run directory listing over a volume. File events are
configured on an external location, so the notification side of this section was
checked against the docs only.

## Choosing an approach — `ASSOC-S2-O6`

| | `COPY INTO` | Auto Loader |
|---|---|---|
| Tracks files in | table metadata | a checkpoint |
| Schema | must exist, enforced | inferred, can evolve |
| Scale | thousands of files | millions |
| Best for | predictable periodic loads | continuous or drifting sources |

Beyond files, the choice is about who writes the extraction:

| Requirement in the stem | Pick |
|---|---|
| Files in cloud storage, growing, schema drifts | Auto Loader |
| Files, SQL-only team, scheduled, modest volume | `COPY INTO` (or a streaming table over `read_files`) |
| SaaS app or database, no extraction code, governed in Unity Catalog | Lakeflow Connect managed connector |
| A source no managed connector covers | partner tool, community connector, or JDBC / REST in a notebook |
| Query a database in place, no copy | Lakehouse Federation (a connection plus a foreign catalog) |

```sql
-- SQL-only incremental load: a streaming table over read_files is Auto Loader underneath
CREATE OR REFRESH STREAMING TABLE bronze_orders AS
SELECT * FROM STREAM read_files('/Volumes/main/raw/landing/orders/', format => 'csv');
```

## Lakeflow Connect — `ASSOC-S2-O4`

**Standard connectors** read sources you can reach directly — cloud storage (Auto
Loader), Kafka, Kinesis. **Managed connectors** are governed pipelines for enterprise
applications and databases (Salesforce, Workday, SQL Server), with Databricks handling
extraction and scheduling.

Database CDC connectors use an **ingestion gateway** that captures changes from the
source into staging, and a pipeline that applies them to Unity Catalog tables.

The managed connectors the docs name:

| Kind | Connectors | Moving parts |
|---|---|---|
| Databases (CDC) | SQL Server, PostgreSQL, MySQL, Oracle | connection → ingestion gateway (continuous, its own job) → staging volume → ingestion pipeline → streaming tables |
| SaaS applications | Salesforce, Workday, ServiceNow, HubSpot, Jira, Confluence, Google Analytics, Zendesk and more | connection → ingestion pipeline (serverless) → streaming tables |
| Files | SharePoint, Google Drive | connection → ingestion pipeline |

Every connector starts from a **connection**, a Unity Catalog securable that holds
the source's credentials. For a database it can be created in SQL; SaaS connectors
that sign in with browser OAuth are created in the UI.

```sql
CREATE CONNECTION sqlserver_erp TYPE sqlserver           -- also postgresql, mysql, snowflake, redshift, ...
OPTIONS (
  host 'erp.example.com',
  port '1433',
  user secret('erp', 'user'),                            -- read from a secret scope, never a literal
  password secret('erp', 'password')
);
GRANT USE CONNECTION ON CONNECTION sqlserver_erp TO `data_engineers`;
```

```yaml
# database connector, as a bundle: a continuous gateway, then a serverless ingestion pipeline
resources:
  pipelines:
    erp_gateway:
      continuous: true                     # the gateway always runs, capturing changes
      gateway_definition:
        connection_name: sqlserver_erp     # the connection lives on the gateway
        gateway_storage_catalog: main      # staging volume for captured changes
        gateway_storage_schema: erp_staging
    erp_ingest:
      serverless: true
      ingestion_definition:
        ingestion_gateway_id: ${resources.pipelines.erp_gateway.id}
        objects:
          - table:
              source_catalog: erp
              source_schema: dbo
              source_table: orders
              destination_catalog: main
              destination_schema: bronze
              table_configuration:
                scd_type: SCD_TYPE_2       # default SCD_TYPE_1 overwrites; type 2 keeps history
```

> **Measured on Free Edition:** `CREATE CONNECTION ... TYPE postgresql` against a
> host that does not exist succeeded, and `DESCRIBE CONNECTION` showed it
> read-only with the password left out: creating a connection does not contact
> the source. The database connectors' gateway needs classic compute, which Free
> Edition lacks, so managed connectors cannot run here.

## JDBC and semi-structured — `ASSOC-S2-O5`, `ASSOC-S2-O7`

Credentials belong in a secret scope, read with `dbutils.secrets.get()`. Databricks
redacts them from notebook output — printing one shows `REDACTED`, which is what stops
credentials escaping into exported HTML, logs and screen-shares.

A plain JDBC read is one query on one connection. To read in parallel, give Spark a
column to split on; all four options go together:

```python
df = (spark.read.format("jdbc")
      .option("url", "jdbc:postgresql://db.example.com:5432/shop")
      .option("dbtable", "public.orders")             # or "(SELECT ...) AS q"; 'query' cannot be partitioned
      .option("user", dbutils.secrets.get("shop", "user"))
      .option("password", dbutils.secrets.get("shop", "password"))
      .option("partitionColumn", "order_id")          # numeric, date or timestamp
      .option("lowerBound", "1")                      # bounds set the stride only:
      .option("upperBound", "1000000")                #   rows outside them are still read
      .option("numPartitions", "8")                   # no default; = concurrent connections
      .option("fetchsize", "1000")                    # default 0, the driver's own
      .load())
df.write.mode("append").saveAsTable("main.bronze.orders")
```

When Lakehouse Federation supports the database, Databricks recommends a connection
and a foreign catalog over hand-written JDBC.

Land nested JSON in bronze **with its nesting intact**, then reshape on the way to
silver. Bronze faithful to the source means you can always reprocess when a
transformation turns out to be wrong.

### The JSON toolkit

| Bronze column holds | Reach in with | Returns |
|---|---|---|
| JSON as `STRING` | `raw:user.geo.city`, `raw:items[0].sku`, `raw:items[*].sku` | `STRING` |
| JSON as `STRING` | `from_json(raw, 'id BIGINT, items ARRAY<STRUCT<...>>')` (schema from `schema_of_json`) | a `STRUCT` you dot into |
| `VARIANT` (`parse_json(raw)`, or `read_files(..., singleVariantColumn => 'data')`) | `v:user.geo.city::STRING`, `try_variant_get(v, '$.items[0].qty', 'int')` | `VARIANT` until cast |
| `STRUCT` / `ARRAY` (inferred by `read_files` or Auto Loader) | `user.geo.city`, `explode(items)`, `inline(items)` | typed columns |

Arrays become rows with `explode` (one row per element, dropping rows whose array is
empty or null), `explode_outer` (keeps them), `inline` (array of structs straight to
columns) and, for `VARIANT`, `variant_explode`.

### Nested JSON to a flat silver row

One bronze record:

```json
{"id": 1, "user": {"name": "ana", "geo": {"city": "Lisbon"}},
 "items": [{"sku": "s1", "qty": 2}, {"sku": "s2", "qty": 1}]}
```

becomes one silver row per line item:

```sql
CREATE OR REPLACE TABLE silver_order_lines AS
SELECT o.id            AS order_id,
       o.user.name     AS customer,
       o.user.geo.city AS city,
       item.sku,
       item.qty
FROM bronze_orders_json AS o                     -- read_files inferred user STRUCT, items ARRAY<STRUCT>
LATERAL VIEW explode(o.items) AS item;
```

| order_id | customer | city | sku | qty |
|---|---|---|---|---|
| 1 | ana | Lisbon | s1 | 2 |
| 1 | ana | Lisbon | s2 | 1 |

Keep the raw text instead and the same row comes from
`from_json(raw, '<schema>')` then `explode`, or from `parse_json(raw)` then
`variant_explode(v:items)` with each field cast (`value:sku::STRING`).

> **Measured on Free Edition:** on a `STRING` column, `raw:id` returned type
> `string` and `raw:items[*].sku` returned `["s1","s2"]`; on `VARIANT`,
> `v:user.geo.city` returned `"Lisbon"` with its quotes (type `variant`) until cast
> with `::STRING`; an out-of-range `v:items[1]` returned NULL rather than failing.
> `explode`, `inline`, `from_json` + `explode` and `variant_explode` all produced the
> same three rows from two records.

## Further reading

Official documentation for what this section tests, one link per topic:

- [Ingest data into Databricks](https://docs.databricks.com/aws/en/ingestion/) — the whole menu of ingestion paths in one place.
- [COPY INTO](https://docs.databricks.com/aws/en/sql/language-manual/delta-copy-into) — syntax, `FORMAT_OPTIONS`, `COPY_OPTIONS`, `force`.
- [Get started with COPY INTO](https://docs.databricks.com/aws/en/ingestion/cloud-object-storage/copy-into/) — the schemaless target table and `mergeSchema`.
- [read_files](https://docs.databricks.com/aws/en/sql/language-manual/functions/read_files) — options, inference defaults, `STREAM read_files`.
- [Create a table from uploaded files](https://docs.databricks.com/aws/en/ingestion/add-data/upload-data) — the Add data UI path.
- [Auto Loader](https://docs.databricks.com/aws/en/ingestion/cloud-object-storage/auto-loader/) — the `cloudFiles` source and when to prefer it.
- [Auto Loader schema inference and evolution](https://docs.databricks.com/aws/en/ingestion/cloud-object-storage/auto-loader/schema) — `schemaEvolutionMode`, `schemaHints`, `_rescued_data`.
- [Directory listing mode](https://docs.databricks.com/aws/en/ingestion/cloud-object-storage/auto-loader/directory-listing-mode) — how listing works and what it costs.
- [File notification mode](https://docs.databricks.com/aws/en/ingestion/cloud-object-storage/auto-loader/file-notification-mode) — directory listing vs notifications, and why scale flips the choice.
- [Auto Loader options](https://docs.databricks.com/aws/en/ingestion/cloud-object-storage/auto-loader/options) — every `cloudFiles.*` option with its default.
- [Lakeflow Connect](https://docs.databricks.com/aws/en/ingestion/lakeflow-connect/) — managed connectors for SaaS and databases.
- [History tracking (SCD type 1 and 2)](https://docs.databricks.com/aws/en/ingestion/lakeflow-connect/scd) — `scd_type` in managed connectors.
- [CREATE CONNECTION](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-connection) — connection types and `secret()` options.
- [Query databases using JDBC](https://docs.databricks.com/aws/en/connect/external-systems/jdbc) — partitioned reads and pushdown.
- [Semi-structured data](https://docs.databricks.com/aws/en/semi-structured/) — `:` paths, `from_json`, `VARIANT`.
- [Query JSON strings](https://docs.databricks.com/aws/en/semi-structured/json) — the `:` path syntax on `STRING` columns.
- [Query variant data](https://docs.databricks.com/aws/en/semi-structured/variant) — `parse_json`, casts, `variant_explode`.

Videos for another angle on the hard parts (channel, length):

- [Auto Loader in Databricks: schema evolution modes and file detection modes](https://www.youtube.com/watch?v=g7d1U2_dWS8) — Ease With Data, 23 min. The two topics this section's objective names, demonstrated.
- [Stop Building Batch Jobs! Use Databricks Auto Loader Instead](https://www.youtube.com/watch?v=YHJQ5HmlclA) — Data Analytics Talks, 12 min. Why incremental ingestion beats a rerun-everything batch.
