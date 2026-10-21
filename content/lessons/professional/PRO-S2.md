# Data Ingestion & Acquisition — 7%

A small section with one organising question: **does the file tell you its own
schema?** Cost, safety and which reader options you must supply all follow from
the answer. The second objective is the shape of a landing table that batch and
streaming writers can share.

> **Names:** Lakeflow Spark Declarative Pipelines (Delta Live Tables; `@dlt` is now `@dp`, `LIVE.` is gone), Lakeflow Jobs (Workflows), `skipChangeCommits` (`ignoreChanges`, legacy since Databricks Runtime 12.2 LTS).

## What the exam asks

- A nightly read of terabytes of JSON with no schema takes twice as long as expected — schema inference is a second pass; supply `.schema()` (`PRO-S2-O1`)
- CSV and Parquet with the same columns in a different order are combined with `union` and nothing fails — `union` is positional; use `unionByName` (`PRO-S2-O1`)
- A Kafka stream returns unreadable `value` bytes — the source is always binary; decode with `CAST`, `from_json` or `from_avro` (`PRO-S2-O1`)
- Malformed rows vanish, turn into nulls, or fail the job — reader `mode`, `_corrupt_record` and `badRecordsPath` (`PRO-S2-O1`)
- An `UPDATE` on bronze makes the downstream stream fail with `DELTA_SOURCE_TABLE_IGNORE_CHANGES` — keep bronze append-only; `skipChangeCommits` is the costly escape hatch (`PRO-S2-O2`)
- An `availableNow` Auto Loader job runs twice in an hour — the checkpoint makes the second run a no-op; a new checkpoint re-ingests everything (`PRO-S2-O2`)

## Defaults and limits

| Setting | Default or limit | Note |
|---|---|---|
| CSV `header` / `inferSchema` | `false` / `false` | without both, columns are `_c0`, `_c1` … and every type is `STRING` |
| Reader `mode` (CSV, JSON) | `PERMISSIVE` | others: `DROPMALFORMED`, `FAILFAST` |
| `columnNameOfCorruptRecord` | `_corrupt_record` | with an explicit schema, filled only if the schema has the column; inference adds it |
| `from_avro` `mode` | `FAILFAST` | `PERMISSIVE` returns a record of nulls instead |
| Kafka `startingOffsets` | `latest` streaming, `earliest` batch | `endingOffsets` (batch only) defaults to `latest` |
| Kafka `failOnDataLoss` / `includeHeaders` | `true` / `false` | `maxOffsetsPerTrigger`: no cap unless set |
| Auto Loader `cloudFiles.maxFilesPerTrigger` | 1000 | `cloudFiles.maxBytesPerTrigger` unset |
| Auto Loader `cloudFiles.inferColumnTypes` | `false` | JSON, CSV and XML columns infer as `STRING` |
| Auto Loader schema inference sample | first 50 GB or 1000 files | whichever is crossed first |
| Auto Loader `cloudFiles.schemaEvolutionMode` | `addNewColumns`; `none` if you supply a schema | `rescue`, `failOnNewColumns`, `addNewColumnsWithTypeWidening` |
| Delta source `maxFilesPerTrigger` | 1000 | `maxBytesPerTrigger` unset |
| Delta source `skipChangeCommits` | `false` | without it, any non-append commit fails the stream |
| `delta.appendOnly` | `false` | `true` refuses `UPDATE`, `DELETE`, `TRUNCATE`, overwrite and updating `MERGE` |

## Reading the formats the exam names — `PRO-S2-O1`

| Format | Schema in the file? | Reader needs |
|---|---|---|
| Delta | yes, plus a transaction log | nothing |
| Parquet / ORC | yes | nothing |
| Avro | yes | nothing |
| JSON | names only | an inference pass, or `.schema()` |
| XML | names only | `rowTag`, and dotted paths for nesting |
| CSV | nothing | `header`, and `inferSchema` or `.schema()` |
| text | nothing | nothing: one `value` column per line |
| binaryFile | not applicable | nothing: you decode the bytes yourself |

