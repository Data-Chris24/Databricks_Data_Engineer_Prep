# Working with Lakeflow Jobs — 16%

Orchestration: task graphs, triggers, and what happens when part of a job fails.

> **Names:** Lakeflow Jobs (Workflows, Databricks Jobs), Lakeflow Spark Declarative Pipelines (Delta Live Tables, DLT) for the pipeline task, If/else condition task (condition task), AI/BI dashboards (Lakeview dashboards) for the dashboard task, Declarative Automation Bundles (Databricks Asset Bundles).

## What the exam asks

- A → (B, C) → D, B fails and C succeeds: does D run? — the six `run_if` values decide; the default `ALL_SUCCESS` skips D (`ASSOC-S4-O1`)
- A task appends and has retries switched on, and the table ends up with duplicates — a retry reruns the whole task, so it must be idempotent (`ASSOC-S4-O1`)
- One notebook must run once per region and adding a region should not mean editing the job — a For each task over a task value or parameter (`ASSOC-S4-O1`)
- Task A computes a value task B needs — `dbutils.jobs.taskValues.set` in A, `{{tasks.A.values.key}}` or `taskValues.get` in B (`ASSOC-S4-O2`)
- A partner drops files at unpredictable times and reports must follow quickly — a file arrival trigger, not a cron schedule (`ASSOC-S4-O3`, `ASSOC-S4-O4`)
- A downstream job depends on a table whose upstream schedule keeps changing — a table update trigger, not a cron offset (`ASSOC-S4-O4`)

## Defaults and limits

| Setting | Default or limit | Note |
|---|---|---|
| `run_if` | `ALL_SUCCESS` | six values in all |
| `max_concurrent_runs` | 1 | range 0 to 1000 |
| `queue.enabled` | `true` on new jobs | queued runs wait up to 48 hours |
| `max_retries` | 0 (no retries) | serverless auto-optimization still retries, see below |
| `timeout_seconds` | 0 (no timeout) | with retries, the timeout applies to each attempt |
| Task value size | 48 KiB | size of the value's JSON representation |
| For each `concurrency` | 1 | maximum 100 |
| For each inputs typed in the UI | 5,000 characters | 48 KB through a task value reference |
| File arrival check | about every minute | best effort |
| File arrival location | 10,000 files | without file events; no limit with them |
| Jobs with a file arrival trigger | 50 per workspace | without file events |
| Tables per table update trigger | 10 | more needs file events |
| `min_time_between_triggers_seconds`, `wait_after_last_change_seconds` | 60 minimum | file arrival and table update triggers |
| Time between scheduled runs | 10 seconds minimum | whatever the cron expression says |
| Cron `timezone_id` | required | `UTC` avoids daylight-saving skips |

## Tasks and the DAG — `ASSOC-S4-O2`

A job is a graph of tasks with dependencies. A task runs when **all** of its
dependencies have succeeded, unless its `run_if` says otherwise.

**A job is not a transaction.** This is the most consequential idea in the section.
Given A → (B, C) → D, if C fails:

- A and B **completed**, and whatever they wrote to the lakehouse **stays written**
- C failed, and writes it committed before failing are still there
- D is **skipped**, not failed (its result state is `UPSTREAM_FAILED`)

Delta gives ACID guarantees per write operation, never across a job. Nothing rolls
back for you.

**Task types:** notebook, Python script, Python wheel, SQL (query, file or alert),
dashboard, pipeline, dbt, JAR, Spark Submit, Run Job (another job as a task), and
the two control-flow tasks, If/else and For each. There is no "run a shell command"
task — that happens inside a notebook or script.

```yaml
resources:
  jobs:
    nightly_orders:
      name: nightly_orders
      job_clusters:                       # one cluster shared by several tasks
        - job_cluster_key: shared
          new_cluster: {spark_version: 15.4.x-scala2.12, node_type_id: i3.xlarge, num_workers: 2}
      tasks:
        - task_key: ingest
          pipeline_task: {pipeline_id: "${resources.pipelines.orders.id}"}
        - task_key: transform
          depends_on: [{task_key: ingest}]
          job_cluster_key: shared         # omit compute on serverless
          notebook_task:
            notebook_path: ../src/transform.py
            base_parameters: {region: emea}
        - task_key: report_sql
          depends_on: [{task_key: transform}]
          sql_task:
            warehouse_id: ${var.warehouse_id}
            query: {query_id: ${var.query_id}}
        - task_key: refresh_dashboard
          depends_on: [{task_key: report_sql}]
          dashboard_task:
            dashboard_id: ${var.dashboard_id}
            warehouse_id: ${var.warehouse_id}
```

