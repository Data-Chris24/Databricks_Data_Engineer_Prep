# Developing Code for Data Processing — 22%

The heaviest Professional section, and the one that assumes the most. It is less
about syntax than about *choosing the right level of abstraction*: built-in versus
UDF, streaming table versus materialized view, Structured Streaming versus a
declarative pipeline, and knowing what each choice costs.

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

## Pipelines and Auto Loader — `PRO-S1-O4`

Lakeflow Spark Declarative Pipelines describe *what* tables exist and how each is
derived; the platform derives the dependency graph, orchestrates it, and applies
your **expectations** (declarative quality rules) as data flows. Auto Loader
(`cloudFiles`) is the ingestion source for files: it tracks what it has already
consumed, so a pipeline over a landing folder processes each file exactly once
and picks up new ones incrementally. Together they are the production shape for
"files land in storage, tables stay current".

## Streaming tables vs materialized views — `PRO-S1-O6`

| | Streaming table | Materialized view |
|---|---|---|
| Processes | each input row **once**, incrementally | the whole query, on refresh |
| Suits | append-only, ever-growing sources | aggregates over data that changes |
| Handles updates to old rows | no: a consumed row is not revisited | yes, recomputed |
| Cost profile | proportional to new data | proportional to the query |

The decision rule: **does old data change?** If yes, a streaming table will not
see it and you want a materialized view. If the source only ever appends, a
streaming table is far cheaper.

## Jobs from the UI, the API and the CLI — `PRO-S1-O5`

The same job can be created three ways and the exam expects you to recognise all
three: the Jobs UI, `POST /api/2.2/jobs/create` with a JSON settings document
(tasks, `depends_on`, schedule, notifications), and `databricks jobs create
--json`. Runs are triggered with `run-now`, which accepts job parameters that
override the defaults; `runs/get` returns per-task state and `runs/get-output`
the notebook's exit value. In a bundle the definition lives in YAML and
`databricks bundle run <key>` triggers it, but it is the same API underneath.

## AUTO CDC — `PRO-S1-O7`

When the source is a **change feed** rather than a snapshot, rows are *events
about* rows. `AUTO CDC` (formerly `APPLY CHANGES`) reduces them to current state,
and the three things it handles are the three things people get wrong by hand:

1. **Sequencing.** `SEQUENCE BY` decides which event wins, not arrival order.
2. **Deletes.** `APPLY AS DELETE WHEN` removes the key rather than keeping a row
   that says "deleted".
3. **Out-of-order arrival.** A late event with a lower sequence is ignored.

```sql
CREATE OR REFRESH STREAMING TABLE customers;

APPLY CHANGES INTO live.customers
FROM STREAM(live.customer_changes)
KEYS (customer_id)
APPLY AS DELETE WHEN op = 'delete'
SEQUENCE BY seq_num
COLUMNS * EXCEPT (op, seq_num);
```

The same by hand is a window over the key ordered by the sequence, keep the latest
event, drop keys whose latest event is a delete. A key that was deleted and then
updated again is *present*, because its highest sequence is the update. That is
exactly the trap in this section's assignment.

## Structured Streaming vs declarative pipelines — `PRO-S1-O8`

| | Structured Streaming | Lakeflow Declarative Pipelines |
|---|---|---|
| You write | the how: `readStream`, checkpoints, triggers | the what: table definitions and dependencies |
| Orchestration | yours | derived from the dependency graph |
| Quality rules | hand-rolled | declarative expectations |
| Best when | you need precise control over state and triggers | the mechanics are incidental |

Declarative pipelines are not "streaming made easy"; they are a different level of
abstraction. Reach for Structured Streaming when you need the mechanics.

## Control flow in jobs — `PRO-S1-O9`

Jobs have control-flow tasks: an **If/else** task branches on a condition
(typically a task value or parameter), and a **For each** task runs a nested task
once per element of a list, with a concurrency setting. Tasks pass small values
downstream with `dbutils.jobs.taskValues.set(...)` and read them with
`taskValues.get(...)`, and `depends_on` can carry a `run_if` rule
(`ALL_SUCCESS`, `AT_LEAST_ONE_FAILED`, ...) so a cleanup task runs even when an
upstream one fails.

## Configuring tasks sensibly — `PRO-S1-O10`

- **Environments and dependencies** are declared per task (serverless
  environment or task libraries), not installed ad hoc mid-run.
- **High memory** is a task-level choice for notebook tasks that genuinely need
  it; it is not a substitute for fixing a `collect()`.
- **Retries** are for transient failures. A task whose work is *not idempotent*
  must not retry blindly, or a retry duplicates its output; either make the write
  idempotent (overwrite, MERGE) or disallow retries. The exam phrases this as
  "auto-optimization to disallow retries".

## Testing transformations — `PRO-S1-O11`

`DataFrame.transform(fn)` lets a transformation be a named function, which is what
makes it testable in isolation. Then:

- `assertDataFrameEqual(actual, expected)` compares content and reports the
  differing rows.
- `assertSchemaEqual(actual.schema, expected.schema)` compares structure,
  including column order.

Test against a **tiny hand-built DataFrame**, not against production data: a test
whose expected values come from the same pipeline it is testing proves nothing.
Run the suite with pytest; on Databricks that means in-process (a subprocess
cannot reach the Spark session), which is exactly how this repo's graders work.
The notebook debugger and `breakpoint()` are for stepping through the Python
half; the Spark half is diagnosed from the query plan and the Spark UI.