**Self-describing formats** (Parquet, ORC, Avro, Delta) carry their types; you
supply a path. Parquet and ORC are columnar, so a query reads only the columns it
asks for and skips row groups by statistics. Avro is row-oriented: whole-record
reads, streaming, schema evolution carried in the file, and column pruning buys
nothing. **Delta is Parquet plus a `_delta_log`**, and the log is what turns a
pile of files into a table with ACID, time travel and concurrent writers. A bare
Parquet directory has no log, so a partial write is a partial read.

**JSON and XML** describe structure but not types. Spark infers types, which means
**reading the data twice**: once for the schema, once to load. Supplying a schema
skips the inference pass. XML has no notion of a row; `rowTag` makes it tabular,
and nested elements come back as structs reached with dotted paths.

**CSV** is text with commas. Every column is a string until you say otherwise:
`inferSchema` (a second pass), an explicit `.schema()`, or cast afterwards. Dates
and times are where CSV bites: an explicit schema only parses what the built-in
parser recognises; anything else needs `to_timestamp` with a pattern or a
`timestampFormat` option.

**text** gives one `value` column per line. **binaryFile** hands you the file and
its metadata, which is the reader for PDFs, images and proprietary formats you
decode yourself; `pathGlobFilter` and `recursiveFileLookup` pick one file type
out of a mixed drop zone.

The option names, with their defaults:

```python
(spark.read.option("header", "true")         # default false: columns become _c0, _c1, ...
           .option("inferSchema", "true")     # default false: every column STRING
           .option("timestampFormat", "dd/MM/yyyy HH:mm:ss")
           .csv(path))

spark.read.schema(SCHEMA).option("multiLine", "true").json(path)   # multiLine default false
spark.read.format("xml").option("rowTag", "scan").load(path)       # rowTag: no default, required
(spark.read.format("binaryFile").option("pathGlobFilter", "*.pdf")
           .option("recursiveFileLookup", "true").load(path))
# binaryFile columns: path STRING, modificationTime TIMESTAMP, length BIGINT, content BINARY
```

> **Measured on Free Edition:** reading or writing XML without `rowTag` fails
> with `XML_ROW_TAG_MISSING`; a write with only `rowTag` wraps the rows in a
> `<ROWS>` root element (the `rootTag` default).

### Malformed records: `mode`, `_corrupt_record`, `badRecordsPath`

Text formats meet bad rows sooner or later, and the reader decides what happens
to them. `mode` is the first knob:

| `mode` | A row that does not fit the schema |
|---|---|
| `PERMISSIVE` (default) | kept; fields that fail become null, raw text goes to `_corrupt_record` if that column is in the schema |
| `DROPMALFORMED` | dropped silently |
| `FAILFAST` | the read raises `MALFORMED_RECORD_IN_PARSING` |

```python
schema = "id INT, n STRING, _corrupt_record STRING"   # include it, or it is not filled
df = (spark.read.schema(schema)
      .option("mode", "PERMISSIVE")                     # default
      .option("columnNameOfCorruptRecord", "_corrupt_record")   # default name
      .json(path))

# Databricks only: divert bad rows to files instead of keeping them
df = spark.read.schema("id INT, n STRING").option("badRecordsPath", "/Volumes/main/raw/_bad").json(path)
# writes <badRecordsPath>/<yyyyMMddTHHmmss>/bad_records/part-... (JSON: the record, its file, the reason)
```

> **Measured on Free Edition** (serverless), three JSON lines: one good, one with
> `"id":"oops"` for an `INT`, one unparsable. `PERMISSIVE` with an explicit
> schema and no corrupt column returned all three, the type mismatch as
> `{id: null, n: 'y'}` and the broken line as all nulls, so **partly parsed rows
> look like real rows**. Adding `_corrupt_record` to the schema filled it with
> the raw text of both bad lines. Inferring the schema added `_corrupt_record`
> on its own. `DROPMALFORMED` returned only the good row. `badRecordsPath` also
> returned only the good row and wrote the other two under
> `<path>/<timestamp>/bad_records/`, so it works on serverless.

The trap: `PERMISSIVE` without `_corrupt_record` in the schema loses the evidence.
A null in `id` could be a null in the source or a value that failed to parse,
and nothing in the table tells you which. Either add the column and quarantine
rows where it is not null, or use `badRecordsPath`, which the docs call
non-transactional: bad rows are written as they are found, so a failed or
retried read can leave a partial set behind. Auto Loader has its own answer,
`_rescued_data`, which ASSOC-S2 and PRO-S3 cover.

