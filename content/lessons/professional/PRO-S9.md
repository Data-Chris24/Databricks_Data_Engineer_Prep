# Debugging and Deploying — 10%

Half of this section is reading what the platform tells you when something
fails. The other half is the case the exam likes best: **nothing failed, and the
data is wrong anyway.** Plus the deployment path that gets code from a branch to
a workspace without a person clicking.

> **Names:** Lakeflow Jobs (Workflows, Databricks Jobs), Lakeflow Spark
> Declarative Pipelines (Delta Live Tables, DLT), Declarative Automation Bundles
> (Databricks Asset Bundles, DABs), Git folders (Repos), Standard / Dedicated
> access mode (Shared / Single user). The CLI still says `databricks repos` for
> Git folders and `databricks bundle` for bundles; old names also turn up in
> distractors.

## What the exam asks

- A stage's slowest task takes ten times the median and spill is zero — skew, read from the stage's Summary Metrics in the Spark UI (`PRO-S9-O1`)
- A three-task job failed at task two; fix the input and finish without redoing task one — a repair run with a job-parameter override (`PRO-S9-O2`)
- A pipeline is green but a table has fewer rows each day — the event log's `flow_progress` expectation counts (`PRO-S9-O3`)
- A stream was changed to aggregate by a new key and will not restart — a stateful change the checkpoint cannot accept, so a new checkpoint (`PRO-S9-O3`)
- A job made by hand in the UI must come under the bundle without being recreated — `bundle generate job` then `bundle deployment bind` (`PRO-S9-O4`)
- CI must deploy without a personal token — a service principal over OAuth (M2M secret or GitHub OIDC) set by environment variables (`PRO-S9-O5`)

## Defaults and limits

| Setting | Default or limit | Note |
|---|---|---|
| Repair eligibility | jobs with **2 or more** tasks | a single-task job is re-run with Run now |
| Repair needs `latest_repair_id` | from the second repair on | the first repair of a run does not need it |
| Task values | **48 KiB** per value (JSON) | for small results, not data |
| Job run history in the UI | **60 days** | `system.lakeflow` job tables keep **365 days** |
| Compute event log | **60 days** | the Event log tab of classic compute |
| Cluster log delivery | every **5 minutes** | to `<destination>/<cluster-id>/driver` and `/executor` |
| Task `max_retries` | 0 on classic compute | serverless retries on its own (see the callout below) |
| Job and task `timeout_seconds` | 0, meaning no timeout | set it, or a hung task runs until cancelled |
| CLI `--timeout` on `run-now` / `repair-run` | 20 minutes | how long the CLI waits, not a job setting |
| Skew rule of thumb | Max task time ≥ **1.5 ×** the 75th percentile | from the Spark UI diagnosis guide |
| Git folder working branch | **1 GB** | each Git operation is capped at 2 GB memory and 4 GB disk writes |
| Assets in a Git folder | about **20,000** recommended maximum | sparse checkout for larger repos |

## Diagnostic sources — `PRO-S9-O1`

Databricks error messages carry an **error class** (`CAST_INVALID_INPUT`,
`DELTA_SOURCE_TABLE_IGNORE_CHANGES`) and a SQLSTATE. Both are searchable, and the
class is stable across versions in a way the prose is not. Read the class first.

| Source | Answers |
|---|---|
| The error message | what broke, often how to fix it |
| Run history | which task, and whether it is new or has always been slow |
| `DESCRIBE HISTORY` | what the table did, and when |
| Query profile | where the time and bytes went in one query |
| Spark UI | which stage, skew, spill, shuffle |
| Cluster logs | driver and executor detail (classic compute only) |
| System tables | cost, audit and run history across the workspace |

Start narrow. Opening logs before checking whether the run is simply slower than
last week wastes the easy answer. When a cast fails, `try_cast` turns "it failed"
into "here are the three rows responsible".

### Spark UI failure signatures

Databricks' Spark UI guide walks one path: the **jobs timeline** first, then the
longest stage, then that stage's detail page. Each failure has a fingerprint:

