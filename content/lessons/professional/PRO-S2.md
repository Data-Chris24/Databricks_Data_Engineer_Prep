# Data Ingestion & Acquisition — 7%

A small section with one organising question: **does the file tell you its own
schema?** Cost, safety and which reader options you must supply all follow from
the answer. The second objective is the shape of a landing table that batch and
streaming writers can share.

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

Message buses (Kafka and the like) are the other source family: the `kafka`
source yields `key`, `value` and metadata columns as bytes; the payload is decoded
with `from_json` or `from_avro` against a schema you supply.

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

Tag every record with its source (`source_format`, the file it came from). It
costs one column and repays it every time something looks wrong.

**Idempotence is your job, not the table's.** An append-only table faithfully
keeps everything it was given, duplicates included. If a source can re-deliver,
silver needs a rule for which copy wins: `dropDuplicates` on the business key
for exact repeats, or a window over the key ordered by a revision number or
arrival time for corrections. Bronze keeps the history; silver answers the
question.

**Why append-only, specifically.** A Delta table can be read as a stream only if
its history is append-only. An update or delete produces a version the reader
cannot express as new rows, and it fails with
`DELTA_SOURCE_TABLE_IGNORE_CHANGES` rather than silently skipping. The escape
hatches cost something: `skipChangeCommits` steps over such versions (the
downstream never learns about the update); `ignoreChanges` re-emits the
rewritten files as if new (the downstream must be idempotent to survive it).
Keeping bronze append-only means never making that choice under pressure.

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

Videos for another angle on the hard parts (channel, length):

- [Auto Loader in Databricks: schema evolution modes and file detection modes](https://www.youtube.com/watch?v=g7d1U2_dWS8) — Ease With Data, 23 min. The options this section keeps naming.
- [Stop Building Batch Jobs! Use Databricks Auto Loader Instead](https://www.youtube.com/watch?v=YHJQ5HmlclA) — Data Analytics Talks, 12 min. Incremental ingestion argued from cost.
