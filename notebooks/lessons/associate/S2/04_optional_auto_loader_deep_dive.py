# Databricks notebook source
# MAGIC %md
# MAGIC # Auto Loader in depth — `ASSOC-S2-O3`
# MAGIC
# MAGIC > **Optional.** Lessons 01–03 cover what the exam needs, and the section's
# MAGIC > assignment does not wait for this notebook. Come here when you want to write
# MAGIC > Auto Loader code with confidence rather than by pattern-matching.
# MAGIC
# MAGIC Lesson 02 used one stream with seven options and said two of them were "reader"
# MAGIC and "writer" settings. This notebook takes that apart:
# MAGIC
# MAGIC 1. **Two objects, two sets of options**: which option goes where, and why.
# MAGIC 2. **Wrong side, on purpose**: every mistake run for real, with the error it gives
# MAGIC    (or, worse, the silence).
# MAGIC 3. **Format by format**: CSV, JSON, Parquet, Avro, ORC, text, XML and binaryFile,
# MAGIC    each with the options that matter for it.
# MAGIC 4. **Schema**: inferred, hinted or declared, and what `_rescued_data` catches.
# MAGIC 5. **Schema evolution, mode by mode**: all four modes, with and without the
# MAGIC    writer's `mergeSchema`.
# MAGIC 6. **Triggers**: what serverless will and will not run.
# MAGIC 7. **The checkpoint and the schema location**: what is inside each, and what
# MAGIC    deleting one does.
# MAGIC
# MAGIC Every error message quoted here was produced by running the code on Free Edition
# MAGIC serverless, and the cells that produce them are below: run them and see.
# MAGIC
# MAGIC **Exercises** are marked ✍️. Each has an empty cell for your code, a check cell
# MAGIC that tells you how you did (and stays quiet if you skip it), and a worked answer
# MAGIC after it. Try before you scroll.
# MAGIC
# MAGIC When you are done, the optional assignment `ASSOC-S2-AUTO-LOADER` asks you to
# MAGIC ingest five sources in five formats from scratch.

# COMMAND ----------

CATALOG, SCHEMA = "workspace", "de_prep"
SRC = f"/Volumes/{CATALOG}/{SCHEMA}/raw/s2_al_teach"     # the sources: read only
WORK = f"/Volumes/{CATALOG}/{SCHEMA}/raw/s2_al_lesson"   # this lesson's scratch

spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")

# The deep-dive sources came with the section's datasets. A workspace that
# generated them before this lesson existed has no s2_al_teach yet: the generator
# rewrites every S2 file byte for byte, so running it again is safe.
try:
    dbutils.fs.ls(SRC)
except Exception:
    print("s2_al_teach not found - running the ASSOC-S2 dataset generator (a few minutes)")
    dbutils.notebook.run("../../../datasets/generate_ASSOC-S2", 1800)

dbutils.fs.rm(WORK, True)
for row in spark.sql(f"SHOW TABLES IN {CATALOG}.{SCHEMA} LIKE 'al_lesson_*'").collect():
    spark.sql(f"DROP TABLE IF EXISTS {row.tableName}")


def fresh(name):
    """A new, empty scratch folder for one stream: its own checkpoint and schema location."""
    path = f"{WORK}/{name}"
    dbutils.fs.rm(path, True)
    return path


def expect_error(build, expected):
    """Run a cell that should fail before its stream starts, and show the error class.

    Errors raised while setting a stream up (a missing option, an unsupported
    trigger) can be caught like any other. A stream that fails *while running*
    cannot: it fails the notebook even when caught, which is why section 5 runs
    those in a helper notebook instead.
    """
    try:
        build()
    except Exception as e:
        msg = str(e).split("JVM stacktrace")[0].strip()
        got = msg.split("]")[0].lstrip("[") if msg.startswith("[") else type(e).__name__
        print(f"{'as expected' if got == expected else 'UNEXPECTED'}: {got}\n\n{msg[:600]}")
        return got
    print(f"UNEXPECTED: no error (expected {expected})")
    return None


for f in dbutils.fs.ls(SRC):
    print(f.name)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Two objects, two sets of options
# MAGIC
# MAGIC An Auto Loader pipeline looks like one long chain, which is what makes the split
# MAGIC confusing. It is really two objects joined by `.writeStream`:
# MAGIC
# MAGIC ```
# MAGIC spark.readStream.format("cloudFiles")   ┐
# MAGIC     .option(...)  ← READER options      │  a DataStreamReader:
# MAGIC     .load(path)                         ┘  .load() returns a streaming DataFrame
# MAGIC                                             (nothing has run yet)
# MAGIC   .writeStream                          ┐
# MAGIC     .option(...)  ← WRITER options      │  a DataStreamWriter:
# MAGIC     .trigger(...)                       │  .toTable() starts the query
# MAGIC     .toTable(name)                      ┘
# MAGIC ```
# MAGIC
# MAGIC **The rule:** an option on the reader describes **the files**: where they are,
# MAGIC how to parse them, what types they hold, what to do when they change. An option
# MAGIC on the writer describes **the query and the table**: where progress is
# MAGIC remembered, whether the table may change shape, when to run.
# MAGIC
# MAGIC Two shortcuts that are always right:
# MAGIC
# MAGIC - **Anything starting `cloudFiles.` is a reader option.** Including the two
# MAGIC   *locations*: `cloudFiles.schemaLocation` is about the files' schema, so it is on
# MAGIC   the reader, even though it feels like the checkpoint's sibling.
# MAGIC - **Every format option is a reader option**, prefix or not: `header`, `sep`,
# MAGIC   `multiLine`, `escape`, `rowTag`, `pathGlobFilter`, `rescuedDataColumn`.
# MAGIC
# MAGIC Pull the chain apart and you can see the two objects:

# COMMAND ----------

reader = (spark.readStream
    .format("cloudFiles")
    .option("cloudFiles.format", "text")
    .option("cloudFiles.schemaLocation", f"{fresh('anatomy')}/_schema"))
df = reader.load(f"{SRC}/text")
writer = df.writeStream.option("checkpointLocation", f"{WORK}/anatomy/_checkpoint").trigger(availableNow=True)

print("reader :", type(reader).__name__)
print("df     :", type(df).__name__, "- streaming:", df.isStreaming, "- columns:", df.columns)
print("writer :", type(writer).__name__)

# Only now does anything run.
writer.toTable("al_lesson_anatomy").awaitTermination()
print("rows   :", spark.table("al_lesson_anatomy").count())

# COMMAND ----------