A **job cluster** (`job_clusters`) starts with the run and terminates when the run
ends; tasks that name the same `job_cluster_key` share it instead of each paying
for a start-up. An all-purpose cluster (`existing_cluster_id`) is for interactive
work and costs more for scheduled jobs. Serverless needs no compute block at all.

### Parameters and task values end to end

Three ways a value reaches a task, and how a notebook reads each:

| What | Set where | Read in a notebook | Reference elsewhere |
|---|---|---|---|
| Job parameter | `parameters:` on the job, overridable at run time | `dbutils.widgets.get("env")` | `{{job.parameters.env}}` |
| Task parameter | `base_parameters:` on a notebook task | `dbutils.widgets.get("region")` | — |
| Task value | `dbutils.jobs.taskValues.set(key, value)` in an upstream task | `dbutils.jobs.taskValues.get(taskKey, key, default, debugValue)` | `{{tasks.<task>.values.<key>}}` |

Job parameters are pushed down to every task that takes key-value parameters, and
when a job parameter and a task parameter share a key, **the job parameter wins**.
In `taskValues.get`, `default` is what you get in a job run when the key is not
found, and `debugValue` is what you get when you run the notebook by hand outside
a job, where there is no upstream task to read from.

```python
# Task "extract"
dbutils.jobs.taskValues.set(key="row_count", value=n)          # JSON-serialisable, 48 KiB max

# Task "transform", which depends_on extract
rows = dbutils.jobs.taskValues.get(taskKey="extract", key="row_count",
                                   default=0, debugValue=360)
env  = dbutils.widgets.get("env")                               # a job parameter
```

```yaml
parameters:
  - {name: env, default: dev}
  - {name: run_date, default: "{{job.start_time.iso_date}}"}   # dynamic value reference
tasks:
  - task_key: check
    depends_on: [{task_key: extract}]
    condition_task: {op: GREATER_THAN, left: "{{tasks.extract.values.row_count}}", right: "0"}
```

Other dynamic value references the exam uses: `{{job.id}}`, `{{job.run_id}}`,
`{{job.trigger.type}}`, `{{job.repair_count}}`, `{{task.name}}`,
`{{tasks.<task>.result_state}}`. The contents of `{{ }}` are not evaluated, so no
expressions inside them. A `dbutils.notebook.exit` value is **not** a task value.

> **Measured on Free Edition:** a job parameter with no matching `base_parameters`
> entry was readable with `dbutils.widgets.get` in every notebook task; a 42 set as a
> task value reached a downstream condition task as `{{tasks.A.values.rows}}`; a
> 49 KiB task value failed with `INVALID_PARAMETER_VALUE: The task value is too large`;
> `{{tasks.A.values.result}}` for a `dbutils.notebook.exit` value failed with "Task
> value ... was not found".

## Control flow — `ASSOC-S4-O1`

### `run_if`: what a dependant does when a dependency fails

Six values. The scenario: A, then B and C both depend on A, then D depends on B and
C. **B fails, C succeeds.**

| D's `run_if` | Rule | D in the scenario |
|---|---|---|
| `ALL_SUCCESS` (default) | every dependency succeeded | skipped, `UPSTREAM_FAILED` |
| `AT_LEAST_ONE_SUCCESS` | one or more succeeded | **runs** |
| `NONE_FAILED` | none failed, and at least one ran | skipped, `UPSTREAM_FAILED` |
| `ALL_DONE` | every dependency finished, whatever the result | **runs** |
| `AT_LEAST_ONE_FAILED` | one or more failed | **runs** |
| `ALL_FAILED` | every dependency failed | skipped, `EXCLUDED` |

When a dependency was itself skipped, `UPSTREAM_FAILED` counts as a failure and
an `EXCLUDED` dependency is left out of the count, except that under `ALL_SUCCESS`
it excludes the dependant too. A task whose dependencies are all `EXCLUDED` is
excluded, whatever its `run_if`. The run as a whole ends `FAILED` because B failed, even though D ran. `ALL_DONE` is
the cleanup or notify task; `AT_LEAST_ONE_FAILED` is the alerting task that should
run only when something broke.

