# Auto Loader: reader options, writer options

**Objectives:** `ASSOC-S2-O3`

An Auto Loader stream reads like one chain, but it is two objects. Everything up to
`.load()` configures a **reader** (a `DataStreamReader`) and returns a streaming
DataFrame; nothing has run yet. Everything after `.writeStream` configures a
**writer** (a `DataStreamWriter`), and `.toTable()` starts the query.

**The rule:** a reader option describes **the files** (where they are, how to parse
them, what types they hold, what to do when they change). A writer option describes
**the query and the table** (where progress is remembered, whether the table may
change shape, when to run). Two shortcuts that are always right: anything starting
`cloudFiles.` is a reader option, the schema location included; and every format
option (`header`, `sep`, `multiLine`, `rowTag`, `pathGlobFilter`,
`rescuedDataColumn`) is a reader option, prefix or not.

The optional lesson `04_optional_auto_loader_deep_dive` runs every row below, and the
optional assignment `ASSOC-S2-AUTO-LOADER` practises it on five formats.

## Which side, and what the wrong side does

Measured on Free Edition serverless, 2026-10-24.

| Option | Side | Put on the other side |
|---|---|---|
| `cloudFiles.format` | reader | `CF_FILE_FORMAT_REQUIRED` at `.load()` |
| `cloudFiles.schemaLocation` | reader | `CLOUDFILES_SCHEMA_LOCATION_REQUIRED` at `.load()` |
| `cloudFiles.inferColumnTypes`, `cloudFiles.schemaHints` | reader | ignored: the types stay inferred (or `STRING`) |
| `cloudFiles.schemaEvolutionMode` | reader | ignored: the default mode applies |
| `cloudFiles.includeExistingFiles`, `cloudFiles.maxFilesPerTrigger` | reader | ignored |
| `sep`, `multiLine`, `escape`, `rowTag`… | reader | ignored, and the rows are quietly wrong |
| `pathGlobFilter` | reader | ignored: every file is loaded |
| `rescuedDataColumn` | reader | ignored: the column stays `_rescued_data` |
| `checkpointLocation` | **writer** | `STREAMING_CHECKPOINT_LOCATION_NOT_SPECIFIED` at `.toTable()`, which has already created the table, empty |
| `mergeSchema` | **writer** | on the reader: accepted, and the table still refuses a new column with `DELTA_METADATA_MISMATCH` |
| `.trigger(availableNow=True)` | **writer** (a method) | as `.option("trigger", …)`: ignored, and serverless refuses the default trigger with `INFINITE_STREAMING_TRIGGER_NOT_SUPPORTED` |

The pattern behind the table: **Spark does not reject an option an object does not
use.** The loud failures are the options something requires. The quiet ones are the
options that change how a file is parsed, and those cost you data rather than a
failed run.

A misspelt name splits the same way. Auto Loader checks its own `cloudFiles.` keys,
so `cloudFiles.schemaEvolutonMode` fails once the stream starts with
`CF_UNKNOWN_OPTION_KEYS_ERROR`. A misspelt format option such as `heder` is accepted
and ignored.

## Format by format

| Format | Options that matter | Measured trap |
|---|---|---|
| `csv` | `sep`, `header`, `multiLine`, `escape`, `nullValue`, `timestampFormat` | without `sep` on a `;` file: one column named after the whole header line, refused with `DELTA_INVALID_CHARACTERS_IN_COLUMN_NAMES`; doubled quotes stay doubled without `escape '"'`; a `DECIMAL` hint reads `12,50` as `1250.00`, unrescued (a `DOUBLE` hint rescues it) |
| `json` | `multiLine` | a pretty-printed array without it: `CF_FAILED_TO_INFER_SCHEMA`; nested fields arrive as JSON strings without `inferColumnTypes` |
| `xml` | `rowTag`, `attributePrefix` | without `rowTag`: `XML_ROW_TAG_MISSING` |
| `parquet`, `avro` | none | still need a schema location |
| `orc` | `cloudFiles.schemaEvolutionMode` = `none` | the default `addNewColumns` is refused: `CF_UNSUPPORTED_SCHEMA_EVOLUTION_MODE` |
| `text` | `wholetext` | one `value` column; parse it before `.writeStream` |
| `binaryFile` | `pathGlobFilter` | `content` holds every file's bytes; `select` it away |

Auto Loader reads a CSV's first line as the header unless told `header = false`
(measured: no `header` option gave named columns), which differs from
`spark.read.csv`.

## Evolution needs both sides

| `schemaEvolutionMode` (reader) | New column, writer `mergeSchema` on | …and off |
|---|---|---|
| `addNewColumns` (default) | fails once (`UNKNOWN_FIELD_EXCEPTION`, "automatic retry: true"), then the table gains it | fails once, then `DELTA_METADATA_MISMATCH` on every retry |
| `rescue` | never fails; the value lands in `_rescued_data` | the same |
| `failOnNewColumns` | fails every run ("automatic retry: false") | the same |
| `none` | never fails; the column is dropped silently | the same |