| What you see | Where | Means | First fix |
|---|---|---|---|
| Red failed jobs or removed executors | jobs timeline | a task failed, or executors were lost (autoscaling, spot reclaim, or memory) | open the failed stage's reason, then the failed tasks; the compute Event log shows resizes and spot loss |
| Max task duration ≥ 1.5 × the 75th percentile | stage page, **Summary Metrics** | skew: one partition holds far more data | check AQE skew join covers it (sort-merge and shuffle-hash joins only, not broadcast), salt the key, or pre-aggregate |
| Spill figures appear in the stage details | stage page, top | the stage ran out of execution memory and wrote to disk | `spark.sql.shuffle.partitions=auto`, fewer columns in memory, more memory per executor |
| Gaps of a minute or more between jobs | jobs timeline | plain Python on the driver, a huge plan (`withColumn` in a loop), an overloaded driver, or simply no work | move the work into Spark; check the driver's load in the compute Metrics |
| Many thin jobs of a few seconds | jobs timeline | many operations on small data, each paying a fixed overhead | combine them, or parameterize one notebook under a For each task |
| No skew, no spill, long stage | stage page | I/O bound: reading too much | check file pruning in the query profile |

Serverless compute has **no Spark UI and no Spark logs**; the query profile
replaces it, from Query History, the notebook cell, or the job or pipeline run.
That is why the Free Edition lab for this objective is partial.

### Cluster logs and their delivery