# MAGIC %md
# MAGIC The DataFrame in the middle is ordinary: you can `select`, `withColumn` or
# MAGIC `filter` it before `.writeStream`, which is where a transformation goes.
# MAGIC
# MAGIC ### The reference table
# MAGIC
# MAGIC "Wrong side" is what happened when the option was put on the other object,
# MAGIC measured on Free Edition serverless. Section 2 runs each one.
# MAGIC
# MAGIC | Option | Side | Controls | Put on the wrong side |
# MAGIC |---|---|---|---|
# MAGIC | `cloudFiles.format` | reader | the file format | `CF_FILE_FORMAT_REQUIRED` at `.load()` |
# MAGIC | `cloudFiles.schemaLocation` | reader | where the inferred schema and its versions live | `CLOUDFILES_SCHEMA_LOCATION_REQUIRED` at `.load()` |
# MAGIC | `cloudFiles.inferColumnTypes` | reader | real types for CSV/JSON/XML instead of `STRING` | ignored: every column is `STRING` |
# MAGIC | `cloudFiles.schemaHints` | reader | force the type of named columns | ignored: inferred types win |
# MAGIC | `cloudFiles.schemaEvolutionMode` | reader | what a new column in the files does | ignored: the default mode applies |
# MAGIC | `cloudFiles.maxFilesPerTrigger` | reader | files per micro-batch | ignored: up to 1,000 files per batch |
# MAGIC | `cloudFiles.includeExistingFiles` | reader | whether files already present are loaded | ignored: they are loaded |
# MAGIC | `header`, `sep`, `multiLine`, `escape`, `rowTag`… | reader | how one file is parsed | ignored, and the data is quietly wrong (section 2) |
# MAGIC | `pathGlobFilter` | reader | which file names are loaded | ignored: every file is loaded |
# MAGIC | `rescuedDataColumn` | reader | the name of the rescue column | ignored: it stays `_rescued_data` |
# MAGIC | `checkpointLocation` | **writer** | which files and batches are done | `STREAMING_CHECKPOINT_LOCATION_NOT_SPECIFIED` at `.toTable()` |
# MAGIC | `mergeSchema` | **writer** | whether the Delta table may gain columns | on the reader: accepted, changes nothing, the write fails `DELTA_METADATA_MISMATCH` |
# MAGIC | `.trigger(...)` | **writer** (a method) | when and how long the query runs | as `.option("trigger", …)`: ignored, the default trigger is refused (section 6) |
# MAGIC | `.outputMode(...)` | **writer** (a method) | append (the default), complete or update | `"complete"` with no aggregation: `STREAMING_OUTPUT_MODE.UNSUPPORTED_OPERATION` |
# MAGIC | `.toTable(name)` | **writer** (a method) | the target table, and starts the query | — |
# MAGIC
# MAGIC Read the last column again. **Four of the reader-side mistakes raise nothing**:
# MAGIC Spark does not reject an option it does not use, so an option on the wrong
# MAGIC object is simply never read. That is why the split is worth learning rather than
# MAGIC discovering: the error does not always come.

# COMMAND ----------

# MAGIC %md
# MAGIC ### ✍️ Exercise 1: sort the options
# MAGIC
# MAGIC Without scrolling back to the table, mark each option `"reader"` or `"writer"`.
# MAGIC Run the check cell after.

# COMMAND ----------

my_sort = {
    "checkpointLocation": "",
    "cloudFiles.schemaLocation": "",
    "cloudFiles.format": "",
    "mergeSchema": "",
    "rescuedDataColumn": "",
    "cloudFiles.schemaEvolutionMode": "",
    "multiLine": "",
    "cloudFiles.schemaHints": "",
    "pathGlobFilter": "",
    "rowTag": "",
}

# COMMAND ----------

ANSWER_SORT = {
    "checkpointLocation": "writer", "cloudFiles.schemaLocation": "reader",
    "cloudFiles.format": "reader", "mergeSchema": "writer",
    "rescuedDataColumn": "reader", "cloudFiles.schemaEvolutionMode": "reader",
    "multiLine": "reader", "cloudFiles.schemaHints": "reader",
    "pathGlobFilter": "reader", "rowTag": "reader",
}
if not any(v.strip() for v in my_sort.values()):
    print("Not attempted yet: fill in my_sort above and run this cell again.")
else:
    wrong = {k: v for k, v in my_sort.items() if v.strip().lower() != ANSWER_SORT[k]}
    print(f"{len(ANSWER_SORT) - len(wrong)} of {len(ANSWER_SORT)} right")
    for k in wrong:
        print(f"  {k}: it is a {ANSWER_SORT[k]} option")
    if "cloudFiles.schemaLocation" in wrong:
        print("\nThe schema location describes the files' schema, so it is read with the files.")
    if "mergeSchema" in wrong:
        print("\nmergeSchema decides whether the Delta *table* may gain columns: a writer concern.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Wrong side, on purpose
# MAGIC
# MAGIC The source for this section is `s2_al_teach/csv/`: coffee-shop orders, exported
# MAGIC with `;` between fields and a gift note that sometimes runs over two lines.
# MAGIC Look at it first:

# COMMAND ----------

print(dbutils.fs.head(f"{SRC}/csv/orders_2026-03-01.csv", 700))

# COMMAND ----------

# MAGIC %md
# MAGIC Here is the correct stream, so the mistakes below have something to differ from.
# MAGIC Every line is labelled with the object it is on.

# COMMAND ----------

w = fresh("csv_right")
(spark.readStream.format("cloudFiles")
    .option("cloudFiles.format", "csv")                     # reader: the format
    .option("cloudFiles.schemaLocation", f"{w}/_schema")    # reader: where the schema is kept
    .option("sep", ";")                                     # reader: a CSV option
    .option("multiLine", "true")                            # reader: a CSV option
    .option("escape", '"')                                  # reader: a CSV option (see section 3)
    .option("cloudFiles.inferColumnTypes", "true")          # reader: real types, not all STRING
    .load(f"{SRC}/csv")
 .writeStream
    .option("checkpointLocation", f"{w}/_checkpoint")       # writer: what is done
    .trigger(availableNow=True)                             # writer: process what is there, stop
    .toTable("al_lesson_orders")
    .awaitTermination())

display(spark.table("al_lesson_orders").orderBy("order_id").limit(5))
print("rows:", spark.table("al_lesson_orders").count())

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2a. The checkpoint on the reader
# MAGIC
# MAGIC The reader accepts `checkpointLocation` without complaint: it is just a key it
# MAGIC never reads. The failure comes at `.toTable()`, when the writer finds it has
# MAGIC nowhere to record progress, and by then `.toTable()` has already **created the
# MAGIC table**, empty, with the stream's schema. A later stream into the same table
# MAGIC then meets a schema it did not choose: one more reason to give every stream its
# MAGIC own table and its own folders.

# COMMAND ----------

def checkpoint_on_reader():
    w = fresh("wrong_checkpoint")
    (spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "csv")
        .option("cloudFiles.schemaLocation", f"{w}/_schema")
        .option("sep", ";")
        .option("checkpointLocation", f"{w}/_checkpoint")   # WRONG: this is a writer option
        .load(f"{SRC}/csv")
     .writeStream
        .trigger(availableNow=True)
        .toTable("al_lesson_wrong_checkpoint_on_reader")
        .awaitTermination())


