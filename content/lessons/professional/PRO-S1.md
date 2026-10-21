# Developing Code for Data Processing — 22%

The heaviest Professional section, and the one that assumes the most. It is less
about syntax than about *choosing the right level of abstraction*: built-in versus
UDF, streaming table versus materialized view, Structured Streaming versus a
declarative pipeline, and knowing what each choice costs.

> **Names:** Declarative Automation Bundles (Databricks Asset Bundles, DABs),
> Lakeflow Spark Declarative Pipelines (Delta Live Tables, DLT; `import dlt` is now
> `from pyspark import pipelines as dp`, `@dlt.table` is `@dp.table`, the `LIVE.`
> prefix is gone), `AUTO CDC` (`APPLY CHANGES`; `create_auto_cdc_flow` was
> `apply_changes`, `create_auto_cdc_from_snapshot_flow` was
> `apply_changes_from_snapshot`), Lakeflow Jobs (Workflows), Git folders (Repos).
> Old names still appear in distractors.

Structured Streaming has its own page in this section,
[Structured Streaming in depth](#structured-streaming--title): triggers, output
modes, watermarks, joins, checkpoints and exactly-once writes.

## What the exam asks

- A team keeps one copy of a job per environment and the copies drift — targets plus variables in one bundle (`PRO-S1-O1`)
- A new library version is installed with `%pip` but the old one still imports — restart Python after `%pip` (`PRO-S1-O2`)
- A row-at-a-time Python UDF is the slowest stage — a built-in first, else a pandas UDF (`PRO-S1-O3`)
- Late CDC events must not overwrite newer ones, and history must be kept — `AUTO CDC ... SEQUENCE BY ... STORED AS SCD TYPE 2` (`PRO-S1-O7`)
- A stream aggregates in append mode and nothing is ever written — append needs a watermark, and emits a window only once the watermark passes its end (`PRO-S1-O8`)
- A cleanup task must run even if an upstream task fails — `run_if: ALL_DONE` (`PRO-S1-O9`)

## Defaults and limits

| Setting | Default or limit | Note |
|---|---|---|
| `cloudFiles.maxFilesPerTrigger` | 1000 | `cloudFiles.maxBytesPerTrigger` has no default; when both are set, whichever limit is hit first applies |
| `cloudFiles.schemaEvolutionMode` | `addNewColumns` (no schema given), `none` (schema given) | the stream stops on a new column, then picks it up on restart |
| `cloudFiles.inferColumnTypes` | `false` | JSON and CSV columns are inferred as strings |
| `spark.sql.execution.arrow.maxRecordsPerBatch` | 10,000 | rows per Arrow batch handed to a pandas UDF |
| Structured Streaming trigger | `processingTime` 0 (next micro-batch as soon as the last ends) | serverless accepts only `availableNow` (and the deprecated `once`) |
| `spark.sql.shuffle.partitions` | 200 on classic compute | fixed in a stateful query's checkpoint at its first run |
| Task `max_retries` | 0 (never); `-1` retries indefinitely | `min_retry_interval_millis` default retries immediately; `retry_on_timeout` default `false` |
| Serverless auto-optimization | on | retries a failed task even with no retry policy; `disable_auto_optimization: true` turns it off |
| Job `max_concurrent_runs` | 1 (maximum 1000) | 0 skips every new run |
| For each `concurrency` | 1 in the UI, maximum 100 | `inputs` up to 48 KiB from a task value |
| Task value size | 48 KiB, JSON-serialisable | `dbutils.jobs.taskValues.set(key, value)` |
| Tasks per job | 1000 | 2,000 tasks running at once per workspace |
| `assertDataFrameEqual` tolerance | `rtol=1e-05`, `atol=1e-08` | applies to float columns only |

## A project shaped for bundles — `PRO-S1-O1`

A Declarative Automation Bundle is a folder with a `databricks.yml` at its root and
resource definitions under it. The layout the exam expects separates three things:

| Folder | Holds | Why separate |
|---|---|---|
| `resources/*.yml` | jobs, pipelines, apps, one resource per file | reviewable, diffable, `include`-able |
| `src/` or a package | reusable Python (transformations, helpers) | importable and unit-testable without Spark |
| notebooks | thin entry points that call the package | the notebook is the *task*, not the logic |

Two rules carry the marks. **Targets, not copies:** one job definition, deployed to
`dev`, `staging` and `prod` by switching `-t <target>`; anything that differs per
environment is a variable the target overrides. **Nothing environment-specific in
code:** the notebook receives its catalog and schema as parameters. Development
mode prefixes resource names with `[dev <user>]` and pauses schedules, so several
people can deploy the same bundle to one workspace without colliding.

```yaml
# databricks.yml
bundle:
  name: etl

include:                       # top level only: globs of resource files
  - resources/*.yml

artifacts:                     # built on deploy, uploaded, then referenced by tasks
  etl_pkg:
    type: whl                  # whl, jar or tgz
    build: uv build --wheel
    path: .

variables:
  catalog:
    default: dev_cat

targets:
  dev:
    mode: development          # "[dev <user>] " prefix, schedules paused
    default: true
  prod:
    mode: production
    workspace:
      root_path: /Workspace/Users/deployer@example.com/.bundle/${bundle.name}/${bundle.target}
    variables:
      catalog: prod_cat        # the only thing that changes per target
```

```bash
databricks bundle validate -t prod     # resolves ${var.catalog} to prod_cat
databricks bundle deploy -t prod       # builds the artifact, uploads, creates or updates
databricks bundle run etl_job -t prod
```

`${var.<name>}`, `${bundle.target}` and `${workspace.current_user.userName}` are
substitutions; a variable can also `lookup` an ID by name (a cluster, warehouse,
job, pipeline, service principal and others).

> **Measured on Free Edition:** with CLI 1.6, `include` under a target is reported
> as an unknown field and ignored. A path in an included file resolves relative to
> *that file*: `./dist/*.whl` written in `resources/etl.job.yml` became
> `./resources/dist/*.whl` in `bundle validate`, so the wheel has to be referenced
> as `../dist/*.whl`. `mode: development` renamed the job to `[dev <short name>] etl`
> and changed no variable.

## Third-party libraries — `PRO-S1-O2`

| Where the code comes from | Install with | Scope |
|---|---|---|
| PyPI | `%pip install pkg==1.2.3` in a notebook, or a `pypi` library on the task | notebook session / task |
| A local wheel | upload to a volume, `%pip install /Volumes/.../pkg.whl`, or a `whl` task library | same |
| Source archive / git | `%pip install git+https://...` | same |

`%pip` changes the Python environment of *that notebook's* session and needs a
`%restart_python` (or `dbutils.library.restartPython()`) before the new version is
importable. Task libraries install before the task starts. The classic failure
is **two libraries pinning incompatible versions of a shared dependency**; the fix
is to pin explicitly rather than hope resolution goes your way. On serverless
compute you declare an *environment* (dependencies plus an environment version)
rather than installing on a cluster.

`%pip` is the magic Databricks recommends. On current runtimes (11.3 LTS and
above) `%sh pip` and `!pip` also install notebook-scoped libraries; the old answer
"`%sh pip` installs on the driver only" describes 10.4 LTS and below.

```python
%pip install requests==2.32.3 /Volumes/main/libs/whl/etl_pkg-0.1-py3-none-any.whl
%restart_python
```

```json
"environments": [{
  "environment_key": "default",
  "spec": {"client": "4", "dependencies": ["requests==2.32.3", "/Volumes/main/libs/whl/etl_pkg-0.1-py3-none-any.whl"]}
}]
```

> **Measured on Free Edition:** serverless refused `libraries` on a task at create
> time ("Libraries field is not supported for serverless task, please specify
> libraries in environment"), and after `%pip install` of a new version the old one
> kept importing until `restartPython()`.

## UDFs: last resort, and vectorised when you must — `PRO-S1-O3`

A built-in runs inside the JVM and the optimiser can see through it. A Python UDF
serialises every row out to a Python process and back, and is opaque to the
optimiser: same result, very different cost.

| | Runs | Optimiser sees it | Use when |
|---|---|---|---|
| Built-in | JVM | yes | almost always |
| pandas UDF | Python, vectorised via Arrow | no | a UDF is needed and volume matters |
| Python UDF | Python, row at a time | no | logic that will not vectorise |

A pandas UDF receives a whole batch as a `pandas.Series` and returns one, so the
per-row serialisation cost is amortised. Preference order: built-in, then pandas
UDF, then a scalar Python UDF. The exam likes "which is slowest and why".

The type hints pick the variant:

```python
from typing import Iterator
import pandas as pd
from pyspark.sql.functions import pandas_udf

@pandas_udf("long")                                   # Series to Series
def plus_one(s: pd.Series) -> pd.Series:
    return s + 1

@pandas_udf("long")                                   # Iterator of Series: set-up once per partition
def scaled(batches: Iterator[pd.Series]) -> Iterator[pd.Series]:
    model = load_model()                              # expensive, done once
    for s in batches:
        yield model.predict(s)

@pandas_udf("double")                                 # Series to scalar: a grouped aggregate
def mean_(s: pd.Series) -> float:
    return float(s.mean())

df.groupBy("g").applyInPandas(fn, schema="...")       # whole group as a DataFrame
df.mapInPandas(fn, schema=df.schema)                  # iterator of DataFrames
```

`spark.sql.execution.arrow.maxRecordsPerBatch` (default 10,000) caps the rows in
each batch; it does not apply to the groups `applyInPandas` receives, which arrive
whole however big they are.

> **Measured on Free Edition:** a one-partition, 25,000-row input reached a pandas
> UDF on serverless in batches of 3,125 rows, not 10,000, and reading
> `spark.sql.execution.arrow.maxRecordsPerBatch` there returned
> `CONFIG_NOT_AVAILABLE`. Do not quote the batch size you see there as the default.
> All five variants above ran on serverless.

## Pipelines and Auto Loader — `PRO-S1-O4`

Lakeflow Spark Declarative Pipelines describe *what* tables exist and how each is
derived; the platform derives the dependency graph, orchestrates it, and applies
your **expectations** (declarative quality rules) as data flows. Auto Loader
(`cloudFiles`) is the ingestion source for files: it tracks what it has already
consumed, so a pipeline over a landing folder processes each file exactly once
and picks up new ones incrementally. Together they are the production shape for
"files land in storage, tables stay current".

```python
(spark.readStream.format("cloudFiles")
    .option("cloudFiles.format", "json")
    .option("cloudFiles.schemaLocation", "/Volumes/main/raw/_schemas/orders")  # needed to infer; pipelines manage it
    .option("cloudFiles.inferColumnTypes", "true")          # default false: everything is a string
    .option("cloudFiles.schemaHints", "amount DECIMAL(10,2)")
    .option("cloudFiles.schemaEvolutionMode", "addNewColumns")  # default when no schema is given
    .option("cloudFiles.maxFilesPerTrigger", 1000)           # the default
    .load("/Volumes/main/raw/orders/"))
```

| `cloudFiles.schemaEvolutionMode` | On a new column |
|---|---|
| `addNewColumns` (default without a schema) | stream stops with `UnknownFieldException`; the restart reads the new schema |
| `rescue` | schema unchanged; the value lands in `_rescued_data` |
| `failOnNewColumns` | stream fails and stays failed until the schema is changed |
| `none` (default with a schema) | ignored; nothing is added and the stream keeps going |

Other options the exam names: `cloudFiles.includeExistingFiles` (default `true`),
`cloudFiles.useNotifications` and `cloudFiles.useManagedFileEvents` (both default
`false`; file notification instead of directory listing), and
`cloudFiles.allowOverwrites` (default `false`: a changed file is not re-read).

> **Measured on Free Edition:** without `cloudFiles.schemaLocation` a JSON stream
> failed with `CLOUDFILES_SCHEMA_LOCATION_REQUIRED`. With it, `{"id": 1, "amt": 2.5}`
> was inferred as `id string, amt string` plus `_rescued_data`; with
> `inferColumnTypes` it became `bigint` and `double`. A file with a new column
> stopped the stream with `UNKNOWN_FIELD_EXCEPTION.NEW_FIELDS_IN_RECORD_WITH_FILE_PATH`.
> The restart read the new schema, then failed at the Delta sink with
> `DELTA_METADATA_MISMATCH`: the target table needs `mergeSchema` (or
> `spark.databricks.delta.schema.autoMerge.enabled`) too.

Several sources feeding one streaming table is an **append flow** per source, not
a `UNION`, so a source can be added later without a full refresh:

```python
from pyspark import pipelines as dp

dp.create_streaming_table("orders")

@dp.append_flow(target="orders", name="orders_eu")
def orders_eu():
    return spark.readStream.table("raw.orders_eu")

@dp.append_flow(target="orders", name="orders_backfill", once=True)   # runs once, again on full refresh
def orders_backfill():
    return spark.read.table("archive.orders_2024")
```

```sql
CREATE OR REFRESH STREAMING TABLE orders;
CREATE FLOW orders_us AS INSERT INTO orders BY NAME SELECT * FROM STREAM(raw.orders_us);
CREATE FLOW orders_hist AS INSERT ONCE INTO orders BY NAME SELECT * FROM archive.orders_2024;
```

> **Measured on Free Edition:** two `@dp.append_flow`s from two Delta tables into
> one `dp.create_streaming_table` target ran in one serverless pipeline; a row added
> to one source later arrived on the next update, and the other source's rows were
> not read again.

## Streaming tables vs materialized views — `PRO-S1-O6`

| | Streaming table | Materialized view |
|---|---|---|
| Processes | each input row **once**, incrementally | the query, on refresh (incrementally where the query allows, else a full recompute) |
| Suits | append-only, ever-growing sources | aggregates over data that changes |
| Handles updates to old rows | no: a consumed row is not revisited | yes, recomputed |
| Cost profile | proportional to new data | proportional to the query |

The decision rule: **does old data change?** If yes, a streaming table will not
see it and you want a materialized view. If the source only ever appends, a
streaming table is far cheaper.

```sql
CREATE OR REFRESH STREAMING TABLE orders_bronze
AS SELECT * FROM STREAM read_files('/Volumes/main/raw/orders/', format => 'json');

CREATE OR REFRESH MATERIALIZED VIEW daily_revenue
AS SELECT order_date, sum(amount) AS revenue FROM orders_bronze GROUP BY order_date;
```

`STREAM` makes the read incremental; without it, `read_files` is a batch read and
a streaming table refuses it.

## Jobs from the UI, the API and the CLI — `PRO-S1-O5`

The same job can be created three ways and the exam expects you to recognise all
three: the Jobs UI, `POST /api/2.2/jobs/create` with a JSON settings document
(tasks, `depends_on`, schedule, notifications), and `databricks jobs create
--json`. Runs are triggered with `run-now`, which accepts job parameters that
override the defaults; `runs/get` returns per-task state and `runs/get-output`
the notebook's exit value. In a bundle the definition lives in YAML and
`databricks bundle run <key>` triggers it, but it is the same API underneath.

```bash
databricks jobs create --json @job.json                 # returns {"job_id": ...}
databricks jobs run-now 123 --json '{"job_parameters": {"run_date": "2026-10-20"}}'
databricks jobs get-run <run_id>                        # per-task life_cycle_state and result_state
databricks jobs get-run-output <task_run_id>            # the task run id, not the job run id
databricks jobs submit --json @once.json                # one-off run, no saved job
```

Task parameters can carry **dynamic value references**, resolved when the task
runs:

| Reference | Resolves to |
|---|---|
| `{{job.id}}`, `{{job.run_id}}` | the job and this job run |
| `{{task.name}}`, `{{task.run_id}}` | this task and its run |
| `{{job.parameters.<name>}}` | a job parameter |
| `{{tasks.<task_key>.values.<key>}}` | a task value set upstream |
| `{{tasks.<task_key>.result_state}}` | `success`, `failed`, `upstream_failed`, ... |
| `{{job.start_time.iso_date}}` | the run's start date |

The old spellings `{{job_id}}`, `{{run_id}}` (now `{{task.run_id}}`, not the job
run), `{{parent_run_id}}` and `{{start_date}}` are deprecated.

> **Measured on Free Edition:** in a `jobs submit` run, `{{tasks.a.values.probe}}`,
> `{{job.run_id}}`, `{{job.id}}`, `{{task.name}}` and `{{job.start_time.iso_date}}`
> all resolved in `base_parameters`; the date is the UTC date (`2026-10-21` for a
> run started late on 20 October in a US time zone), and
> `{{tasks.a.result_state}}` after a failed task was the lower-case `failed`.

## AUTO CDC — `PRO-S1-O7`

When the source is a **change feed** rather than a snapshot, rows are *events
about* rows. `AUTO CDC` (formerly `APPLY CHANGES`) reduces them to current state,
and the three things it handles are the three things people get wrong by hand:

1. **Sequencing.** `SEQUENCE BY` decides which event wins, not arrival order.
2. **Deletes.** `APPLY AS DELETE WHEN` removes the key rather than keeping a row
   that says "deleted".
3. **Out-of-order arrival.** A late event with a lower sequence is ignored under
   SCD type 1; under SCD type 2 it becomes a historical version instead.

```sql
CREATE OR REFRESH STREAMING TABLE customers;

CREATE FLOW customers_cdc AS AUTO CDC INTO customers
FROM STREAM(customer_changes)
KEYS (customer_id)
APPLY AS DELETE WHEN op = 'delete'
SEQUENCE BY seq_num
COLUMNS * EXCEPT (op, seq_num)
STORED AS SCD TYPE 1;
```

The older spelling, `APPLY CHANGES INTO live.customers ...`, still appears in
distractors; the `live.` prefix is deprecated in Unity Catalog pipelines. With
`STORED AS SCD TYPE 2` the target keeps every version with `__START_AT` and
`__END_AT` columns, and a late event re-cuts those intervals rather than being
dropped.

The same by hand is a window over the key ordered by the sequence, keep the latest
event, drop keys whose latest event is a delete. A key that was deleted and then
updated again is *present*, because its highest sequence is the update. That is
exactly the trap in this section's assignment.

The clauses beyond the core five:

| Clause (SQL) | Python argument | Does |
|---|---|---|
| `STORED AS SCD TYPE 2` | `stored_as_scd_type=2` (default `1`) | keeps history in `__START_AT` / `__END_AT`, typed like the `SEQUENCE BY` column; the current row has `__END_AT IS NULL` |
| `TRACK HISTORY ON (col, ...)` or `ON * EXCEPT (...)` | `track_history_column_list`, `track_history_except_column_list` | SCD 2 only: a change to an untracked column updates the current row in place |
| `IGNORE NULL UPDATES` | `ignore_null_updates=True` (default `False`) | a NULL in the update keeps the existing value |
| `APPLY AS TRUNCATE WHEN` | `apply_as_truncates` | SCD 1 only: empties the target |
| `SEQUENCE BY STRUCT(ts, id)` | `sequence_by=struct("ts", "id")` | ties broken by the second field |

```python
dp.create_streaming_table("customers_history")
dp.create_auto_cdc_flow(
    target="customers_history", source="customer_changes",
    keys=["customer_id"], sequence_by="seq_num",
    apply_as_deletes="op = 'delete'", except_column_list=["op"],
    stored_as_scd_type=2,
)
```

When the source is a **full snapshot** each time (a nightly dump, no change
events), `AUTO CDC FROM SNAPSHOT` diffs consecutive snapshots: a key missing from
the new snapshot is a delete, a changed row is an update. There is no
`SEQUENCE BY`; the snapshot version orders the changes.

```python
dp.create_streaming_table("products")
dp.create_auto_cdc_from_snapshot_flow(
    target="products",
    source="raw.products_snapshot",   # or a function returning (DataFrame, version) or None
    keys=["product_id"],
    stored_as_scd_type=2,
)
```

```sql
-- SQL: as written, this loads ONE snapshot; a later update fails
CREATE FLOW products_snap AS AUTO CDC INTO products
FROM SNAPSHOT (SELECT * FROM raw.products_snapshot)
KEYS (product_id)
STORED AS SCD TYPE 2;
```

The SQL form needs `WITH VERSION (version_query)` to process snapshot after
snapshot: the version query says which snapshot is next, and the snapshot query
reads it through `current_snapshot_version()`. Without it the flow is a one-time
load, and the next update fails with
`AUTO_CDC_FROM_SNAPSHOT_NON_EMPTY_TARGET_WITHOUT_VERSION`.

> **Measured on Free Edition:** the SCD type 2 flow above (in SQL) was fed
> sequences 1 and 3 for key 1, then a late sequence 2 in the next update. The
> target went from `v1 [1, 3)`, `v3 [3, open)` to `v1 [1, 2)`, `v2 [2, 3)`,
> `v3 [3, open)`: the late event was slotted in, not dropped. A key whose last event
> was a delete kept its history row with `__END_AT` set and had no current row.
> `create_auto_cdc_from_snapshot_flow` on a table source stamped `__START_AT` /
> `__END_AT` with timestamps; when the next snapshot dropped key 2 and changed key 1,
> key 2's row was closed and key 1 got a new version. The SQL `FROM SNAPSHOT` flow
> without `WITH VERSION` loaded the first snapshot and failed the next update with
> `AUTO_CDC_FROM_SNAPSHOT_NON_EMPTY_TARGET_WITHOUT_VERSION`.

## Structured Streaming vs declarative pipelines — `PRO-S1-O8`

| | Structured Streaming | Lakeflow Declarative Pipelines |
|---|---|---|
| You write | the how: `readStream`, checkpoints, triggers | the what: table definitions and dependencies |
| Orchestration | yours | derived from the dependency graph |
| Quality rules | hand-rolled | declarative expectations |
| Best when | you need precise control over state and triggers | the mechanics are incidental |

Declarative pipelines are not "streaming made easy"; they are a different level of
abstraction. Reach for Structured Streaming when you need the mechanics.

```python
# Structured Streaming: you own the checkpoint, the trigger and the sink
(spark.readStream.table("raw.orders")
    .writeStream
    .option("checkpointLocation", "/Volumes/main/chk/orders_silver")
    .trigger(availableNow=True)
    .toTable("main.silver.orders"))
```

```sql
-- Pipeline: the same table, with the checkpoint and trigger managed for you
CREATE OR REFRESH STREAMING TABLE orders_silver AS SELECT * FROM STREAM(raw.orders);
```

**Which primitive?**

| You need | Use |
|---|---|
| append-only source, each row processed once | streaming table (`CREATE ... STREAMING TABLE ... AS SELECT ... STREAM`) |
| an aggregate or join that must reflect changed rows | materialized view |
| several sources into one table, or a one-off backfill | `append_flow` / `CREATE FLOW ... INSERT INTO`, with `once` for the backfill |
| a change feed reduced to current state or history | `AUTO CDC` (`FROM SNAPSHOT` when the source is full dumps) |
| per-batch logic: MERGE into an existing table, several sinks, a non-Delta target | `foreachBatch` in Structured Streaming, or `@dp.foreach_batch_sink` in a pipeline (Python only) |

## Control flow in jobs — `PRO-S1-O9`

Jobs have control-flow tasks: an **If/else** task branches on a condition
(typically a task value or parameter), and a **For each** task runs a nested task
once per element of a list, with a concurrency setting. Tasks pass small values
downstream with `dbutils.jobs.taskValues.set(...)` and read them with
`taskValues.get(...)`, and `depends_on` can carry a `run_if` rule
(`ALL_SUCCESS`, `AT_LEAST_ONE_FAILED`, ...) so a cleanup task runs even when an
upstream one fails.

```yaml
tasks:
  - task_key: check
    notebook_task: {notebook_path: ../src/check.py}      # taskValues.set("row_count", n)
  - task_key: has_rows
    depends_on: [{task_key: check}]
    condition_task:
      op: GREATER_THAN                 # EQUAL_TO, NOT_EQUAL, GREATER_THAN(_OR_EQUAL), LESS_THAN(_OR_EQUAL)
      left: "{{tasks.check.values.row_count}}"
      right: "0"
  - task_key: per_region
    depends_on: [{task_key: has_rows, outcome: "true"}]
    for_each_task:
      inputs: '["eu", "us", "apac"]'
      concurrency: 3                   # 1 to 100
      task:
        task_key: load_region
        notebook_task:
          notebook_path: ../src/load.py
          base_parameters: {region: "{{input}}"}
  - task_key: cleanup
    depends_on: [{task_key: per_region}]
    run_if: ALL_DONE
```

`EQUAL_TO` and `NOT_EQUAL` compare strings; the four ordering operators compare
numbers. `run_if` scenarios, for a task with two upstreams:

| `run_if` | Upstreams: both succeed | one fails | both fail |
|---|---|---|---|
| `ALL_SUCCESS` (default) | runs | upstream failed, skipped | skipped |
| `AT_LEAST_ONE_SUCCESS` | runs | runs | skipped |
| `NONE_FAILED` | runs | skipped | skipped |
| `ALL_DONE` | runs | runs | runs |
| `AT_LEAST_ONE_FAILED` | skipped | runs | runs |
| `ALL_FAILED` | skipped | skipped | runs |

`NONE_FAILED` differs from `ALL_SUCCESS` only when an upstream was itself skipped
(excluded) rather than failed: a skipped upstream is not a failure. With one
upstream succeeded and one excluded, `NONE_FAILED` runs the task and `ALL_SUCCESS`
excludes it.

> **Measured on Free Edition:** a For each task with one failed iteration counts as
> a single *failed* upstream, so a dependant with `AT_LEAST_ONE_SUCCESS` and only
> that upstream did not run ("All upstream tasks failed"). `ALL_DONE` ran after it.
> A 50 KiB task value was refused with "The task value is too large".

![Pick each dependant's run_if, fail a task and watch the states resolve](visual:job-dag-repair?h=1250)

## Configuring tasks sensibly — `PRO-S1-O10`

- **Environments and dependencies** are declared per task (serverless
  environment or task libraries), not installed ad hoc mid-run.
- **High memory** is a task-level choice for notebook tasks that genuinely need
  it; it is not a substitute for fixing a `collect()`.
- **Retries** are for transient failures. A task whose work is *not idempotent*
  must not retry blindly, or a retry duplicates its output; either make the write
  idempotent (overwrite, MERGE) or disallow retries. The exam phrases this as
  "auto-optimization to disallow retries".

```yaml
- task_key: load
  max_retries: 2                      # default 0; -1 retries indefinitely
  min_retry_interval_millis: 60000    # default: retry at once
  retry_on_timeout: false             # the default
  timeout_seconds: 3600               # default 0, no timeout
  disable_auto_optimization: true     # serverless: no automatic retries for a non-idempotent task
  environment_key: default            # serverless: dependencies live in the environment
```

On serverless, jobs **auto-optimize** and retry a failed task on their own. That
is separate from the retry policy: you disallow it per task by unchecking *Enable
serverless auto-optimization* in the Retry Policy dialog, or with
`disable_auto_optimization: true` in the task's JSON or YAML. A
pipeline has its own retry settings, `pipelines.numUpdateRetryAttempts` and
`pipelines.maxFlowRetryAttempts`, set in the pipeline `configuration`.

> **Measured on Free Edition:** serverless jobs created without any retry setting
> re-ran a failed notebook task once (`attempt_number` 1) before failing the run,
> and a task that inserted a row and then raised committed that row twice. With
> `max_retries: 0` in a `jobs submit` task it still re-ran once; with
> `disable_auto_optimization: true` the failing task ran once and the run failed.
> `spark.driver.memory` is `CONFIG_NOT_AVAILABLE` on serverless, so high memory is a
> classic-compute exercise.

## Testing transformations — `PRO-S1-O11`

`DataFrame.transform(fn)` lets a transformation be a named function, which is what
makes it testable in isolation. Then:

- `assertDataFrameEqual(actual, expected)` compares content and reports the
  differing rows; row order is ignored unless `checkRowOrder=True`.
- `assertSchemaEqual(actual.schema, expected.schema)` compares structure,
  including column order; nullability is ignored by default.

```python
from pyspark.testing import assertDataFrameEqual, assertSchemaEqual

assertDataFrameEqual(
    actual, expected,
    checkRowOrder=False,       # default
    rtol=1e-05, atol=1e-08,    # defaults: float tolerance, |a - b| <= atol + rtol * |b|
    ignoreNullable=True,       # default
    ignoreColumnOrder=False,   # default: column order matters
    ignoreColumnName=False, ignoreColumnType=False,
    maxErrors=None, showOnlyDiff=False,
)
assertSchemaEqual(actual.schema, expected.schema,
                  ignoreNullable=True, ignoreColumnOrder=False, ignoreColumnName=False)

def test_clean(spark):
    raw = spark.createDataFrame([(" a ", 1)], "name string, n int")
    assertDataFrameEqual(raw.transform(clean), spark.createDataFrame([("a", 1)], "name string, n int"))
```

Test against a **tiny hand-built DataFrame**, not against production data: a test
whose expected values come from the same pipeline it is testing proves nothing.
Run the suite with pytest; on Databricks that means in-process (a subprocess
cannot reach the Spark session), which is exactly how this repo's graders work.
The notebook debugger and `breakpoint()` are for stepping through the Python
half; the Spark half is diagnosed from the query plan and the Spark UI.

> **Measured on Free Edition:** PySpark 4.0.0 on serverless has the signature
> above. `1.000001` against `1.0` passed under the default tolerance; `1.001` failed.

## Further reading

Official documentation for what this section tests, one link per topic:

- [Bundle configuration](https://docs.databricks.com/aws/en/dev-tools/bundles/settings) — `include`, `variables`, `artifacts`, `targets`.
- [Bundle variables](https://docs.databricks.com/aws/en/dev-tools/bundles/variables) — `${var.*}`, overrides and `lookup`.
- [Libraries](https://docs.databricks.com/aws/en/libraries/) — `%pip`, environments and init scripts.
- [Notebook-scoped Python libraries](https://docs.databricks.com/aws/en/libraries/notebooks-python-libraries) — `%pip`, `%sh pip` and restarting Python.
- [pandas user-defined functions](https://docs.databricks.com/aws/en/udf/pandas) — vectorised UDFs and when they pay off.
- [Lakeflow Spark Declarative Pipelines concepts](https://docs.databricks.com/aws/en/ldp/concepts) — flows, streaming tables, materialized views.
- [Auto Loader options](https://docs.databricks.com/aws/en/ingestion/cloud-object-storage/auto-loader/options) — every `cloudFiles.*` option and its default.
- [Auto Loader schema inference and evolution](https://docs.databricks.com/aws/en/ingestion/cloud-object-storage/auto-loader/schema) — the four evolution modes and `_rescued_data`.
- [append_flow](https://docs.databricks.com/aws/en/ldp/developer/ldp-python-ref-append-flow) — fan-in and `once` backfills.
- [CREATE FLOW](https://docs.databricks.com/aws/en/ldp/developer/ldp-sql-ref-create-flow) — `INSERT [ONCE] INTO` and `AUTO CDC ... FROM SNAPSHOT` in SQL.
- [AUTO CDC](https://docs.databricks.com/aws/en/ldp/cdc) — SCD type 1 and 2, sequencing, `APPLY AS DELETE WHEN`.
- [create_auto_cdc_from_snapshot_flow](https://docs.databricks.com/aws/en/ldp/developer/ldp-python-ref-apply-changes-from-snapshot) — CDC from full snapshots.
- [Structured Streaming](https://docs.databricks.com/aws/en/structured-streaming/) — the streaming documentation home.
- [Triggers](https://docs.databricks.com/aws/en/structured-streaming/triggers) — `availableNow`, `processingTime`, continuous.
- [Watermarks](https://docs.databricks.com/aws/en/structured-streaming/watermarks) — late data and state cleanup.
- [Checkpoints](https://docs.databricks.com/aws/en/structured-streaming/checkpoints) — what is stored and when it must be reset.
- [foreachBatch](https://docs.databricks.com/aws/en/structured-streaming/foreach) — MERGE and multi-sink writes with idempotence.
- [Dynamic value references](https://docs.databricks.com/aws/en/jobs/dynamic-value-references) — `{{job.*}}`, `{{task.*}}`, `{{tasks.*}}` and the deprecated forms.
- [Control the flow of tasks](https://docs.databricks.com/aws/en/jobs/control-flow) — `run_if`, conditions, loops.
- [For each task](https://docs.databricks.com/aws/en/jobs/for-each) — `inputs`, `concurrency` and limits.
- [Task values](https://docs.databricks.com/aws/en/jobs/task-values) — `taskValues.set` / `get` and the 48 KiB limit.
- [Configure a task](https://docs.databricks.com/aws/en/jobs/configure-task) — retries, timeouts and environments.
- [Unit testing for notebooks](https://docs.databricks.com/aws/en/notebooks/testing) — `pyspark.testing` and pytest in notebooks.
- [Exam page](https://www.databricks.com/learn/certification/data-engineer-professional) — official guide, section weights and policies.

Videos for another angle on the hard parts (channel, length):

- [Dive into Streaming Checkpoints and Best Practices](https://www.youtube.com/watch?v=v-GHBmL3KmI) — Databricks Skill Builder, 66 min. Long, but it is the checkpoint talk.
- [Late data processing, watermarks, tumbling and sliding windows](https://www.youtube.com/watch?v=4DT528dAjtU) — Ease With Data, 10 min. Watermark arithmetic with a picture.
- [Data Quality as Code: Spark Declarative Pipelines expectations](https://www.youtube.com/watch?v=CjS6ILJZP7k) — DataMindAI with Ahmed, 46 min. Expectations end to end.