Classic compute exposes three kinds of log: the **compute event log** (start,
resize, terminate; kept 60 days), **driver logs** (standard output, standard
error and Log4j), and **worker logs** (through the Spark UI's Executors tab).
They disappear with the cluster unless you deliver them:

```json
"cluster_log_conf": {
  "volumes": { "destination": "/Volumes/main/ops/cluster_logs" }
}
```

The destination is one of `volumes` (recommended with Unity Catalog), `s3` or
`dbfs` (legacy). Logs arrive every five minutes under
`<destination>/<cluster-id>/driver`, `/executor` and, with init scripts,
`/init_scripts`. Volume delivery needs Standard access mode or Dedicated mode
assigned to a user (not to a group), plus `READ VOLUME` and `WRITE VOLUME` for
the compute's owner. Driver stdout and stderr are not redacted, so a printed
secret is visible to anyone who can read them.

For history beyond one run, query the system tables:

```sql
SELECT job_id, run_id, task_key, result_state, termination_code, period_start_time
FROM system.lakeflow.job_task_run_timeline
WHERE result_state <> 'SUCCEEDED'
  AND period_start_time > current_timestamp() - INTERVAL 7 DAYS;
```

`termination_code` separates your code failing (`RUN_EXECUTION_ERROR`) from the
platform failing (`CLUSTER_ERROR`). `jobs` and `job_tasks` are slowly changing
(a new row per change); the two timeline tables are append-only. Note the
spelling: the system tables say `SUCCEEDED` where the Jobs API and the run page
say `SUCCESS`.

> **Measured on Free Edition:** over 30 days the task timeline held the states
> `SUCCEEDED`, `FAILED`, `SKIPPED`, `CANCELLED` and `ERROR`, with termination
> codes such as `WORKSPACE_RUN_LIMIT_EXCEEDED` (the workspace's concurrent-task
> cap), `MAX_CONCURRENT_RUNS_EXCEEDED` and `INVALID_RUN_CONFIGURATION`. A
> scratch job's runs had not appeared there minutes after they finished, so the
> tables are for trends, not for the run that just failed.

## Repairing runs and overriding parameters — `PRO-S9-O2`

A multi-task job that fails partway does **not** roll back what earlier tasks
committed. **Repair** re-executes only the failed tasks and the dependants that
were skipped because of them (a dependant that had already succeeded is re-run
only if you ask, with `rerun_dependent_tasks`), which is why idempotent tasks
matter: a repaired task runs again from the start.

```
original run          repair (rerun_all_failed_tasks)
a  SUCCESS      ──►   a  not re-run, its commits stand
b  FAILED       ──►   b  re-run from the start, current job settings
c  UPSTREAM_FAILED ─► c  re-run (it was skipped, not successful)
```

Three request fields decide what runs again:

| Field | Re-runs |
|---|---|
| `rerun_all_failed_tasks: true` | every failed task and the tasks skipped because of them |
| `rerun_tasks: ["a"]` | exactly the listed tasks, failed or not |
| `rerun_tasks` + `rerun_dependent_tasks: true` | the listed tasks and everything downstream, even tasks that succeeded; each re-evaluates its `run_if` |

A repair runs with the job's **current** settings, so you can fix a notebook
path or a cluster first. A run that shared a job cluster gets a new one with a
`_v1` suffix. The run must not be in progress, and from the second repair on you
must pass the ID of the previous one.

```bash
databricks jobs list-runs --job-id <job-id>
databricks jobs get-run <run-id> --include-history     # repair_history, task attempts
databricks jobs repair-run <run-id> --rerun-all-failed-tasks
databricks jobs repair-run --json '{
  "run_id": <run-id>,
  "rerun_tasks": ["b"],
  "rerun_dependent_tasks": true,
  "latest_repair_id": <previous-repair-id>,
  "job_parameters": {"cutoff": "2026-03-01"}
}'
databricks jobs run-now --json '{"job_id": <job-id>, "job_parameters": {"cutoff": "2026-03-01"}}'
databricks bundle run my_job --params cutoff=2026-03-01 --only b   # from a bundle
```

`repair-run` has flags only for the two booleans and `--latest-repair-id`;
`rerun_tasks` and `job_parameters` go in `--json`, which then has to carry
`run_id` too.

Parameter overrides on repair (and on `run-now`) re-run a task against a
corrected input without editing and redeploying the job. Job-level parameters
reach notebooks as widgets (`dbutils.widgets.get("cutoff")`); task values pass
small results between tasks:

```python
dbutils.jobs.taskValues.set(key="row_count", value=n)                 # in task a
n = dbutils.jobs.taskValues.get(taskKey="a", key="row_count", default=0)  # in task b
```

> **Measured on Free Edition:** on a three-task serverless job (October 2026),
> `repair-run --rerun-tasks` was rejected as an unknown flag (CLI v1.6.0). A
> repair with `rerun_all_failed_tasks` and `job_parameters: {"mode": "fixed"}`
> re-ran the failed task and its skipped dependant and left the successful first
> task alone. A second repair without `latest_repair_id` was refused with "The
> latest repair ID needs to be provided". `rerun_tasks: ["a"]` alone re-ran only
> `a`; adding `rerun_dependent_tasks` re-ran `a`, `b` and `c`. That third repair
> passed no parameters and `b` ran with the job default again: an override
> applies to the repair it is sent with, not to later ones. A run that had
> already succeeded could still be repaired. Serverless retried each failed
> notebook task once on its own (`attempt_number` 1) with `max_retries` unset.
> On a second job, `rerun_all_failed_tasks` left an `EXCLUDED` task and two
> `ALL_FAILED` handlers that had run alone. Re-running the fixed task with
> `rerun_dependent_tasks` re-ran those two handlers too, and both ended `EXCLUDED`
> ("One or more upstream tasks succeeded").

![Fail a task, run the job, then repair it both ways and compare what is kept](visual:job-dag-repair?h=1250)

## Debugging pipelines — `PRO-S9-O3`

A declarative pipeline's **event log** is the record: every update, every flow,
expectation counts, and the error with its error class when a flow fails. Query
it as a table to see which expectation started dropping rows and when.

```sql
-- by pipeline ID, or by any streaming table or materialized view it defines
SELECT timestamp, event_type, message FROM event_log('<pipeline-id>');
SELECT * FROM event_log(TABLE(main.sales.orders_st));

SELECT timestamp,
       e.name, e.dataset, e.passed_records, e.failed_records
FROM event_log('<pipeline-id>'),
     LATERAL explode(from_json(details:flow_progress.data_quality.expectations,
       'array<struct<name:string,dataset:string,passed_records:bigint,failed_records:bigint>>')) AS t(e)
WHERE event_type = 'flow_progress';
```

| `event_type` | Holds |
|---|---|
| `create_update` | what started an update, and with which settings |
| `update_progress` | the update's state changes, and the error when it fails |
| `flow_progress` | per-flow state, rows, and `data_quality` (expectations, `dropped_records`) |
| `flow_definition` | each flow's schema and plan |
| `user_action` | who started, stopped or edited the pipeline |
| `cluster_resources` | task slots and autoscaling |

By default only the pipeline's run-as user can query the event log; publish it to
Unity Catalog (the pipeline's `event_log` setting with `catalog`, `schema` and
`name`) to share it. Expectation counts live only on `flow_progress`; a FAILED
`update_progress` event carries the error and no counts. On classic compute the
pipeline's Spark UI answers the same questions as a job's (a stage that skews, a
shuffle that spills); on serverless the pipeline UI links to the query profile.

> **Measured on Free Edition:** `event_log()` on a managed table fails with
> `EVENT_LOG_UNSUPPORTED_TABLE_TYPE` (only materialized views, streaming tables
> and pipelines), and an unknown ID gives `PIPELINE_DOES_NOT_EXIST`.

### When to reset a checkpoint

For a hand-rolled Structured Streaming job, the checkpoint is where state lives;
a stream that "does nothing" on restart usually has a checkpoint that already
consumed the input, and a stream that reprocesses everything has lost it. A
checkpoint belongs to one query and cannot be shared. Some code changes keep it
valid; others make the restart fail or, worse, run with wrong state:

| Change | Same checkpoint? |
|---|---|
| Add or remove a filter; a projection with the same output schema | yes |
| Rate limits (`maxFilesPerTrigger`, `maxBytesPerTrigger`, `maxOffsetsPerTrigger`) | yes |
| Trigger type or interval | yes |
| Kafka output topic | yes |
| Number or type of input sources | no (named sources on newer runtimes can evolve) |
| Subscribed topic, or the source path | no |
| File sink output directory | no |
| Grouping keys, aggregates or state schema of an aggregation, `dropDuplicates`, stream-stream join | no |

```python
(spark.readStream.table("bronze.orders")
   .groupBy("region").count()               # changing the key breaks the checkpoint
   .writeStream
   .option("checkpointLocation", "/Volumes/main/ops/chk/orders_by_region_v2")  # new path = fresh start
   .trigger(availableNow=True)
   .toTable("silver.orders_by_region"))
```

Reset only when the change is on the "no" side, and decide what the restart will
read: a new checkpoint on a Delta source starts from the table's beginning unless
you set `startingVersion` or `startingTimestamp`, and an append sink then gets
every row again, so clear or rebuild the target too. Do **not** reset for
`DELTA_SOURCE_TABLE_IGNORE_CHANGES` (an upstream update or delete): set
`skipChangeCommits` on the reader and keep the checkpoint. In a pipeline the
same reset is a **full refresh**, which clears a streaming table's data and
checkpoints together:

```bash
databricks pipelines start-update <pipeline-id> --full-refresh
databricks bundle run my_pipeline --full-refresh orders_st   # one table
```

## Deploying with bundles — `PRO-S9-O4`

```bash
databricks bundle validate -t prod    # configuration only, never runs code
databricks bundle deploy -t prod      # uploads files, creates or updates resources
databricks bundle run my_job -t prod  # triggers a job, or deploys and starts an app
```

`validate` checks configuration and resolves variables; it is not a test run.
`deploy` is idempotent and records the deploying identity in the workspace path
(`/Users/<deployer>/.bundle/<name>/<target>`). Development mode prefixes resource
names with `[dev <user>]` and pauses schedules; production mode does neither and
expects a single deployer. Environment-specific values are **variables overridden
per target**, never edits to the YAML.

```yaml
variables:
  catalog:
    default: dev_catalog
targets:
  dev:
    mode: development
    default: true
  prod:
    mode: production
    workspace:
      root_path: /Workspace/Users/${workspace.current_user.userName}/.bundle/${bundle.name}/${bundle.target}
    variables:
      catalog: prod_catalog
```

The flags the exam leans on:

```bash
databricks bundle validate --strict -t prod          # warnings become errors
databricks bundle deploy -t prod --var catalog=hotfix # override a variable (or BUNDLE_VAR_catalog=hotfix)
databricks bundle deploy -t prod --fail-on-active-runs  # refuse while a job or pipeline is running
databricks bundle deploy -t prod --force-lock        # take a deployment lock left by a dead deploy
databricks bundle deploy -t prod --auto-approve      # no prompt before deleting or recreating resources
databricks bundle destroy -t dev --auto-approve      # delete everything the target deployed
```

`DATABRICKS_BUNDLE_TARGET=prod` picks the target without `-t`, which is how the
GitHub Actions examples do it.

### Bringing existing resources under a bundle

A job or pipeline made by hand is not lost or recreated; it is generated and
bound:

```bash
databricks bundle generate job --existing-job-id 6565621249 --key my_etl_job
#   writes resources/my_etl_job.job.yml and downloads its notebooks to src/
databricks bundle deployment bind my_etl_job 6565621249 -t prod --auto-approve
databricks bundle deploy -t prod     # the bound job now follows the YAML
databricks bundle deployment unbind my_etl_job -t prod   # let go without deleting
```

`generate` only writes local files (`--bind` does both steps at once). After
`bind`, the next deploy **overwrites** the job with the bundle's definition and
`destroy` **deletes** it; `unbind` is how you hand it back to the UI. `generate`
also covers `pipeline`, `dashboard`, `app` and `alert`.

> **Measured on Free Edition:** `bundle generate job` wrote the YAML under
> `resources/` but did not add an `include:` for it, so `validate` resolved no
> jobs until `include: [resources/*.yml]` was added. `validate` created an empty
> `.bundle/<name>/<target>` folder in the workspace. A production target without
> `workspace.root_path` got a *recommendation* to set one and still exited 0,
> even with `--strict`. `deploy --fail-on-active-runs` stopped with "job … is
> running" while a repair was in progress. A bound job's name gained the
> `[dev <user>]` prefix on the first development-mode deploy.

## Git-based CI/CD — `PRO-S9-O5`

```
branch → pull request → checks → merge → deploy
```

- **Git folders** (formerly Repos) put a branch in the workspace so notebooks can
  be edited and run against real compute, then committed. The folder tracks one
  branch; switching branches switches every notebook in it.
- **CI** runs the checks on the pull request (validation, unit tests, `bundle
  validate`) with no credentials to production.
- **CD** runs on merge to `main`, re-validates, then `bundle deploy` as a
  **service principal** over OAuth M2M, never as a person. The deploy re-runs
  tests because two individually valid pull requests can merge into a broken
  `main`.

```yaml
# .github/workflows/deploy.yml
permissions:
  id-token: write        # GitHub OIDC (workload identity federation)
  contents: read
jobs:
  deploy:
    runs-on: ubuntu-latest
    env:
      DATABRICKS_HOST: ${{ vars.DATABRICKS_HOST }}
      DATABRICKS_CLIENT_ID: ${{ secrets.DATABRICKS_CLIENT_ID }}   # service principal UUID
      DATABRICKS_AUTH_TYPE: github-oidc
      # or, with an OAuth secret instead of OIDC:
      # DATABRICKS_CLIENT_SECRET: ${{ secrets.DATABRICKS_CLIENT_SECRET }}
    steps:
      - uses: actions/checkout@v4
      - uses: databricks/setup-cli@main
      - run: databricks bundle validate --strict -t prod
      - run: databricks bundle deploy -t prod
```

`databricks/setup-cli` installs the CLI; the CLI then authenticates from
environment variables alone (`DATABRICKS_HOST`, `DATABRICKS_TOKEN`,
`DATABRICKS_CLIENT_ID`, `DATABRICKS_CLIENT_SECRET`, `DATABRICKS_AUTH_TYPE`,
`DATABRICKS_CONFIG_PROFILE`). OIDC is the better answer: no long-lived secret in
the repository at all. A personal access token in CI is the distractor.

One trap worth knowing: if `DATABRICKS_CONFIG_PROFILE` is set in your shell, the
CLI resolves that profile and ignores `DATABRICKS_CLIENT_ID` and `SECRET`, so a
local test of CI authentication runs as *you* and appears to succeed.

For deploying code without bundles, the pattern is a **production Git folder**
outside user folders, pointed at the deployment branch, updated only by
automation after a merge and run-only for everyone else:

```bash
databricks repos create https://github.com/org/etl gitHub --path /Workspace/Shared/etl_prod
databricks repos update /Workspace/Shared/etl_prod --branch main   # pull the latest commit
databricks repos update /Workspace/Shared/etl_prod --tag v1.4.0    # or pin a release
```

Databricks recommends bundles over this: a Git folder moves code, a bundle also
moves the jobs, pipelines and permissions around it.

> **Measured on Free Edition:** `repos create` of a public GitHub repository
> needed no Git credential; `repos update <path> --branch <name>` moved the
> folder's `head_commit_id` to that branch's tip, and the command accepted the
> workspace path in place of the numeric ID.

## The failure that does not raise

Everything above assumes something failed. The dangerous failures do not:

| Silent failure | Run state | How it shows |
|---|---|---|
| An upstream source stops arriving | SUCCESS | row count drops |
| A join starts dropping rows | SUCCESS | row count drops |
| A cast starts failing | SUCCESS | null rate rises |
| A filter's assumption breaks | SUCCESS | count moves either way |

None of these raise. The run is green, the alert never fires, and the data is
wrong until somebody downstream notices. **The only reliable detector is a
trend**: compare this run's row count, null rate, or per-source contribution
against the previous runs. For a table rebuilt on a schedule, `DESCRIBE HISTORY`
holds the operation metrics of every version; for a job, the run history holds
durations. A version that wrote noticeably fewer rows than the one before, with
no error anywhere, is the shape of a silent regression. That comparison is the
whole technique, and it is this section's assignment.

## Further reading

Official documentation for what this section tests, one link per topic:

- [Troubleshoot and repair job failures](https://docs.databricks.com/aws/en/jobs/repair-job-failures) — what a repair re-runs.
- [Monitor jobs](https://docs.databricks.com/aws/en/jobs/monitor) — run history and task-level durations.
- [Task values](https://docs.databricks.com/aws/en/jobs/task-values) — passing small results between tasks, and the 48 KiB limit.
- [Jobs system tables](https://docs.databricks.com/aws/en/admin/system-tables/jobs) — `system.lakeflow` run timelines and termination codes.
- [Diagnose with the Spark UI](https://docs.databricks.com/aws/en/optimizations/spark-ui-guide/) — the failure fingerprints.
- [Skew and spill in the Spark UI](https://docs.databricks.com/aws/en/optimizations/spark-ui-guide/long-spark-stage-page) — the Max vs 75th percentile rule.
- [Failing jobs or removed executors](https://docs.databricks.com/aws/en/optimizations/spark-ui-guide/failing-spark-jobs) — reading a failed stage.
- [Compute log delivery](https://docs.databricks.com/aws/en/compute/configure#compute-log-delivery) — destinations and the five-minute delivery.
- [Query profile](https://docs.databricks.com/aws/en/sql/user/queries/query-profile) — the serverless replacement for the Spark UI.
- [Pipeline observability](https://docs.databricks.com/aws/en/ldp/observability) — the event log and its error payloads.
- [Query the event log](https://docs.databricks.com/aws/en/ldp/monitor-event-logs) — `event_log()`, event types and the `data_quality` path.
- [Structured Streaming checkpoints](https://docs.databricks.com/aws/en/structured-streaming/checkpoints) — which query changes a checkpoint survives.
- [Error classes](https://docs.databricks.com/aws/en/error-messages/) — the `SQLSTATE` and error-class reference.
- [Declarative Automation Bundles](https://docs.databricks.com/aws/en/dev-tools/bundles/) — the bundles home.
- [Bundle commands](https://docs.databricks.com/aws/en/dev-tools/cli/bundle-commands) — every `bundle` subcommand and flag.
- [Migrate existing resources to a bundle](https://docs.databricks.com/aws/en/dev-tools/bundles/migrate-resources) — `generate` and `deployment bind`.
- [Deployment modes](https://docs.databricks.com/aws/en/dev-tools/bundles/deployment-modes) — development vs production.
- [Bundle variables](https://docs.databricks.com/aws/en/dev-tools/bundles/variables) — per-target values.
- [CI/CD on Databricks](https://docs.databricks.com/aws/en/dev-tools/ci-cd/) — the recommended pipeline.
- [GitHub Actions](https://docs.databricks.com/aws/en/dev-tools/ci-cd/github) — authenticating and deploying from CI.
- [Authentication environment variables](https://docs.databricks.com/aws/en/dev-tools/auth/env-vars) — the `DATABRICKS_*` names.
- [OAuth for service principals](https://docs.databricks.com/aws/en/dev-tools/auth/oauth-m2m) — M2M authentication for CI.
- [Git folders](https://docs.databricks.com/aws/en/repos/) — pull-based deployment.
- [Git folders in CI/CD](https://docs.databricks.com/aws/en/repos/ci-cd) — the production Git folder pattern.
- [Git folder limits](https://docs.databricks.com/aws/en/repos/limits) — branch size and file count.

Videos for another angle on the hard parts (channel, length):

- [CI/CD for Databricks: Advanced Asset Bundles and GitHub Actions](https://www.youtube.com/watch?v=XumUXF1e6RI) — Databricks, 41 min. The conference talk on the pattern this repo uses.
- [Automate Databricks deployments with Asset Bundles and GitHub Actions](https://www.youtube.com/watch?v=kStRXqCznHA) — Data & AI Espresso, 30 min. A full pipeline with OIDC.
- [Deploy Faster: Databricks Asset Bundles + Git Explained](https://www.youtube.com/watch?v=FZpgwclX88Q) — Databricks Skill Builder, 23 min. Bundles and Git folders compared.