```yaml
- task_key: D
  depends_on: [{task_key: B}, {task_key: C}]
  run_if: AT_LEAST_ONE_FAILED       # ALL_SUCCESS | AT_LEAST_ONE_SUCCESS | NONE_FAILED
                                    # ALL_DONE | AT_LEAST_ONE_FAILED | ALL_FAILED
```

> **Measured on Free Edition:** the scenario above was run with six D tasks, one per
> value. The three that ran and the three that were skipped, with the result states
> shown, are exactly the table. A second job checked skipped dependencies. The docs
> say an `EXCLUDED` upstream is treated as successful, but with one dependency
> `FAILED` and one `EXCLUDED`, `ALL_FAILED` ran and `AT_LEAST_ONE_SUCCESS` ended
> `UPSTREAM_FAILED` ("All upstream tasks failed"). With one `SUCCESS` and one
> `EXCLUDED`, `ALL_SUCCESS` ended `EXCLUDED` and `NONE_FAILED` ran.

![Fail a task, pick each dependant's run_if, run the job, then repair it](visual:job-dag-repair?h=1250)

### Retries and timeouts

**Retries assume idempotence.** A retry reruns the task from the start. If the failed
attempt already committed writes and the retry blindly appends the same data, you get
duplicates. Idempotent design — overwrite a partition, `MERGE` on a key, or a
checkpoint — is what makes retries safe. Retries are a design decision, not a checkbox.

```yaml
- task_key: load
  max_retries: 3                    # default 0; -1 retries indefinitely
  min_retry_interval_millis: 60000  # default: retry immediately
  retry_on_timeout: false           # default false: a timed-out attempt is not retried
  timeout_seconds: 1800             # default 0 = none; applies to each attempt
  health:                           # a warning, not a stop
    rules: [{metric: RUN_DURATION_SECONDS, op: GREATER_THAN, value: 1200}]
```

A **timeout** stops the task and marks it timed out; a **duration warning**
(`RUN_DURATION_SECONDS` health rule) only sends a notification. Serverless jobs add
**auto-optimization**, which can retry a failed task on its own; for a task that must
run at most once, clear "Enable serverless auto-optimization (may include additional
retries)" in the task's retry policy.

> **Measured on Free Edition:** a serverless notebook task with `max_retries: 0` was
> still retried once (attempts 0 and 1) before the run failed.

### If/else and For each

**If/else conditions** compare two values with `EQUAL_TO`, `NOT_EQUAL`,
`GREATER_THAN`, `GREATER_THAN_OR_EQUAL`, `LESS_THAN` or `LESS_THAN_OR_EQUAL`, usually
a task value against a constant. A task downstream of the condition names the branch
it belongs to with `outcome`. Keeping the branch in the job graph rather than inside a
notebook means the run history shows which path a run took.

```yaml
- task_key: drifted
  depends_on: [{task_key: check_drift}]
  condition_task: {op: EQUAL_TO, left: "{{tasks.check_drift.values.drifted}}", right: "true"}
- task_key: reprocess
  depends_on: [{task_key: drifted, outcome: "true"}]
  notebook_task: {notebook_path: ../src/reprocess.py}
```

**For each** runs one iteration of a nested task per input value, with
per-iteration visibility, retries and controllable concurrency. Adding a new value
becomes a data change rather than a job change. The nested task reads the current
value as `{{input}}`; it cannot itself be another For each.

```yaml
- task_key: per_region
  depends_on: [{task_key: list_regions}]
  for_each_task:
    inputs: "{{tasks.list_regions.values.regions}}"   # or a JSON array literal
    concurrency: 4                                    # default 1, maximum 100
    task:
      task_key: per_region_iteration
      notebook_task:
        notebook_path: ../src/load_region.py
        base_parameters: {region: "{{input}}"}
```

> **Measured on Free Edition:** a dependency on an If/else task without `outcome` is
> refused at create time ("does not specify an outcome"); `concurrency: 101` is refused
> ("must be less than or equal to 100"); an If/else task nested in a For each is
> refused.

### Retry vs repair vs a new run