expect_error(checkpoint_on_reader, "STREAMING_CHECKPOINT_LOCATION_NOT_SPECIFIED")
left = "al_lesson_wrong_checkpoint_on_reader"
if spark.catalog.tableExists(left):
    print(f"\nThe stream never ran, but {left} exists, with {spark.table(left).count()} rows:")
    print(spark.table(left).schema.simpleString())
else:
    print(f"\n{left} was not created")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2b. The schema location on the writer
# MAGIC
# MAGIC The mirror image, and the one people actually write, because "the two locations"
# MAGIC feel like a pair. This time it fails at `.load()`, before the writer exists: the
# MAGIC reader has to infer a schema and has nowhere to keep it.

# COMMAND ----------

def schema_location_on_writer():
    w = fresh("wrong_schema_location")
    (spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "csv")
        .option("sep", ";")
        .load(f"{SRC}/csv")
     .writeStream
        .option("checkpointLocation", f"{w}/_checkpoint")
        .option("cloudFiles.schemaLocation", f"{w}/_schema")   # WRONG: this is a reader option
        .trigger(availableNow=True)
        .toTable("al_lesson_wrong_schema_location_on_writer")
        .awaitTermination())


expect_error(schema_location_on_writer, "CLOUDFILES_SCHEMA_LOCATION_REQUIRED")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2c. The format on the writer
# MAGIC
# MAGIC Same shape: the reader needs it to do anything at all.

# COMMAND ----------

def format_on_writer():
    w = fresh("wrong_format")
    (spark.readStream.format("cloudFiles")
        .option("cloudFiles.schemaLocation", f"{w}/_schema")
        .load(f"{SRC}/csv")
     .writeStream
        .option("cloudFiles.format", "csv")                   # WRONG: this is a reader option
        .option("checkpointLocation", f"{w}/_checkpoint")
        .trigger(availableNow=True)
        .toTable("al_lesson_wrong_format_on_writer")
        .awaitTermination())


expect_error(format_on_writer, "CF_FILE_FORMAT_REQUIRED")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2d. A parsing option on the writer: no error at all
# MAGIC
# MAGIC Now the dangerous kind. Move `multiLine` and `escape` to the writer and nothing
# MAGIC fails: the writer ignores them and the reader parses the file one physical line
# MAGIC at a time. A gift note that spans two lines becomes two rows, and the second
# MAGIC one is garbage. Compare the row count with the 80 above.

# COMMAND ----------

w = fresh("wrong_multiline")
(spark.readStream.format("cloudFiles")
    .option("cloudFiles.format", "csv")
    .option("cloudFiles.schemaLocation", f"{w}/_schema")
    .option("sep", ";")
    .load(f"{SRC}/csv")
 .writeStream
    .option("checkpointLocation", f"{w}/_checkpoint")
    .option("multiLine", "true")                           # WRONG: ignored here
    .option("escape", '"')                                 # WRONG: ignored here
    .trigger(availableNow=True)
    .toTable("al_lesson_wrong_multiline")
    .awaitTermination())

broken = spark.table("al_lesson_wrong_multiline")
print("rows:", broken.count(), "(the right answer is 80)")
display(broken.where("NOT order_id LIKE 'ORD-%' OR store IS NULL"))

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2e. `sep` forgotten (or on the writer)
# MAGIC
# MAGIC Without `sep` the reader splits on commas, finds none, and sees one column whose
# MAGIC name is the whole header line. Delta refuses that name: the error is about
# MAGIC column names, a long way from the real cause.

# COMMAND ----------

def no_sep():
    w = fresh("wrong_sep")
    (spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "csv")
        .option("cloudFiles.schemaLocation", f"{w}/_schema")
        .load(f"{SRC}/csv")
     .writeStream
        .option("checkpointLocation", f"{w}/_checkpoint")
        .option("sep", ";")                                # WRONG: ignored here
        .trigger(availableNow=True)
        .toTable("al_lesson_wrong_no_sep")
        .awaitTermination())


expect_error(no_sep, "DELTA_INVALID_CHARACTERS_IN_COLUMN_NAMES")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2f. `trigger` as an option
# MAGIC
# MAGIC `trigger` is a method on the writer, not an option. Written as one, it is
# MAGIC ignored, the query gets the default trigger (run forever, a batch as soon as the
# MAGIC last one ends), and serverless refuses to run a query that never stops.

# COMMAND ----------

def trigger_as_option():
    w = fresh("wrong_trigger")
    (spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "text")
        .option("cloudFiles.schemaLocation", f"{w}/_schema")
        .load(f"{SRC}/text")
     .writeStream
        .option("checkpointLocation", f"{w}/_checkpoint")
        .option("trigger", "availableNow")                 # WRONG: not an option
        .toTable("al_lesson_wrong_trigger_as_option")
        .awaitTermination())


expect_error(trigger_as_option, "INFINITE_STREAMING_TRIGGER_NOT_SUPPORTED")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2g. The quiet ones, all at once
# MAGIC
# MAGIC Each of these reader options, put on the writer, raises nothing. The cell runs
# MAGIC every one and shows what the table looks like instead.

# COMMAND ----------

def on_the_writer(name, folder, fmt, reader_opts, writer_opt):
    """The stream with one reader option moved to the writer; returns the table."""
    w = fresh(f"quiet_{name}")
    r = (spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", fmt)
        .option("cloudFiles.schemaLocation", f"{w}/_schema"))
    for k, v in reader_opts.items():
        r = r.option(k, v)
    (r.load(f"{SRC}/{folder}")
     .writeStream
        .option("checkpointLocation", f"{w}/_checkpoint")
        .option(*writer_opt)                               # WRONG: a reader option
        .trigger(availableNow=True)
        .toTable(f"al_lesson_quiet_{name}")
        .awaitTermination())
    return spark.table(f"al_lesson_quiet_{name}")


CSV = {"sep": ";", "multiLine": "true", "escape": '"'}
quiet = []

