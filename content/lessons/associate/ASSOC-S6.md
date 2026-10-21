# Troubleshooting, Monitoring and Optimization — 10%

Reading what the platform tells you, and knowing which knob matches which symptom.

> **Names:** Lakeflow Jobs (Workflows, Databricks Jobs), Standard access mode (Shared), Dedicated access mode (Single user), Lakeflow Spark Declarative Pipelines (Delta Live Tables) for the pipeline runs a job may contain.

## What the exam asks

- A job went green but took 90 minutes instead of 20; where do you look first — the run history and matrix view, comparing task durations against earlier runs (`ASSOC-S6-O1`)
- A downstream task shows `Upstream failed` and never ran — the task it depends on failed, and its `run_if` was the default `ALL_SUCCESS` (`ASSOC-S6-O2`)
- On a stage's Summary Metrics, Max task duration is 8x the 75th percentile — data skew; check AQE skew join, then salt or cluster (`ASSOC-S6-O3`)
- A table is filtered on two high-cardinality columns and its access pattern changes every quarter — liquid clustering with `CLUSTER BY`, not partitioning or Z-order (`ASSOC-S6-O4`)
- Which tables does predictive optimization maintain, and what does it run — Unity Catalog managed tables only; `OPTIMIZE`, `VACUUM` and `ANALYZE` (`ASSOC-S6-O4`)
- `toPandas()` on a large result kills the notebook with "The spark driver has stopped unexpectedly" — driver OOM; more workers do not help (`ASSOC-S6-O5`)

## Defaults and limits

| Setting | Default or limit | Note |
|---|---|---|
| Job run history | 60 days | export runs you need to keep before they expire |
| `max_concurrent_runs` | 1 | new jobs, UI or API |
| `timeout_seconds` (job and task) | 0 | 0 means no timeout |
| `run_if` | `ALL_SUCCESS` | so a failed upstream task leaves its dependants `Upstream failed` |
| `spark.sql.shuffle.partitions` | 200 | set to `auto` to let Databricks choose |
| `spark.sql.autoBroadcastJoinThreshold` | 10 MB | static planning; AQE's runtime threshold on Databricks is 30 MB |
| AQE skew split | partition > 5x the median **and** > 256 MB | `skewedPartitionFactor`, `skewedPartitionThresholdInBytes` |
| `spark.sql.adaptive.advisoryPartitionSizeInBytes` | 64 MB | AQE's target when coalescing or splitting |
| Skew rule of thumb in the Spark UI | Max ≥ 1.5x the 75th percentile | from the Databricks Spark UI guide |
| Liquid clustering keys | 4 | a fifth fails with `DELTA_CLUSTER_BY_INVALID_NUM_COLUMNS` |
| Statistics columns | first 32 | `delta.dataSkippingNumIndexedCols`; clustering keys need statistics |
| `VACUUM` retention | 7 days (168 hours) | `delta.deletedFileRetentionDuration` |
| Delta log retention | 30 days | `delta.logRetentionDuration`; bounds time travel along with VACUUM |
| `VACUUM ... DRY RUN` | lists up to 1,000 files | deletes nothing |
| Partitioning guidance | don't partition under 1 TB; each partition ≥ 1 GB | otherwise cluster |

## Monitoring jobs — `ASSOC-S6-O1`, `ASSOC-S6-O2`

Run history is where an investigation starts. Comparing a slow run's task durations
against previous runs localises the problem before you open a single log — if one task
went from 2 minutes to 70 while the rest held steady, you know where to look.

**A successful run can still be unhealthy.** A job that normally takes 20 minutes and
took 90 has told you something, even though it went green. Left alone that becomes a
missed SLA or a quota breach.

Where each question is answered in the Jobs UI:

| Question | View |
|---|---|
| Is this run slower than usual? | **Runs** tab, **matrix view**: one column per run, one cell per task; bar height is duration, colour is status |
| Which task is the long one? | the run's **timeline** view |
| What stopped this task from starting? | the run's **graph** (DAG): the red or grey upstream task |
| How often does it fail? | the job's run list (60 days), or **Job runs** across all jobs |
| Tell me before it gets bad | a duration **Warning** threshold and a **Timeout** on the job |

