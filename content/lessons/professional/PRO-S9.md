# Debugging and Deploying — 10%

Half of this section is reading what the platform tells you when something
fails. The other half is the case the exam likes best: **nothing failed, and the
data is wrong anyway.** Plus the deployment path that gets code from a branch to
a workspace without a person clicking.

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

## Repairing runs and overriding parameters — `PRO-S9-O2`

A multi-task job that fails partway does **not** roll back what earlier tasks
committed. **Repair** re-executes only the failed tasks and their dependants,
which is why idempotent tasks matter: a repaired task runs again from the start.

```bash
databricks jobs list-runs --job-id <id>
databricks jobs repair-run <run-id> --rerun-tasks failed_task
databricks jobs repair-run <run-id> --job-parameters '{"cutoff":"2026-03-01"}'
```

Parameter overrides on repair (and on `run-now`) re-run a task against a
corrected input without editing and redeploying the job. Job-level parameters
reach notebooks as widgets; task values pass small results between tasks.

## Debugging pipelines — `PRO-S9-O3`

A declarative pipeline's **event log** is the record: every update, every flow,
expectation counts, and the error with its error class when a flow fails. Query
it as a table to see which expectation started dropping rows and when. The
pipeline's Spark UI answers the same questions as a job's (a stage that skews, a
shuffle that spills). For a hand-rolled Structured Streaming job, the checkpoint
is where state lives; a stream that "does nothing" on restart usually has a
checkpoint that already consumed the input, and a stream that reprocesses
everything has lost it.

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

One trap worth knowing: if `DATABRICKS_CONFIG_PROFILE` is set in your shell, the
CLI resolves that profile and ignores `DATABRICKS_CLIENT_ID` and `SECRET`, so a
local test of CI authentication runs as *you* and appears to succeed.

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