t = on_the_writer("infer", "csv", "csv", CSV, ("cloudFiles.inferColumnTypes", "true"))
quiet.append(("cloudFiles.inferColumnTypes", "quantity is " + dict(t.dtypes)["quantity"], "int"))

t = on_the_writer("hints", "csv", "csv", {**CSV, "cloudFiles.inferColumnTypes": "true"},
                  ("cloudFiles.schemaHints", "unit_price DECIMAL(10,2)"))
quiet.append(("cloudFiles.schemaHints", "unit_price is " + dict(t.dtypes)["unit_price"], "decimal(10,2)"))

t = on_the_writer("glob", "binary/receipts", "binaryFile", {}, ("pathGlobFilter", "*.png"))
quiet.append(("pathGlobFilter", f"{t.count()} files loaded, README.txt among them", "6 PNGs"))

t = on_the_writer("rescue_name", "csv", "csv", {**CSV, "cloudFiles.inferColumnTypes": "true"},
                  ("rescuedDataColumn", "_bad_values"))
quiet.append(("rescuedDataColumn", "rescue column is " + [c for c in t.columns if c.startswith("_")][0], "_bad_values"))

t = on_the_writer("existing", "text", "text", {}, ("cloudFiles.includeExistingFiles", "false"))
quiet.append(("cloudFiles.includeExistingFiles", f"{t.count()} rows loaded", "0 rows"))

display(spark.createDataFrame(quiet, "option_on_the_writer STRING, what_happened STRING, on_the_reader_it_would_be STRING"))

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2h. `mergeSchema` on the reader, and a typo in an option name
# MAGIC
# MAGIC `mergeSchema` on the reader is the same kind of silence, and the most common
# MAGIC one, but it stays silent until a column arrives: section 5 shows that failure.
# MAGIC
# MAGIC A misspelt option name splits the same way the options do:
# MAGIC
# MAGIC - **A `cloudFiles.` key is checked.** Auto Loader knows its own options, so
# MAGIC   `cloudFiles.schemaEvolutonMode` fails, once the stream starts, with
# MAGIC   `CF_UNKNOWN_OPTION_KEYS_ERROR` ("Found unknown option keys:
# MAGIC   cloudFiles.schemaevolutonmode"). Section 5 runs it.
# MAGIC - **A format option is not.** `.option("heder", "true")` is accepted and ignored,
# MAGIC   like every other key the reader does not use.

# MAGIC ## 3. Format by format
# MAGIC
# MAGIC `cloudFiles.format` takes the same names as `spark.read.format`, and the format
# MAGIC options are the same as for a batch read. What changes per format is which of
# MAGIC Auto Loader's own options matter.
# MAGIC
# MAGIC | Format | Schema comes from | Options that matter | Watch out for |
# MAGIC |---|---|---|---|
# MAGIC | `csv` | inference over a sample | `sep`, `header`, `multiLine`, `escape`, `quote`, `nullValue`, `timestampFormat` | all `STRING` without `inferColumnTypes`; doubled quotes need `escape '"'` |
# MAGIC | `json` | inference | `multiLine` (one document per file, or an array) | nested fields arrive as JSON *strings* without `inferColumnTypes` |
# MAGIC | `xml` | inference | `rowTag` (required), `attributePrefix` | attributes become `_name` columns |
# MAGIC | `parquet`, `avro` | the files | none needed | still needs a schema location |
# MAGIC | `orc` | the files | `cloudFiles.schemaEvolutionMode` = `none` | the default evolution mode is refused |
# MAGIC | `text` | fixed: `value STRING` | `wholetext` (one row per file) | parse the line yourself |
# MAGIC | `binaryFile` | fixed: `path`, `modificationTime`, `length`, `content` | `pathGlobFilter` | `content` holds the whole file |

# COMMAND ----------

# MAGIC %md
# MAGIC ### CSV: types, hints and quoting
# MAGIC
# MAGIC In the stream from section 2, `unit_price` came back as `STRING`, not a number.
# MAGIC Inference saw two values that are not plain numbers (`TBC`, and `12,50` with a
# MAGIC decimal comma) and widened the whole column to text. The gift notes are intact
# MAGIC because that stream set `escape` to `"`: without it, Spark's CSV reader escapes
# MAGIC with `\`, and a note written `"Ring twice; say ""hi"""` keeps its doubled quotes.

# COMMAND ----------

display(spark.sql("""
    SELECT order_id, unit_price, gift_note FROM al_lesson_orders
    WHERE unit_price NOT RLIKE '^[0-9]+\\.[0-9]+$' OR gift_note LIKE '%"%' OR gift_note LIKE '%\n%'
    ORDER BY order_id"""))
print(spark.table("al_lesson_orders").schema.simpleString())

# COMMAND ----------

# MAGIC %md
# MAGIC ### ✍️ Exercise 2: make `unit_price` a `DECIMAL(10,2)`
# MAGIC
# MAGIC Write the CSV stream again into a table called `al_lesson_ex_orders`, so that
# MAGIC `unit_price` is `DECIMAL(10,2)` and the `TBC` is not lost. One reader option does
# MAGIC the typing (hint: it takes a column list in SQL syntax); the rescue column does
# MAGIC the rest without you asking. Use `fresh("ex_orders")` for a scratch folder. Then
# MAGIC read what the check says about `ORD-700053`, whose price in the file is `12,50`.

# COMMAND ----------

# your stream here


# COMMAND ----------

if not spark.catalog.tableExists("al_lesson_ex_orders"):
    print("Not attempted yet: write the stream above and run this cell again.")
else:
    t = spark.table("al_lesson_ex_orders")
    types = dict(t.dtypes)
    print("unit_price is", types.get("unit_price"), "(want decimal(10,2))")
    print("rows:", t.count(), "(want 80)")
    if "_rescued_data" in t.columns:
        print("rows with _rescued_data:", t.where("_rescued_data IS NOT NULL").count(), "(want 1: the TBC)")
    else:
        print("no _rescued_data column: did you supply a full schema instead of a hint?")
    comma = t.where("order_id = 'ORD-700053'").select("unit_price").first()
    print("ORD-700053, '12,50' in the file, is now:", comma[0] if comma else "missing", "- see the worked answer")

# COMMAND ----------

# MAGIC %md
# MAGIC **Worked answer.** `cloudFiles.schemaHints` overrides inference for the columns it
# MAGIC names and leaves the rest inferred. A value that does not fit the hinted type
# MAGIC becomes `NULL` in the column and is kept, with the file it came from, in
# MAGIC `_rescued_data`.

# COMMAND ----------