**Run states.** A run has a life cycle state and, once it ends, a result. The UI
labels and the API names differ; the exam uses the UI words.

| UI status | API `result_state` | What happened |
|---|---|---|
| Succeeded | `SUCCESS` | every task that had to run, ran and passed |
| Succeeded with failures | `SUCCESS_WITH_FAILURES` | some tasks failed, but every leaf task succeeded — e.g. an `ALL_DONE` clean-up leaf |
| Failed | `FAILED` | a task raised an error |
| Timed out | `TIMEDOUT` | it passed `timeout_seconds` |
| Canceled | `CANCELED` | someone or something stopped it |
| Upstream failed | `UPSTREAM_FAILED` | never ran: its `run_if` (`ALL_SUCCESS`, `AT_LEAST_ONE_SUCCESS` or `NONE_FAILED`) was not met |
| Upstream canceled | `UPSTREAM_CANCELED` | never ran, because a dependency was canceled |
| Skipped | `MAXIMUM_CONCURRENT_RUNS_REACHED` | never started: the job was at `max_concurrent_runs` with queueing off |
| Excluded | `EXCLUDED` | a failure-handling task (`AT_LEAST_ONE_FAILED`, `ALL_FAILED`) whose condition was not met, or the branch an If/else task did not take; counts as success |

Before a run ends its life cycle state moves through `QUEUED`, `PENDING`,
`BLOCKED` (waiting on upstream tasks), `RUNNING` and `TERMINATED`, or `SKIPPED` for a
task that never started. The run's own result is decided by its leaf tasks.

`run_if` decides whether a task runs after its dependencies: `ALL_SUCCESS` (the
default), `ALL_DONE`, `NONE_FAILED`, `AT_LEAST_ONE_SUCCESS`, `ALL_FAILED`,
`AT_LEAST_ONE_FAILED`. A clean-up task is usually `ALL_DONE`, which always runs; an
alerting task `AT_LEAST_ONE_FAILED`, which shows `Excluded` on a good day. A task marked
`Upstream failed` counts as failed to the tasks below it.

```bash
# Duration warning and hard timeout on a job, as the API and bundles spell them
#   "timeout_seconds": 3600,                      # default 0 = never time out
#   "health": {"rules": [{"metric": "RUN_DURATION_SECONDS",
#                         "op": "GREATER_THAN", "value": 1800}]},
#   "email_notifications": {"on_duration_warning_threshold_exceeded": ["me@example.com"]}

# Run history from the CLI: one line per run, with its result and duration
databricks jobs list-runs --job-id <JOB_ID> --limit 25 -o json \
  | jq -r '.[] | [.run_id, .state.result_state, .run_duration] | @tsv'

# Per-task results of one run
databricks jobs get-run <RUN_ID> -o json \
  | jq -r '.tasks[] | [.task_key, .run_if, .state.result_state] | @tsv'
```