Two traps that produce no error:

- **ANSI mode raises on a bad cast, but only if the cast runs.** A projection
  nothing consumes is pruned first, so a query that returned a number without
  complaining is not evidence that your casts are valid. Only materialising the
  values proves it.
- **`union` is positional.** Two DataFrames of the same width union whatever
  their column names say. Line sources up with `unionByName` (with
  `allowMissingColumns` when one source lacks a column), and **pin your types**
  afterwards: a union keeps the widest type it is given, so one source inferring
  a `BIGINT` silently changes the table's schema.

### Message buses: Kafka

Message buses are the other source family. The `kafka` source has a **fixed
schema** whatever the topic carries: `key` and `value` as `BINARY`, plus `topic`,
`partition`, `offset`, `timestamp` and `timestampType`, and a `headers` array
when `includeHeaders` is `true`. The payload is yours to decode: `CAST(value AS
STRING)` for text, `from_json` against a schema you supply, or `from_avro`.

```python
raw = (spark.readStream.format("kafka")
       .option("kafka.bootstrap.servers", "host1:9092,host2:9092")  # required
       .option("subscribe", "scans")          # or subscribePattern, or assign: exactly one
       .option("startingOffsets", "earliest") # default latest for a stream, earliest for batch
       .option("maxOffsetsPerTrigger", 100000) # default: no cap
       .option("failOnDataLoss", "true")      # default true
       .load())

scans = raw.select(F.col("key").cast("string").alias("scan_id"),
                   F.from_json(F.col("value").cast("string"), SCHEMA).alias("r"),
                   "topic", "partition", "offset", "timestamp").select("scan_id", "r.*", "offset")
```

```sql
-- the same source as a table-valued function, for SQL and streaming tables
CREATE OR REFRESH STREAMING TABLE bronze_scans AS
SELECT CAST(key AS STRING) AS scan_id, CAST(value AS STRING) AS payload, `offset`
FROM STREAM read_kafka(bootstrapServers => 'host1:9092', subscribe => 'scans',
                       startingOffsets => 'earliest');
```

Two things the exam likes here. **Offsets live in the checkpoint**, not in a
Kafka consumer group, so `startingOffsets` only matters the first time a query
starts; after that the checkpoint wins. And **`failOnDataLoss` defaults to
`true`**: if retention deleted offsets the checkpoint still points at, the query
fails rather than silently skipping them.

**Avro on the wire** is decoded with `from_avro`, which takes the Avro schema as
a JSON string (or a Schema Registry `subject` and `schemaRegistryAddress` on
Databricks). Its own `mode` defaults to **`FAILFAST`**: one undecodable message
raises `MALFORMED_AVRO_MESSAGE`; `PERMISSIVE` returns a record of nulls instead.

```python
from pyspark.sql.avro.functions import from_avro, to_avro

avro_schema = open("/Volumes/main/raw/schemas/scan.avsc").read()
decoded = raw.select(from_avro("value", avro_schema).alias("r")).select("r.*")
lenient = raw.select(from_avro("value", avro_schema, {"mode": "PERMISSIVE"}).alias("r"))
```

> **Measured on Free Edition:** with no broker to reach, `format("kafka")`
> still resolves its schema on serverless: the seven columns above, and
> `headers ARRAY<STRUCT<key: STRING, value: BINARY>>` with `includeHeaders`.
> `from_avro` over a `to_avro` round trip decoded correctly; five garbage bytes
> raised `MALFORMED_AVRO_MESSAGE` by default and gave a null-field record under
> `PERMISSIVE`. Offset handling and the option defaults are from the docs, since
> no topic could be read.

## One append-only table, fed by batch and stream — `PRO-S2-O2`

Append-only is not a limitation you tolerate. It is the property that lets a batch
job and a stream write to the same table without coordinating, and it is what
makes the table readable *as* a stream downstream.

- The **batch half** writes with `mode("append")`. `DESCRIBE HISTORY` records the
  operation, and an append is the one a downstream stream can follow.
- The **streaming half** is Auto Loader over the same location with
  `outputMode("append")`, so it only ever adds rows and never fights the batch
  writer. `trigger(availableNow=True)` processes everything waiting and stops,
  which is what a job wants.