w = fresh("orders_hinted")
(spark.readStream.format("cloudFiles")
    .option("cloudFiles.format", "csv")
    .option("cloudFiles.schemaLocation", f"{w}/_schema")
    .option("sep", ";")
    .option("multiLine", "true")
    .option("escape", '"')
    .option("cloudFiles.inferColumnTypes", "true")
    .option("cloudFiles.schemaHints", "unit_price DECIMAL(10,2)")
    .load(f"{SRC}/csv")
 .writeStream
    .option("checkpointLocation", f"{w}/_checkpoint")
    .trigger(availableNow=True)
    .toTable("al_lesson_orders_hinted")
    .awaitTermination())

display(spark.sql("""
    SELECT order_id, unit_price, _rescued_data FROM al_lesson_orders_hinted
    WHERE _rescued_data IS NOT NULL OR order_id = 'ORD-700053' ORDER BY order_id"""))

# COMMAND ----------

# MAGIC %md
# MAGIC Only `TBC` was rescued. `12,50` **fitted**: parsing text as a `DECIMAL` accepts
# MAGIC `,` as a thousands separator, so it is now `1250.00`, a hundred times the real
# MAGIC price, with no rescue and no error. The same column hinted `DOUBLE` rejects
# MAGIC `12,50` and rescues it (measured on Free Edition). The rescue column catches
# MAGIC what does not parse; it cannot catch what parses wrongly. Know your source's
# MAGIC number format, and check the range of what you loaded:

# COMMAND ----------

display(spark.sql("SELECT min(unit_price), max(unit_price) FROM al_lesson_orders_hinted"))

# COMMAND ----------

# MAGIC %md
# MAGIC ### JSON: one array per file, and nested types
# MAGIC
# MAGIC Without `multiLine`, Auto Loader expects one JSON document per line. These files
# MAGIC are one pretty-printed array each, so it cannot infer anything at all:

# COMMAND ----------

print(dbutils.fs.head(f"{SRC}/json/customers_part1.json", 300))


def json_without_multiline():
    w = fresh("json_wrong")
    (spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "json")
        .option("cloudFiles.schemaLocation", f"{w}/_schema")
        .load(f"{SRC}/json")
     .writeStream.option("checkpointLocation", f"{w}/_checkpoint")
        .trigger(availableNow=True).toTable("al_lesson_wrong_json_without_multiline").awaitTermination())


expect_error(json_without_multiline, "CF_FAILED_TO_INFER_SCHEMA.OTHER")

# COMMAND ----------

# MAGIC %md
# MAGIC ### ✍️ Exercise 3: customers with real nested types
# MAGIC
# MAGIC Load `s2_al_teach/json/` into `al_lesson_ex_customers` so that `address` is a
# MAGIC `STRUCT` you can query as `address.city`, and `tags` is an `ARRAY<STRING>`. Two
# MAGIC reader options beyond the basics.

# COMMAND ----------

# your stream here


# COMMAND ----------

if not spark.catalog.tableExists("al_lesson_ex_customers"):
    print("Not attempted yet: write the stream above and run this cell again.")
else:
    types = dict(spark.table("al_lesson_ex_customers").dtypes)
    print("address:", types.get("address"), "(want struct<city:string,postcode:string>)")
    print("tags   :", types.get("tags"), "(want array<string>)")
    print("rows   :", spark.table("al_lesson_ex_customers").count(), "(want 24)")

# COMMAND ----------

# MAGIC %md
# MAGIC **Worked answer.** First without `inferColumnTypes`, to see what you would get:
# MAGIC every field, nested ones included, as a `STRING` of JSON.

# COMMAND ----------

def customers(name, infer):
    w = fresh(name)
    (spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "json")
        .option("cloudFiles.schemaLocation", f"{w}/_schema")
        .option("multiLine", "true")
        .option("cloudFiles.inferColumnTypes", infer)
        .load(f"{SRC}/json")
     .writeStream.option("checkpointLocation", f"{w}/_checkpoint")
        .trigger(availableNow=True).toTable(f"al_lesson_{name}").awaitTermination())
    print(f"inferColumnTypes={infer}:", spark.table(f"al_lesson_{name}").schema.simpleString())


customers("customers_strings", "false")
customers("customers_typed", "true")
display(spark.sql("SELECT customer_id, address.city, tags FROM al_lesson_customers_typed ORDER BY customer_id LIMIT 5"))

# COMMAND ----------

# MAGIC %md
# MAGIC ### Parquet and Avro: the files carry their schema
# MAGIC
# MAGIC Self-describing formats need no inference and no type options. They still need
# MAGIC `cloudFiles.schemaLocation`: Auto Loader records the schema there so it can tell
# MAGIC when a later file differs. And they still get `_rescued_data`, for a file whose
# MAGIC types disagree with the recorded schema.

# COMMAND ----------

def self_describing(fmt, folder):
    w = fresh(fmt)
    (spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", fmt)
        .option("cloudFiles.schemaLocation", f"{w}/_schema")
        .load(f"{SRC}/{folder}")
     .writeStream.option("checkpointLocation", f"{w}/_checkpoint")
        .trigger(availableNow=True).toTable(f"al_lesson_{fmt}").awaitTermination())
    print(f"{fmt:8}", spark.table(f"al_lesson_{fmt}").schema.simpleString())


self_describing("parquet", "parquet")
self_describing("avro", "avro")


def parquet_without_schema_location():
    w = fresh("parquet_no_location")
    (spark.readStream.format("cloudFiles").option("cloudFiles.format", "parquet")
        .load(f"{SRC}/parquet")
     .writeStream.option("checkpointLocation", f"{w}/_checkpoint")
        .trigger(availableNow=True).toTable("al_lesson_wrong_parquet_without_schema_location").awaitTermination())


expect_error(parquet_without_schema_location, "CLOUDFILES_SCHEMA_LOCATION_REQUIRED")

# COMMAND ----------

# MAGIC %md
# MAGIC ### ORC: the default evolution mode is refused
# MAGIC
# MAGIC Without a schema, Auto Loader's evolution mode defaults to `addNewColumns`, and
# MAGIC ORC does not support it. The error says what to do.

# COMMAND ----------

def orc(mode=None):
    w = fresh("orc")
    r = (spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "orc")
        .option("cloudFiles.schemaLocation", f"{w}/_schema"))
    if mode:
        r = r.option("cloudFiles.schemaEvolutionMode", mode)
    (r.load(f"{SRC}/orc")
     .writeStream.option("checkpointLocation", f"{w}/_checkpoint")
        .trigger(availableNow=True).toTable("al_lesson_orc").awaitTermination())


expect_error(orc, "CF_UNSUPPORTED_SCHEMA_EVOLUTION_MODE")
orc(mode="none")
print(spark.table("al_lesson_orc").schema.simpleString())