> **Measured on Free Edition:** a one-time serverless run in which one task raised an
> error (2026-10-20). The failing task was tried twice (`attempt_number` 0 and 1) with no
> retry policy set, and ended `FAILED`. Its default-`run_if` dependant and a `NONE_FAILED`
> dependant ended with life cycle `SKIPPED` and result `UPSTREAM_FAILED` ("An upstream
> task failed."). Its `ALL_DONE` and `AT_LEAST_ONE_FAILED` dependants ran and succeeded.
> The run as a whole: `FAILED`. While other runs were active, a task sat in
> `QUEUED` with "There are already 5 active runs (limit: 5)": Free Edition caps
> active runs across the workspace at five. A job created through the API here came back
> with `max_concurrent_runs: 1`, `timeout_seconds: 0`, `run_if: ALL_SUCCESS` and
> `queue.enabled: true`.

## Reading the Spark UI — `ASSOC-S6-O3`

**The hierarchy.** Every action (`count`, `write`, `collect`) starts a **job**. A job
is split into **stages** at every shuffle, because a shuffle needs all of the previous
stage's output before the next can start. A stage runs one **task** per partition. So:
the Jobs page tells you which action was slow; the Stages page tells you which
shuffle boundary; the stage's task table tells you whether one task or all of them.

**Summary Metrics** on a stage page give five columns for each task metric — Min,
25th percentile, Median, 75th percentile, Max — for Duration, GC time, Shuffle Read
Size / Records, Shuffle spill (memory), Shuffle spill (disk) and Peak execution memory.
Reading one row across is the whole diagnosis.

**Reading one stage page — three fingerprints:**

```text
1. SKEW                       Min    25th   Median  75th   Max
   Duration                   2 s    3 s    3 s     4 s    11 min    <- Max far above 75th
   Shuffle Read Size          40 MB  45 MB  48 MB   50 MB  9.8 GB    <- one key, one task
   => one task holds most of the data; the stage waits for it.
      Rule of thumb: Max at least 1.5x the 75th percentile.

2. SPILL                      Min    25th   Median  75th   Max
   Duration                   3 min  3 min  4 min   4 min  5 min     <- even, but all slow
   Shuffle spill (disk)       1.1 GB 1.2 GB 1.2 GB  1.3 GB 1.4 GB    <- present at all
   => every task's working set exceeds its memory; correct but slow.
      Spill only appears on the stage page when there is some.

3. OVER-PARTITIONED           Tasks: 20,000
   Duration                   40 ms  60 ms  80 ms   90 ms  150 ms    <- all sub-second
   Shuffle Read Size          8 KB   10 KB  12 KB   13 KB  20 KB
   => scheduling overhead dominates; fewer, larger partitions.
```

| Symptom in the UI | Means |
|---|---|
| One task far slower than the rest; Max shuffle read far above the 75th percentile | **data skew** — one key holds disproportionate data |
| "Shuffle spill (disk)" on a stage | working set exceeded memory; correct but slow |
| Thousands of sub-second tasks | over-partitioned; per-task overhead dominates |
| Long shuffle read/write times | too much data moving between stages |

**Skew** is the classic. Adaptive Query Execution with skew join handling splits
oversized partitions at runtime, which fixes the cause with no code change — try that
before hand-salting keys. AQE splits skewed partitions in sort-merge and shuffle-hash
joins, not in broadcast joins, and only counts a partition as skewed when it is more
than 5x the median *and* above 256 MB.

**Spill** is Spark surviving rather than failing: it writes to disk instead of raising
OOM. The result is right and slow. Causes are partitions that are too large or a skewed
key; fixes are more partitions (`spark.sql.shuffle.partitions = auto`), less data per
task, or addressing the skew.

**`Exchange` is a shuffle.** In a plan, every `Exchange` node is a stage boundary and
data moving across the network. `BroadcastExchange` sends a small table to every
executor instead of shuffling the large one. On Photon the same node is printed as
`PhotonShuffleExchangeSink` / `PhotonShuffleExchangeSource`.

**`repartition` vs `coalesce`:**

| | `repartition(n)` / `repartition(col)` | `coalesce(n)` |
|---|---|---|
| Shuffle | yes — adds an `Exchange` | no — merges partitions in place |
| Direction | up or down | down only |
| Result | evenly sized (round-robin, or hash by column) | can be uneven; fewer, possibly larger tasks |
| Use it for | spreading skewed or too-few partitions; partitioning by a key before a write | cutting the number of output files cheaply |

```python
df.explain()                       # look for Exchange (shuffle) and BroadcastExchange
df.repartition(8).explain()        # Exchange RoundRobinPartitioning(8)
df.repartition("k").explain()      # Exchange hashpartitioning(k, 200)
df.coalesce(2).explain()           # Coalesce 2, no Exchange

spark.conf.set("spark.sql.shuffle.partitions", "auto")   # default 200
```

```sql
EXPLAIN SELECT /*+ REPARTITION(8, a) */ * FROM t;   -- hashpartitioning(a, 8)
EXPLAIN SELECT /*+ COALESCE(2) */ * FROM t;         -- Coalesce 2, no shuffle
-- REBALANCE evens out output files on a write; needs AQE
INSERT INTO target SELECT /*+ REBALANCE */ * FROM source;
```

> **Measured on Free Edition:** there is no Spark UI here; everything runs on serverless.
> A serverless job task's run record has no cluster or Spark context to link to, and
> `spark.sparkContext` raises `JVM_ATTRIBUTE_NOT_SUPPORTED` (`df.rdd` is not implemented
> either). What you get instead is the **query profile** ("See performance" under a cell,
> or Query History), and the query history API returns per-query totals: task counts
> (planned, completed, failed), `task_total_time_ms`, `spill_to_disk_bytes`, bytes and
> rows read. It does not break those down by stage, or give Summary Metrics quartiles or
> per-task shuffle read. So a skewed join can be run on Free Edition and seen in the data
> and the plan, but the Max vs 75th-percentile fingerprint cannot. The stage page is
> classic-compute only. On serverless, `spark.sql.shuffle.partitions` reads `auto` (and
> can be set); the AQE, broadcast and `maxResultSize` settings are not readable
> (`CONFIG_NOT_AVAILABLE`). `spark.sql.files.maxPartitionBytes` reads 128 MB. Plans print
> `PhotonShuffleExchangeSink RoundRobinPartitioning(8)` for `repartition(8)`,
> `hashpartitioning(k, 64)` for `repartition("k")` after setting 64 partitions, and a bare
> `Coalesce 2` (no exchange; Photon falls back for that node) for `coalesce(2)`.

### Watching for spill and shuffle on a schedule

The Spark UI shows one run after the fact. To catch spill and heavy shuffles as
they happen, query `system.query.history` (SQL warehouses, serverless notebooks
and jobs) on a schedule. Two columns carry the signal: `spilled_local_bytes`
(bytes written to local disk while the statement ran) and `shuffle_read_bytes`
(bytes sent over the network between stages).

```sql
-- the statements that spilled most this week
SELECT statement_id, executed_by, compute.type AS compute_type,
       total_duration_ms, spilled_local_bytes,
       query_source.job_info.job_id AS job_id,
       left(statement_text, 80) AS statement
FROM system.query.history
WHERE start_time >= current_timestamp() - INTERVAL 7 DAYS
  AND execution_status = 'FINISHED'
  AND spilled_local_bytes > 0
ORDER BY spilled_local_bytes DESC LIMIT 20;

-- shuffle-heavy: moved over 1 GB, and more than 3x what it read
SELECT statement_id, executed_by, total_duration_ms, read_bytes,
       shuffle_read_bytes,
       round(shuffle_read_bytes / nullif(read_bytes, 0), 1) AS shuffle_to_read,
       left(statement_text, 80) AS statement
FROM system.query.history
WHERE start_time >= current_timestamp() - INTERVAL 7 DAYS
  AND execution_status = 'FINISHED'
  AND shuffle_read_bytes > 1024 * 1024 * 1024
  AND shuffle_read_bytes > 3 * read_bytes
ORDER BY shuffle_read_bytes DESC LIMIT 20;
```

A query that shuffles several times what it reads is usually joining or
aggregating on a key it could have broadcast, filtered earlier or clustered on.
The query history API gives the same per-query totals under other names:

```bash
# spill_to_disk_bytes and network_sent_bytes, worst spill first
databricks api get "/api/2.0/sql/history/queries?include_metrics=true&max_results=100" \
  | jq -r '.res[] | [.query_id, .metrics.spill_to_disk_bytes,
                    .metrics.network_sent_bytes, .metrics.task_total_time_ms] | @tsv' \
  | sort -t$'\t' -k2,2nr | head
# or: databricks query-history list --include-metrics --max-results 100 -o json
```

**No system table records skew.** Skew is a property of the tasks inside a stage
(one task's input far larger than the rest), and no system table or query
history row holds per-task data: they hold one total per statement. A skewed
query and an evenly spread one with the same totals look identical there. To see
skew, open the stage's Summary Metrics in the Spark UI (Max far above the 75th
percentile) or the query profile.

> **Measured on Free Edition:** both queries above run on the Serverless Starter
> Warehouse and return no rows. Across all ~8,730 statements in
> `system.query.history` since 2026-08, `spilled_local_bytes` and
> `shuffle_read_bytes` are 0 on every row. Two deliberately skewed probes on the
> 2X-Small warehouse (a 60M-row GROUP BY on a skewed key; a window sort with 30M
> rows in one partition, 19.7 s of task time) also reported
> `spill_to_disk_bytes` 0 and `network_sent_bytes` 0 through the API. If your
> queries return nothing here, they are not wrong: this workspace does not report
> spill or shuffle bytes. Where they are reported, the same queries are the
> start of a spill and shuffle alert.

## Layout optimization — `ASSOC-S6-O4`

**Liquid clustering** is now preferred over partitioning for most tables. A partition
column is a decision you are stuck with — changing it means rewriting the table — and
choosing badly gives you either huge skewed partitions or millions of tiny files.
Clustering keys can be changed with `ALTER TABLE`, and the layout adapts incrementally.

| | Partitioning | Z-order | Liquid clustering |
|---|---|---|---|
| Declared with | `PARTITIONED BY (col)` at create | `OPTIMIZE t ZORDER BY (col)` each time | `CLUSTER BY (col, ...)` at create or `ALTER` |
| Columns suit | low, known cardinality (date, region) | high cardinality | either, up to 4 keys |
| Changing it | rewrite the table | pick new columns next `OPTIMIZE` | `ALTER TABLE ... CLUSTER BY`, no rewrite |
| Incremental | — | no; not idempotent, rewrites a lot | yes; `OPTIMIZE` only touches what needs it |
| Combine with | Z-order on *other* columns | partitioning | nothing: no partitioning, no Z-order |
| When | tables over 1 TB with ≥ 1 GB per partition | legacy tables | Databricks' default for all new tables |

```sql
CREATE TABLE events (id BIGINT, customer_id INT, event_date DATE)
  CLUSTER BY (customer_id, event_date);         -- up to 4 keys; need statistics
CREATE TABLE e2 CLUSTER BY (k) AS SELECT ...;   -- CTAS works too

ALTER TABLE events CLUSTER BY (event_date);     -- change keys; old data not rewritten
ALTER TABLE events CLUSTER BY AUTO;             -- managed tables: predictive optimization picks keys
ALTER TABLE events CLUSTER BY NONE;             -- stop clustering; nothing rewritten

OPTIMIZE events;                                -- incremental: clusters what isn't yet
OPTIMIZE events FULL;                           -- recluster everything, after changing keys

-- Convert a partitioned table in place
ALTER TABLE legacy REPLACE PARTITIONED BY WITH CLUSTER BY (b);

-- Z-order, for tables that are not clustered
OPTIMIZE legacy_unclustered ZORDER BY (customer_id);
```

Writes cluster on the way in only above a size threshold (64 MB for a one-key UC
managed table, rising with more keys), so small appends wait for the next `OPTIMIZE`.

**Predictive optimization** runs maintenance — `OPTIMIZE`, `VACUUM` and `ANALYZE`
(statistics collection) — automatically, and only on Unity Catalog *managed* tables,
because the catalog owns their layout; external tables are yours to maintain. It runs
on serverless jobs compute, never applies Z-order, and is on by default for accounts
created since November 2024. You switch it at catalog, schema or table level, and lower
levels inherit:

```sql
ALTER CATALOG main  ENABLE PREDICTIVE OPTIMIZATION;   -- or DISABLE | INHERIT
ALTER SCHEMA  main.s DISABLE PREDICTIVE OPTIMIZATION;
SELECT * FROM system.storage.predictive_optimization_operations_history;
```

**`VACUUM`** deletes data files no longer referenced by the table and older than the
retention window; once they are gone, time travel to the versions that used them fails.

```sql
VACUUM events DRY RUN;                 -- list (up to 1,000) files it would delete
VACUUM events;                         -- default RETAIN 168 HOURS (7 days)
VACUUM events RETAIN 240 HOURS;        -- keep more history
VACUUM events LITE;                    -- use the log instead of listing storage; default is FULL
ALTER TABLE events SET TBLPROPERTIES ('delta.deletedFileRetentionDuration' = 'interval 14 days');
```

**Deletion vectors** mark rows as deleted rather than rewriting files, making deletes
and updates much cheaper; the files are cleaned up later during maintenance
(`OPTIMIZE`, or `REORG TABLE ... APPLY (PURGE)`, then `VACUUM`).

> **Measured on Free Edition:** a fifth clustering key fails with
> `DELTA_CLUSTER_BY_INVALID_NUM_COLUMNS`; `PARTITIONED BY` with `CLUSTER BY` fails with
> `SPECIFY_CLUSTER_BY_WITH_PARTITIONED_BY_IS_NOT_ALLOWED`; `OPTIMIZE ... ZORDER BY` on a
> clustered table fails with `DELTA_CLUSTERING_WITH_ZORDER_BY`; Z-ordering a partition
> column fails with `DELTA_ZORDERING_ON_PARTITION_COLUMN`; a `MAP` column cannot be a key
> (`DELTA_CLUSTERING_COLUMNS_DATATYPE_NOT_SUPPORTED`). `ALTER TABLE ... CLUSTER BY` on a
> partitioned table is refused and names `REPLACE PARTITIONED BY WITH CLUSTER BY`, which
> then worked. `OPTIMIZE ... FULL`, `CLUSTER BY AUTO` (it sets `clusterByAuto = true`) and
> `CLUSTER BY NONE` all ran. New tables had `delta.enableDeletionVectors = true` without
> asking. `VACUUM ... RETAIN 0 HOURS` was refused with
> `DELTA_VACUUM_RETENTION_PERIOD_TOO_SHORT`, and the retention check cannot be turned off
> on serverless; yet `RETAIN 1 HOURS`, `24 HOURS` and `100 HOURS` were accepted. Do not
> learn that as a rule: the documented behaviour, and the exam's, is that anything under
> 168 hours trips the safety check unless
> `spark.databricks.delta.retentionDurationCheck.enabled` is false.

## Compute failures — `ASSOC-S6-O5`

| Failure | Usual cause | Where you see it |
|---|---|---|
| Cluster will not start | cloud quota, a bad init script, an unavailable instance type | the compute's **Event log** and the termination reason |
| Library conflict | two libraries pinning incompatible versions of a shared dependency | the **Libraries** tab shows a failed install; or `ImportError` / `AttributeError` at run time |
| Driver OOM | `collect()` or `toPandas()` on a large result; heavy pure-Python on the driver | "The spark driver has stopped unexpectedly and is restarting", "Driver is temporarily unavailable", `Driver_Not_Responding` in the event log |
| Result too large for the driver | an action returns more than the cap | "Total size of serialized results of N tasks ... is bigger than `spark.driver.maxResultSize`" |
| Executor OOM | partitions too large, or heavy skew | a stage failure naming `ExecutorLostFailure`, or `java.lang.OutOfMemoryError` in an executor's log |

**Driver OOM is not fixed by a bigger cluster.** `collect()` pulls every row into a
single JVM; more executors do not help. Write the result to a table instead.

**An OOM triage tree:**

```text
Out of memory
├── Message names the DRIVER ("driver has stopped", "maxResultSize", Driver_Not_Responding)
│   ├── code calls collect() / toPandas() / display of a huge result
│   │     -> don't bring it back: write to a table, or limit()/aggregate first
│   ├── pure-Python loop or UDF doing the work on the driver
│   │     -> rewrite in Spark so executors share it
│   └── many notebooks on one interactive cluster
│         -> separate job compute; only then a bigger driver node
└── Message names an EXECUTOR (ExecutorLostFailure, OOM in an executor log)
    ├── Summary Metrics: Max >> 75th percentile         -> skew: AQE skew join, salt, cluster
    ├── spill on every task, sizes even                  -> partitions too big: more partitions
    └── broadcast of a table that is not small           -> lower the broadcast threshold / hint
```

**Init scripts** run on every node as it starts; when a cluster-scoped script exits
non-zero the cluster fails to start, and its output is in the cluster log delivery
location under `init_scripts/`. Where they may live:

| Location | Standard access mode | Dedicated access mode |
|---|---|---|
| Unity Catalog volume (13.3 LTS+) | yes, once an admin adds it to the **allowlist** | yes |
| Workspace file | no | yes |
| Cloud object storage | yes (13.3 LTS+), allowlisted | yes |
| DBFS | end of life: clusters with DBFS init scripts do not start | same |

Global init scripts (admins only) run before cluster-scoped ones, on every cluster
in dedicated or no-isolation mode. Serverless supports neither.

**Libraries.** A notebook-scoped `%pip install` affects only that notebook's session
and wins over a compute-scoped library of the same name, which in turn wins over the
version in Databricks Runtime. That precedence is how one notebook hides a conflict
from the others — or causes one only in itself.

```python
%pip install pandas==2.2.3          # notebook-scoped; pin versions (serverless needs it)
dbutils.library.restartPython()     # %pip does not restart Python; do it to pick up upgrades
```

```bash
# Compute-scoped library and an init script from a volume (cluster JSON)
#   "libraries":    [{"pypi": {"package": "pandas==2.2.3"}}],
#   "init_scripts": [{"volumes": {"destination": "/Volumes/main/ops/scripts/setup.sh"}}]
databricks clusters events <CLUSTER_ID> -o json | jq -r '.[] | [.timestamp, .type] | @tsv'
databricks libraries cluster-status <CLUSTER_ID>
```

> **Measured on Free Edition:** On serverless compute there are no clusters to
> configure, so these particular failures cannot occur — and cannot be practised.
> This objective is theory on Free Edition. Serverless has no init scripts and no
> compute-scoped libraries; dependencies come from the notebook's environment or `%pip`.

## Further reading

Official documentation for what this section tests, one link per topic:

- [Monitor jobs](https://docs.databricks.com/aws/en/jobs/monitor) — run history, matrix view and duration trends.
- [Configure a job](https://docs.databricks.com/aws/en/jobs/configure-job) — duration warning, timeout, concurrency and queueing.
- [Diagnose cost and performance with the Spark UI](https://docs.databricks.com/aws/en/optimizations/spark-ui-guide/) — the guided walk from job to stage to task.
- [Skew and spill](https://docs.databricks.com/aws/en/optimizations/spark-ui-guide/long-spark-stage-page) — the two fingerprints and how to tell them apart.
- [Adaptive query execution](https://docs.databricks.com/aws/en/optimizations/aqe) — the defaults for shuffle partitions, broadcast and skew joins.
- [Query profile](https://docs.databricks.com/aws/en/sql/user/queries/query-profile) — what serverless gives you instead of the Spark UI.
- [Liquid clustering](https://docs.databricks.com/aws/en/delta/clustering) — `CLUSTER BY`, changing keys, `OPTIMIZE`.
- [When to partition tables](https://docs.databricks.com/aws/en/tables/partitions) — the 1 TB and 1 GB guidance.
- [Data skipping and Z-order](https://docs.databricks.com/aws/en/delta/data-skipping) — the 32-column statistics default and `ZORDER BY`.
- [OPTIMIZE and compaction](https://docs.databricks.com/aws/en/delta/optimize) — small files and the target size.
- [VACUUM](https://docs.databricks.com/aws/en/delta/vacuum) — the 7-day default and what it does to time travel.
- [Predictive optimization](https://docs.databricks.com/aws/en/optimizations/predictive-optimization) — managed tables only, and what it runs.
- [Deletion vectors](https://docs.databricks.com/aws/en/delta/deletion-vectors) — why deletes stopped rewriting files.
- [Compute configuration best practices](https://docs.databricks.com/aws/en/compute/cluster-config-best-practices) — the sizing and failure-mode advice.
- [Init scripts](https://docs.databricks.com/aws/en/init-scripts/) — where scripts may live per access mode, and the order they run.
- [Libraries](https://docs.databricks.com/aws/en/libraries/) — notebook-scoped vs cluster-scoped, and precedence.
- [Notebook-scoped Python libraries](https://docs.databricks.com/aws/en/libraries/notebooks-python-libraries) — `%pip` and `restartPython()`.
- [Serverless compute limitations](https://docs.databricks.com/aws/en/compute/serverless/limitations) — no Spark UI, no init scripts, no cluster libraries.

Videos for another angle on the hard parts (channel, length):

- [Understanding Spark UI in Depth: jobs, stages, tasks](https://www.youtube.com/watch?v=t-42lC167k4) — DataBeli, 19 min. Reading the UI the way the exam expects.
- [Databricks Liquid Clustering Introduction](https://www.youtube.com/watch?v=na3Wp-j855g) — Apostolos Athanasiou, 13 min. Clustering versus partitioning and Z-order, demonstrated.