- The **checkpoint** is the stream's memory: it records which files were
  consumed, so a restart resumes rather than reprocesses. Delete it and the
  stream consumes everything again. Same data, twice, no error anywhere.

![Delete the checkpoint and every file loads twice; delete the schema location and nothing reloads](visual:autoloader-checkpoint?h=900)

```python
# batch half: append, never overwrite
batch_df.write.mode("append").saveAsTable("bronze_scans")

# streaming half: Auto Loader into the same table
(spark.readStream.format("cloudFiles")
      .option("cloudFiles.format", "csv")                 # required, no default
      .option("cloudFiles.schemaLocation", f"{CKPT}/schema")
      .option("cloudFiles.maxFilesPerTrigger", 1000)      # default 1000
      .schema(SCHEMA)                                     # schemaEvolutionMode then defaults to none
      .load(landing)
      .withColumn("source_file", F.col("_metadata.file_path"))
 .writeStream
      .outputMode("append")                               # default for a non-aggregating query
      .option("checkpointLocation", f"{CKPT}/bronze")     # one per stream, never shared
      .trigger(availableNow=True)
      .toTable("bronze_scans"))
```

Tag every record with its source (`source_format`, the file it came from:
`_metadata.file_path` gives it for free). It costs one column and repays it
every time something looks wrong.

**Idempotence is your job, not the table's.** An append-only table faithfully
keeps everything it was given, duplicates included. If a source can re-deliver,
silver needs a rule for which copy wins: `dropDuplicates` on the business key
for exact repeats, or a window over the key ordered by a revision number or
arrival time for corrections. Bronze keeps the history; silver answers the
question.

**Why append-only, specifically.** A stream reading a Delta table can follow
only appends. A stream starts from a snapshot of the current version, then reads
each later commit; an update, delete, merge or overwrite committed after that
point is a version the reader cannot express as new rows, and it fails with
`DELTA_SOURCE_TABLE_IGNORE_CHANGES` rather than silently skipping. (A stream
started *after* the update reads the snapshot without complaint, which is why
the failure shows up only on a stream that was already running.) The reader
options decide what happens instead:

```python
(spark.readStream
      .option("skipChangeCommits", "true")   # default false; skip any commit that rewrites rows
      # .option("ignoreDeletes", "true")     # legacy: covers whole-partition deletes only
      # .option("ignoreChanges", "true")     # legacy: re-emit rewritten files
      .option("maxFilesPerTrigger", 1000)    # default 1000; maxBytesPerTrigger unset
      .option("startingVersion", 5)          # first run only; the checkpoint wins after that
      .table("bronze_scans"))
```

| Commit on the source | no option | `ignoreDeletes` | `skipChangeCommits` | `ignoreChanges` |
|---|---|---|---|---|
| `DELETE` of a whole partition | fails | skipped | skipped | skipped |
| `DELETE` of some rows | fails | fails | skipped | rewritten file re-emitted |
| `UPDATE` | fails | fails | skipped | rewritten file re-emitted |
| `MERGE` that updates and inserts | fails | fails | **whole commit skipped, inserts too** | rewritten file and inserts emitted |

> **Measured on Free Edition** (serverless, a three-row table, one stream per
> option started before the change): every cell above except the two
> `ignoreChanges` `DELETE` cells, which are from the docs. `ignoreChanges` is
> still accepted on serverless. After `UPDATE ... WHERE id = 1` it emitted the
> updated row *and* the two untouched rows that shared its file, so the sink
> held two copies of each unchanged row. After a `MERGE` that updated one row and inserted another,
> `skipChangeCommits` delivered nothing at all: the new row was lost with the
> update, because the commit is skipped as a unit.

Neither escape hatch is free. `skipChangeCommits` means the downstream never
learns about the change, and a `MERGE` into bronze silently drops its inserts as
well. `ignoreChanges` means unchanged rows arrive again and the downstream must
be idempotent to survive it. Keeping bronze append-only means never making that
choice under pressure.

### Append-only as a contract

Convention is one engineer away from an `UPDATE`. A table property makes the
rule enforceable: with `delta.appendOnly` set, Delta refuses every operation
that would remove or rewrite rows, so every downstream stream can trust that it
will never meet a change commit.