# COMMAND ----------

# MAGIC %md
# MAGIC Note the schema: no `_rescued_data`. Mode `none` turns the rescue column off
# MAGIC unless you name one with `rescuedDataColumn`.
# MAGIC
# MAGIC ### Text: one line, one row
# MAGIC
# MAGIC The schema is fixed, `value STRING`, so there is nothing to infer, but the schema
# MAGIC location is still required. Parsing is a transformation on the DataFrame, between
# MAGIC `.load()` and `.writeStream`: the place it always goes.

# COMMAND ----------

from pyspark.sql import functions as F

w = fresh("text")
till = (spark.readStream.format("cloudFiles")
    .option("cloudFiles.format", "text")
    .option("cloudFiles.schemaLocation", f"{w}/_schema")
    .load(f"{SRC}/text"))

pattern = r"^(\S+) (\w+) (till-\d) (.+)$"
parsed = till.select(
    F.to_timestamp(F.regexp_extract("value", pattern, 1)).alias("logged_at"),
    F.regexp_extract("value", pattern, 2).alias("level"),
    F.regexp_extract("value", pattern, 3).alias("till"),
    F.regexp_extract("value", pattern, 4).alias("event"),
    F.col("_metadata.file_name").alias("source_file"),       # which file each row came from
)

(parsed.writeStream.option("checkpointLocation", f"{w}/_checkpoint")
    .trigger(availableNow=True).toTable("al_lesson_till").awaitTermination())
display(spark.sql("SELECT level, count(*) AS n FROM al_lesson_till GROUP BY level ORDER BY n DESC"))

# COMMAND ----------

# MAGIC %md
# MAGIC `wholetext` makes each *file* one row instead, which is what you want for a
# MAGIC document rather than a log.
# MAGIC
# MAGIC ### XML: `rowTag` says what one row is
# MAGIC
# MAGIC An XML file is one document; `rowTag` names the element that becomes a row.
# MAGIC Attributes become columns prefixed with `_` (change it with `attributePrefix`).
# MAGIC Without `rowTag` the read fails before it starts.

# COMMAND ----------

print(dbutils.fs.head(f"{SRC}/xml/suppliers.xml", 300))


def suppliers(row_tag=None):
    w = fresh("xml")
    r = (spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "xml")
        .option("cloudFiles.schemaLocation", f"{w}/_schema")
        .option("cloudFiles.inferColumnTypes", "true"))
    if row_tag:
        r = r.option("rowTag", row_tag)
    (r.load(f"{SRC}/xml")
     .writeStream.option("checkpointLocation", f"{w}/_checkpoint")
        .trigger(availableNow=True).toTable("al_lesson_suppliers").awaitTermination())


expect_error(suppliers, "XML_ROW_TAG_MISSING")
suppliers(row_tag="supplier")
display(spark.table("al_lesson_suppliers"))

# COMMAND ----------

# MAGIC %md
# MAGIC ### ✍️ Exercise 4: receipt images, without the images
# MAGIC
# MAGIC `s2_al_teach/binary/receipts/` holds six PNG receipts and a `README.txt`. Load
# MAGIC into `al_lesson_ex_receipts` one row per **PNG only**, with the columns `path`,
# MAGIC `modificationTime` and `length` but **not** `content` (the bytes are better left
# MAGIC in the volume). One reader option and one DataFrame step.

# COMMAND ----------

# your stream here


# COMMAND ----------

if not spark.catalog.tableExists("al_lesson_ex_receipts"):
    print("Not attempted yet: write the stream above and run this cell again.")
else:
    t = spark.table("al_lesson_ex_receipts")
    print("columns:", t.columns, "(want path, modificationTime, length)")
    print("rows   :", t.count(), "(want 6)")
    print("non-PNG:", t.where("NOT path LIKE '%.png'").count(), "(want 0)")

# COMMAND ----------

# MAGIC %md
# MAGIC **Worked answer.** `pathGlobFilter` is a reader option that filters on the file
# MAGIC *name*; dropping `content` is a `select` on the DataFrame.

# COMMAND ----------

w = fresh("receipts")
(spark.readStream.format("cloudFiles")
    .option("cloudFiles.format", "binaryFile")
    .option("cloudFiles.schemaLocation", f"{w}/_schema")
    .option("pathGlobFilter", "*.png")
    .load(f"{SRC}/binary/receipts")
    .select("path", "modificationTime", "length")
 .writeStream.option("checkpointLocation", f"{w}/_checkpoint")
    .trigger(availableNow=True).toTable("al_lesson_receipts").awaitTermination())