| | What runs | When to use |
|---|---|---|
| **Retry** | the same task, automatically, within the same run | transient failures, idempotent task |
| **Repair run** | the failed tasks and their skipped dependants, inside the original run, with the **current** job settings; parameters can be overridden | fix the cause, then finish the run without recomputing what succeeded |
| **Run now** | the whole job as a new run | a single-task job (repair needs two or more tasks) or a clean start |

`rerun_dependent_tasks` also re-runs dependants that had **succeeded**; without it
they are left alone.

```bash
databricks jobs repair-run --json '{"run_id": 987654321,
  "rerun_all_failed_tasks": true, "job_parameters": {"fail": "false"}}' --profile FREE
databricks jobs repair-run --json '{"run_id": 987654321, "rerun_tasks": ["A"],
  "rerun_dependent_tasks": true, "latest_repair_id": 123}' --profile FREE
```

> **Measured on Free Edition:** after the `run_if` scenario, `rerun_all_failed_tasks`
> with a changed job parameter re-ran B (now passing) and the two dependants that had
> been `UPSTREAM_FAILED`; the `EXCLUDED` one and the ones that had succeeded were not
> re-run, and the run's result flipped to `SUCCESS`. With `--json`, the run id goes
> inside the JSON; the CLI refuses a positional id alongside it.

## Triggers — `ASSOC-S4-O3`, `ASSOC-S4-O4`

| Trigger | Fires | Use when |
|---|---|---|
| Scheduled (cron) | at fixed times | the cadence is genuinely time-based |
| File arrival | when files land | arrival time is unpredictable and latency matters |
| Table update | when a table changes | you depend on data, not on someone's schedule |
| Continuous | keeps running | genuinely never-ending work |

A job has **one** of `schedule`, `trigger` (periodic, file arrival or table update)
or `continuous`; you can always also start it manually or from the API.

```yaml
schedule:                                      # Quartz cron: seconds first, six or seven fields
  quartz_cron_expression: "0 30 2 * * ?"       # 02:30 every day
  timezone_id: Europe/London                   # DST zones can skip or shift an hourly run
  pause_status: UNPAUSED

trigger:                                       # one of these per job
  pause_status: UNPAUSED
  periodic: {interval: 4, unit: HOURS}         # MINUTES | HOURS | DAYS | WEEKS
  # file_arrival:
  #   url: /Volumes/main/landing/partner/      # a UC volume or external location, no wildcards
  #   min_time_between_triggers_seconds: 900   # at least 60
  #   wait_after_last_change_seconds: 120      # at least 60; a new file resets the wait
  # table_update:
  #   table_names: [main.silver.orders, main.silver.customers]   # up to 10
  #   condition: ANY_UPDATED                   # or ALL_UPDATED; required with more than one table
  #   wait_after_last_change_seconds: 60

# continuous: {pause_status: UNPAUSED}         # one run at a time, restarted with backoff on failure
```

Quartz is not Unix cron: the first field is seconds and one of day-of-month or
day-of-week must be `?`. `wait_after_last_change_seconds` is what stops a file arrival
trigger firing while a partner is still uploading a batch. A table update trigger can
watch managed or external Delta tables, materialized views, streaming tables and views
over them; the run-as principal needs `SELECT` on each, plus `USE CATALOG` and
`USE SCHEMA`.

Starting a run from the CLI, with or without new parameter values:

```bash
databricks jobs run-now 123456789 --profile FREE
databricks jobs run-now --json '{"job_id": 123456789, "job_parameters": {"env": "prod"}}' --profile FREE
```