```sql
CREATE TABLE bronze_scans (scan_id STRING, payload STRING, source_file STRING)
TBLPROPERTIES ('delta.appendOnly' = 'true');           -- default false

ALTER TABLE bronze_scans SET TBLPROPERTIES ('delta.appendOnly' = 'true');  -- on an existing table
```

| Allowed | Refused with `DELTA_CANNOT_MODIFY_APPEND_ONLY` |
|---|---|
| `INSERT INTO`, `mode("append")`, streaming appends | `UPDATE`, `DELETE`, `TRUNCATE TABLE` |
| `MERGE` with only `WHEN NOT MATCHED THEN INSERT` | `MERGE` with `WHEN MATCHED THEN UPDATE` |
| `OPTIMIZE` (rewrites files, changes no data) | `INSERT OVERWRITE`, `mode("overwrite")` |

> **Measured on Free Edition:** each row of that table. `DESCRIBE DETAIL` lists
> `appendOnly` in `tableFeatures`. The property is a guard, not a lock: an owner
> can `SET TBLPROPERTIES ('delta.appendOnly' = 'false')` and the next `DELETE`
> succeeds.

What the contract buys and what it does not:

- **Buys:** downstream streams need no `skipChangeCommits`; an accidental
  overwrite or fix-up `UPDATE` fails loudly at the writer instead of breaking a
  reader hours later.
- **Does not buy:** idempotence. Duplicates are appends, and an append-only
  table keeps them; deduplicate in silver. Corrections arrive as new rows with a
  higher revision, not as updates.
- **Costs:** erasure. A right-to-be-forgotten delete needs the property lifted
  first (PRO-S7 covers erasure end to end), and the readers then face the change
  commit anyway.

## Further reading

Official documentation for what this section tests, one link per topic:

- [Ingest data into Databricks](https://docs.databricks.com/aws/en/ingestion/) — the menu of ingestion paths.
- [Auto Loader schema inference and evolution](https://docs.databricks.com/aws/en/ingestion/cloud-object-storage/auto-loader/schema) — `schemaEvolutionMode` and `_rescued_data`.
- [Auto Loader options](https://docs.databricks.com/aws/en/ingestion/cloud-object-storage/auto-loader/options) — every option with its default.
- [COPY INTO](https://docs.databricks.com/aws/en/ingestion/copy-into/) — the file-level idempotent alternative.
- [read_files](https://docs.databricks.com/aws/en/sql/language-manual/functions/read_files) — the table-valued function behind streaming tables.
- [JSON files](https://docs.databricks.com/aws/en/query/formats/json) — `multiLine`, corrupt records, nested fields.
- [VARIANT](https://docs.databricks.com/aws/en/semi-structured/variant) — semi-structured data without a fixed schema.
- [Delta table streaming reads and writes](https://docs.databricks.com/aws/en/structured-streaming/delta-lake) — `ignoreDeletes`, `skipChangeCommits`, `txnAppId`.
- [Delta table properties](https://docs.databricks.com/aws/en/delta/table-properties) — `delta.appendOnly` and the rest.
- [Stream processing with Apache Kafka](https://docs.databricks.com/aws/en/connect/streaming/kafka) — the source schema, options and the Kafka sink.
- [read_kafka](https://docs.databricks.com/aws/en/sql/language-manual/functions/read_kafka) — the SQL table-valued function, every option with its default.
- [Read and write streaming Avro data](https://docs.databricks.com/aws/en/structured-streaming/avro-dataframe) — `from_avro`, `to_avro`, Schema Registry and `mode`.
- [Handle bad records and files](https://docs.databricks.com/aws/en/ingestion/bad-records) — `badRecordsPath` and its output layout.
- [XML files](https://docs.databricks.com/aws/en/query/formats/xml) — `rowTag`, `rootTag` and XSD validation.
- [Binary file](https://docs.databricks.com/aws/en/query/formats/binary) — the four columns and `pathGlobFilter`.

Videos for another angle on the hard parts (channel, length):

- [Auto Loader in Databricks: schema evolution modes and file detection modes](https://www.youtube.com/watch?v=g7d1U2_dWS8) — Ease With Data, 23 min. The options this section keeps naming.
- [Stop Building Batch Jobs! Use Databricks Auto Loader Instead](https://www.youtube.com/watch?v=YHJQ5HmlclA) — Data Analytics Talks, 12 min. Incremental ingestion argued from cost.