display(spark.table("al_lesson_receipts"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Schema: inferred, hinted or declared
# MAGIC
# MAGIC Three ways to say what the columns are, and they behave differently when the data
# MAGIC does not fit:
# MAGIC
# MAGIC | You give | Types | A value that does not fit | Schema location |
# MAGIC |---|---|---|---|
# MAGIC | nothing | inferred (all `STRING` for CSV/JSON/XML without `inferColumnTypes`) | widens the column's type | required |
# MAGIC | `cloudFiles.schemaHints` | inferred, except the named columns | `NULL`, original kept in `_rescued_data` | required |
# MAGIC | `.schema(...)` | exactly yours | **`NULL`, and nothing is kept** | not needed |
# MAGIC
# MAGIC The last row is the trap: declare the schema yourself and the rescue column is off
# MAGIC unless you ask for it. Here are the same 80 orders with a declared schema:

# COMMAND ----------

w = fresh("declared")
(spark.readStream.format("cloudFiles")
    .option("cloudFiles.format", "csv")
    .option("sep", ";").option("header", "true").option("multiLine", "true").option("escape", '"')
    .schema("order_id STRING, store STRING, product_sku STRING, quantity INT, "
            "unit_price DECIMAL(10,2), gift_note STRING, ordered_at TIMESTAMP")
    .load(f"{SRC}/csv")
 .writeStream.option("checkpointLocation", f"{w}/_checkpoint")
    .trigger(availableNow=True).toTable("al_lesson_declared").awaitTermination())

t = spark.table("al_lesson_declared")
print(t.columns)
print("rows with no price:", t.where("unit_price IS NULL").count(), "- and nothing says why")

# COMMAND ----------

# MAGIC %md
# MAGIC Add `.option("rescuedDataColumn", "_rescued_data")` and the `TBC` is kept
# MAGIC again. The rule worth remembering: **a declared schema should always come with a
# MAGIC rescue column**, or bad values disappear without an error.
# MAGIC
# MAGIC `_rescued_data` holds JSON: the column name, the original text, and `_file_path`,
# MAGIC the file it came from. That is enough to find and fix the source.

# COMMAND ----------

display(spark.sql("""
    SELECT order_id,
           _rescued_data:unit_price AS original_price,
           _rescued_data:_file_path AS from_file
    FROM al_lesson_orders_hinted WHERE _rescued_data IS NOT NULL"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Schema evolution, mode by mode
# MAGIC
# MAGIC `cloudFiles.schemaEvolutionMode` (reader) decides what Auto Loader does when a
# MAGIC file has a column the recorded schema lacks. `mergeSchema` (writer) decides
# MAGIC whether the Delta table may gain that column. They are independent settings on
# MAGIC different objects, so there are eight combinations. All eight are run below.
# MAGIC
# MAGIC Each run: land a file with `order_id, store`, run the stream; land a file that
# MAGIC adds `channel`; run the stream three more times. **Runs 2–4 are a job retrying.**
# MAGIC
# MAGIC These streams fail *while running*, and a failed stream fails the notebook that
# MAGIC started it even inside `try`/`except` (measured; the cell still ends "Workload
# MAGIC failed"). So each combination runs in a helper notebook,
# MAGIC [`_helpers/evolution_attempt`](./_helpers/evolution_attempt), whose stream is the
# MAGIC familiar one:
# MAGIC
# MAGIC ```python
# MAGIC (spark.readStream.format("cloudFiles")
# MAGIC     .option("cloudFiles.format", "csv")
# MAGIC     .option("cloudFiles.schemaLocation", f"{WORK}/_schema")
# MAGIC     .option("header", "true")
# MAGIC     .option("cloudFiles.schemaEvolutionMode", MODE)    # reader
# MAGIC     .load(LANDING)
# MAGIC  .writeStream
# MAGIC     .option("checkpointLocation", f"{WORK}/_checkpoint")
# MAGIC     .option("mergeSchema", MERGE)                      # writer
# MAGIC     .trigger(availableNow=True)
# MAGIC     .toTable(TABLE)
# MAGIC     .awaitTermination())
# MAGIC ```
# MAGIC
# MAGIC Interactively you can do the same by hand: run a stream cell, see it fail, run it
# MAGIC again. That is what lesson 03 asks you to do.

# COMMAND ----------

import json


def evolution(mode, merge_schema, extra=None, name=None):
    name = name or f"evo_{mode}_{'merge' if merge_schema else 'nomerge'}".lower()
    # Fully qualified: the child notebook runs without this notebook's USE SCHEMA,
    # and a bare name would land in workspace.default, out of clean-up's reach.
    work, table = f"{WORK}/{name}", f"{CATALOG}.{SCHEMA}.al_lesson_{name}"
    try:
        dbutils.notebook.run("./_helpers/evolution_attempt", 900,
                             {"mode": mode, "merge_schema": str(merge_schema).lower(), "work": work, "table": table,
                              "extra_reader_options": json.dumps(extra or {})})
    except Exception:
        pass        # a failed last run fails the helper; its record is still on disk
    record = json.loads(dbutils.fs.head(f"{work}/_record.json", 100_000))
    return [(mode, "yes" if merge_schema else "no", r["run"],
             "ok" if r["ok"] else r["error"],
             ", ".join(c for c in r.get("columns", []) if c != "_rescued_data") if r["ok"] else "",
             r.get("rows"),
             len(r.get("rescued") or []) if r["ok"] else None)
            for r in record["runs"]]


results = []
for mode in ("addNewColumns", "rescue", "failOnNewColumns", "none"):
    for merge in (True, False):
        results += evolution(mode, merge)

display(spark.createDataFrame(results, "mode STRING, writer_mergeSchema STRING, run STRING, outcome STRING, "
                                       "columns STRING, rows LONG, rows_with_rescued_data LONG"))

# COMMAND ----------

# MAGIC %md
# MAGIC Two more through the same helper: `mergeSchema` put on the **reader** (with
# MAGIC `addNewColumns`, and none on the writer), and the misspelt option from 2h.

# COMMAND ----------

more = (evolution("addNewColumns", False, extra={"mergeSchema": "true"}, name="evo_merge_on_reader")
        + evolution("addNewColumns", True, extra={"cloudFiles.schemaEvolutonMode": "rescue"}, name="evo_typo"))
display(spark.createDataFrame([("mergeSchema on the reader" if i < 4 else "typo: schemaEvolutonMode",) + r[2:] for i, r in enumerate(more)],
                              "case STRING, run STRING, outcome STRING, columns STRING, rows LONG, rows_with_rescued_data LONG"))

# COMMAND ----------

# MAGIC %md
# MAGIC ### Reading the results
# MAGIC
# MAGIC | Mode | First run after the new column | Later runs | `channel` ends up |
# MAGIC |---|---|---|---|
# MAGIC | `addNewColumns` (the default) | fails `UNKNOWN_FIELD_EXCEPTION.NEW_FIELDS_IN_FILE` ("fixed by an automatic retry: true") | succeed, **with** writer `mergeSchema`; fail `DELTA_METADATA_MISMATCH` every time **without** it | a new column, `NULL` for the old rows |
# MAGIC | `rescue` | succeeds | succeed | inside `_rescued_data` as JSON; the schema never changes |
# MAGIC | `failOnNewColumns` | fails `UNKNOWN_FIELD_EXCEPTION.NEW_FIELDS_IN_FILE` ("automatic retry: false") | fail, until someone changes the schema or the mode | nowhere |
# MAGIC | `none` | succeeds | succeed | **dropped**: no column, no rescue, no error |
# MAGIC
# MAGIC Four things to take from it:
# MAGIC
# MAGIC 1. **Both halves, or a pipeline that fails every night.** `addNewColumns` without
# MAGIC    the writer's `mergeSchema` is not a one-off failure: the reader keeps offering
# MAGIC    the wider schema and the table keeps refusing it.
# MAGIC 2. **`rescue` and `none` never fail**, and only one of them keeps the data.
# MAGIC 3. **`mergeSchema` only matters when the reader's schema changes.** With `rescue`
# MAGIC    or `none` it has nothing to do.
# MAGIC 4. **The error message tells you the mode**: "automatic retry: true" is
# MAGIC    `addNewColumns`, "false" is `failOnNewColumns`.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Triggers
# MAGIC
# MAGIC `.trigger()` is a writer method and it decides how long the query lives:
# MAGIC
# MAGIC | Trigger | Runs | On Free Edition serverless |
# MAGIC |---|---|---|
# MAGIC | `availableNow=True` | everything that has arrived, in as many batches as the limits need, then stops | ✓ |
# MAGIC | `once=True` | everything in one batch, then stops (deprecated in favour of `availableNow`) | ✓ |
# MAGIC | `processingTime="10 seconds"` | forever, a batch every 10 s | `INFINITE_STREAMING_TRIGGER_NOT_SUPPORTED` |
# MAGIC | none | forever, a batch as soon as the last finishes | `INFINITE_STREAMING_TRIGGER_NOT_SUPPORTED` |
# MAGIC
# MAGIC `availableNow` respects the reader's rate limits. With
# MAGIC `cloudFiles.maxFilesPerTrigger` at 1, the two till logs arrive in two batches:

# COMMAND ----------

w = fresh("max_files")
q = (spark.readStream.format("cloudFiles")
    .option("cloudFiles.format", "text")
    .option("cloudFiles.schemaLocation", f"{w}/_schema")
    .option("cloudFiles.maxFilesPerTrigger", "1")          # reader: at most one file per batch
    .load(f"{SRC}/text")
 .writeStream.option("checkpointLocation", f"{w}/_checkpoint")
    .trigger(availableNow=True)                            # writer: drain, then stop
    .toTable("al_lesson_max_files"))
q.awaitTermination()
print("rows per batch:", [p["numInputRows"] for p in q.recentProgress])

# COMMAND ----------

def processing_time():
    w = fresh("processing_time")
    (spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "text")
        .option("cloudFiles.schemaLocation", f"{w}/_schema")
        .load(f"{SRC}/text")
     .writeStream.option("checkpointLocation", f"{w}/_checkpoint")
        .trigger(processingTime="10 seconds")
        .toTable("al_lesson_wrong_processing_time")
        .awaitTermination())


expect_error(processing_time, "INFINITE_STREAMING_TRIGGER_NOT_SUPPORTED")

# COMMAND ----------

# MAGIC %md
# MAGIC On a classic cluster `processingTime` runs; it is the trigger for a stream that
# MAGIC should keep up continuously, and the exam expects you to know both.
# MAGIC
# MAGIC ## 7. The checkpoint and the schema location
# MAGIC
# MAGIC Both are folders you name, and both hold real state. Look inside:

# COMMAND ----------

def ls(path):
    return sorted(f.name for f in dbutils.fs.ls(path))


orders = f"{WORK}/csv_right"
print("schema location:", ls(f"{orders}/_schema"), "->", ls(f"{orders}/_schema/_schemas"))
print("checkpoint     :", ls(f"{orders}/_checkpoint"))
print()
print(dbutils.fs.head(f"{orders}/_schema/_schemas/0", 400))

# COMMAND ----------

# MAGIC %md
# MAGIC | Folder | Holds | Written by |
# MAGIC |---|---|---|
# MAGIC | schema location `_schemas/0, 1, …` | one file per schema version; a new one each time `addNewColumns` evolves it | the reader |
# MAGIC | checkpoint `offsets/`, `commits/` | each batch: what it planned to read, and that it finished | the query |
# MAGIC | checkpoint `sources/` | Auto Loader's record of every file already ingested | the reader, inside the checkpoint |
# MAGIC
# MAGIC That last row is why the checkpoint, not the schema location, is what makes a
# MAGIC re-run load nothing. Delete it and every file is new again:

# COMMAND ----------

def till_stream(work):
    (spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "text")
        .option("cloudFiles.schemaLocation", f"{work}/_schema")
        .load(f"{SRC}/text")
     .writeStream.option("checkpointLocation", f"{work}/_checkpoint")
        .trigger(availableNow=True).toTable("al_lesson_rerun").awaitTermination())


w = fresh("rerun")
till_stream(w)
first = spark.table("al_lesson_rerun").count()
till_stream(w)
again = spark.table("al_lesson_rerun").count()
dbutils.fs.rm(f"{w}/_checkpoint", True)
till_stream(w)
after = spark.table("al_lesson_rerun").count()
print(f"first run {first} rows; re-run {again}; after deleting the checkpoint {after} (every line twice)")

# COMMAND ----------

# MAGIC %md
# MAGIC Two more rules that follow from what is in the folders:
# MAGIC
# MAGIC - **One checkpoint per stream.** Two streams writing to the same checkpoint
# MAGIC   overwrite each other's record of what is done.
# MAGIC - **The schema location can sit inside the checkpoint folder** (it is common to
# MAGIC   put it at `<checkpoint>/_schema`), but it is still set on the reader.
# MAGIC
# MAGIC ## Takeaways
# MAGIC
# MAGIC - Reader options describe the files; writer options describe the query and the
# MAGIC   table. `cloudFiles.*` and every format option are reader options.
# MAGIC - A reader option on the writer is usually **ignored, not rejected**. The loud
# MAGIC   failures are the required ones (`cloudFiles.format`, the schema location, the
# MAGIC   checkpoint); the quiet ones corrupt data (`multiLine`, `sep`, `pathGlobFilter`).
# MAGIC - CSV, JSON and XML need `cloudFiles.inferColumnTypes` for real types; hints pin
# MAGIC   the columns you care about; a declared schema needs a rescue column.
# MAGIC - `addNewColumns` needs `mergeSchema` on the writer, and fails once by design.
# MAGIC   `rescue` keeps new data in `_rescued_data`; `none` drops it silently.
# MAGIC - Serverless runs `availableNow`. The checkpoint is what makes a re-run safe.
# MAGIC
# MAGIC **Next, if you want it:** the optional assignment
# MAGIC [ASSOC-S2-AUTO-LOADER](../../../assignments/ASSOC-S2-AUTO-LOADER/assignment)
# MAGIC ([the task](../../../assignments/ASSOC-S2-AUTO-LOADER/README.md)): five sources, five
# MAGIC formats, every one of them a trap from this notebook.

# COMMAND ----------

# Clean up: every table and scratch folder this lesson made. The sources in
# s2_al_teach are never touched.
for row in spark.sql(f"SHOW TABLES IN {CATALOG}.{SCHEMA} LIKE 'al_lesson_*'").collect():
    spark.sql(f"DROP TABLE IF EXISTS {row.tableName}")
dbutils.fs.rm(WORK, True)
print("lesson tables and scratch removed")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Next
# MAGIC
# MAGIC The section's graded assignment: [ASSOC-S2 assignment notebook](../../../assignments/ASSOC-S2/assignment) · [the task](../../../assignments/ASSOC-S2/README.md).
# MAGIC
# MAGIC The optional one that goes with this lesson: [ASSOC-S2-AUTO-LOADER assignment notebook](../../../assignments/ASSOC-S2-AUTO-LOADER/assignment) · [the task](../../../assignments/ASSOC-S2-AUTO-LOADER/README.md).