> **Measured on Free Edition:** a five-field Unix cron (`0 8 * * *`) is refused as
> invalid Quartz; setting both `schedule` and `trigger` is refused ("One of 'schedule',
> 'trigger' or 'continuous' can be set"); `min_time_between_triggers_seconds: 30` and
> `wait_after_last_change_seconds: 30` are refused and 60 is accepted; eleven tables in
> one table update trigger are refused; a periodic trigger of 30 `MINUTES` is accepted.

### Choosing a trigger

**Choose time-based or data-driven by what you actually depend on.** If a downstream
job cares that upstream *finished*, a table update trigger decouples the two — the
upstream schedule can change and the dependency still holds. A cron offset "shortly
after upstream usually finishes" is a coupling you have to re-tune forever.

A file arrival trigger beats polling: one prompt run when there is something to
process, instead of two dozen empty runs a night.

| The question says | Choose |
|---|---|
| "every day at 06:00", a business deadline, a calendar | scheduled (cron, with a time zone) |
| "every four hours", no clock time matters | periodic |
| files arrive "at unpredictable times", "as soon as they land" | file arrival |
| "whenever the upstream table is updated", "the upstream schedule changes" | table update |
| "always on", lowest latency, never finishes | continuous (or a streaming pipeline) |
| "the upstream task in the same job" | a dependency, not a trigger |

### Overlapping runs

**`max_concurrent_runs` defaults to 1.** What happens to a run that starts while
another is active depends on queueing: with `queue.enabled` (the default on new jobs)
the new run **waits** in the queue, for up to 48 hours. With queueing off, it is
**skipped**, and a job that consistently overruns its schedule silently halves its
frequency. Raise `max_concurrent_runs` only if two runs can safely overlap.

```yaml
max_concurrent_runs: 1   # default; 0 to 1000
queue:
  enabled: true          # default on new jobs; false = skip an overlapping run
```

> **Measured on Free Edition:** a job created through the API with no settings came
> back with `queue.enabled: true`, `max_concurrent_runs: 1`, `timeout_seconds: 0` and
> `run_if: ALL_SUCCESS` on its task; an overlapping run was `QUEUED`, and was skipped
> (`MAX_CONCURRENT_RUNS_EXCEEDED`) only with queueing off. `max_concurrent_runs: 1001`
> is refused ("must be in the range [0, 1000]"). Free Edition also caps the workspace
> at five active runs, so runs can queue there for reasons a real workspace would not
> have.

## Further reading

Official documentation for what this section tests, one link per topic:

- [Lakeflow Jobs](https://docs.databricks.com/aws/en/jobs/) — the top of the jobs documentation.
- [Configure and edit jobs](https://docs.databricks.com/aws/en/jobs/configure-job) — tasks, compute, parameters and notifications.
- [Configure tasks](https://docs.databricks.com/aws/en/jobs/configure-task) — task types, retries, timeouts and duration warnings.
- [Compute for jobs](https://docs.databricks.com/aws/en/jobs/compute) — job clusters, sharing a cluster between tasks, serverless.
- [Serverless jobs](https://docs.databricks.com/aws/en/jobs/run-serverless-jobs) — auto-optimization and its extra retries.
- [Control the flow of tasks](https://docs.databricks.com/aws/en/jobs/control-flow) — dependencies, conditions, branching and loops.
- [Run if conditions](https://docs.databricks.com/aws/en/jobs/run-if) — the six `run_if` values.
- [For each tasks](https://docs.databricks.com/aws/en/jobs/for-each) — looping over a list with a concurrency cap.
- [Task values](https://docs.databricks.com/aws/en/jobs/task-values) — passing results between tasks.
- [Job and task parameters](https://docs.databricks.com/aws/en/jobs/parameters) — parameters, widgets and dynamic value references.
- [Job parameters](https://docs.databricks.com/aws/en/jobs/job-parameters) — push-down to tasks and which value wins.
- [Dynamic value references](https://docs.databricks.com/aws/en/jobs/dynamic-value-references) — every `{{ }}` reference.
- [Trigger types](https://docs.databricks.com/aws/en/jobs/triggers) — schedule, continuous, file arrival and table update.
- [Scheduled triggers](https://docs.databricks.com/aws/en/jobs/scheduled) — Quartz cron, time zones and daylight saving.
- [File arrival triggers](https://docs.databricks.com/aws/en/jobs/file-arrival-triggers) — the settings that stop a trigger firing on half-written data.
- [Table update triggers](https://docs.databricks.com/aws/en/jobs/trigger-table-update) — which tables, any or all, and the waits.
- [Concurrency and queueing](https://docs.databricks.com/aws/en/jobs/advanced) — maximum concurrent runs and the run queue.
- [Repair job failures](https://docs.databricks.com/aws/en/jobs/repair-job-failures) — what a repair run re-executes.
- [`jobs` CLI commands](https://docs.databricks.com/aws/en/dev-tools/cli/reference/jobs-commands) — `run-now`, `repair-run` and the rest.

Videos for another angle on the hard parts (channel, length):

- [Databricks Lakeflow Jobs Tutorial: exploring the Jobs UI step by step](https://www.youtube.com/watch?v=xnuQ94qLsWc) — DataMindAI with Ahmed, 27 min. Every screen the exam describes in words, shown.
