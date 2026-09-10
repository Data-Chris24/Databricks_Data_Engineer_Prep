# Data Ingestion and Loading — 21%

Getting data in, incrementally, without duplicating it or losing it when the source
changes shape.

## Ingestion patterns — `ASSOC-S2-O1`

What makes ingestion *incremental* is bookkeeping: a record of what has already been
consumed. `COPY INTO` keeps a file list in table metadata; Auto Loader keeps a
checkpoint.

Incremental is **not** the same as continuous. Auto Loader with
`trigger(availableNow=True)` is incremental *and* batch — it processes what has
arrived and stops.

## `COPY INTO` — `ASSOC-S2-O2`

Loads files into an **existing** table, enforcing that table's schema.

```sql
COPY INTO bronze_orders
FROM '/Volumes/catalog/schema/raw/orders'
FILEFORMAT = CSV
FORMAT_OPTIONS ('header' = 'true', 'nullValue' = '')
```

**It is idempotent per file.** Run it twice and the second run is a no-op — which is
what makes it safe to schedule and safe to retry.

It will **not** coerce CSV text into declared numeric types. Declare
`unit_price DOUBLE` against a CSV source and the load fails with
`DELTA_FAILED_TO_MERGE_FIELDS`. Make bronze all `STRING` and cast into silver.

## Auto Loader — `ASSOC-S2-O3`

Structured Streaming underneath, but `availableNow` makes it behave like a batch job.

**Three locations, and confusing two of them is a classic trap:**

| Location | Holds | Delete it and… |
|---|---|---|
| landing path | the source files | nothing to read |
| `cloudFiles.schemaLocation` | inferred schema + versions | schema re-inferred from scratch |
| `checkpointLocation` | which files were processed | **everything is reprocessed** |

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
malformed batch costs you a column to inspect rather than lost records. Enable it as
routine.

## Choosing an approach — `ASSOC-S2-O6`

| | `COPY INTO` | Auto Loader |
|---|---|---|
| Tracks files in | table metadata | a checkpoint |
| Schema | must exist, enforced | inferred, can evolve |
| Scale | thousands of files | millions |
| Best for | predictable periodic loads | continuous or drifting sources |

## Lakeflow Connect — `ASSOC-S2-O4`

**Standard connectors** read sources you can reach directly — cloud storage (Auto
Loader), Kafka, Kinesis. **Managed connectors** are governed pipelines for enterprise
applications and databases (Salesforce, Workday, SQL Server), with Databricks handling
extraction and scheduling.

Database CDC connectors use an **ingestion gateway** that captures changes from the
source into staging, and a pipeline that applies them to Unity Catalog tables.

## JDBC and semi-structured — `ASSOC-S2-O5`, `ASSOC-S2-O7`

Credentials belong in a secret scope, read with `dbutils.secrets.get()`. Databricks
redacts them from notebook output — printing one shows `REDACTED`, which is what stops
credentials escaping into exported HTML, logs and screen-shares.

Land nested JSON in bronze **with its nesting intact**, then reshape on the way to
silver. Bronze faithful to the source means you can always reprocess when a
transformation turns out to be wrong.
