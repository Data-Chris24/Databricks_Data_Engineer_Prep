# Cost and Performance Optimization — 13%

The second-heaviest Professional section. Most optimisation questions are really
"which of these is happening?", and the answer comes from `DESCRIBE DETAIL` and
the query profile rather than intuition. Learn the symptoms, the source that
shows each one, and the fix that matches.

> **Names:** Lakeflow Jobs (Workflows), Lakeflow Spark Declarative Pipelines
> (Delta Live Tables, DLT), disk cache (Delta cache, DBIO cache), SQL warehouse
> (SQL endpoint), liquid clustering (replaces partitioning and `ZORDER` for new
> tables), automatic liquid clustering (`CLUSTER BY AUTO`).

## What the exam asks

- A small dimension is shuffled on both sides of a join — broadcast it with a hint or a higher threshold (`PRO-S6-O5`)
- Deletes are cheap but the deleted rows must leave storage for a compliance request — deletion vectors, then `REORG ... APPLY (PURGE)` and `VACUUM` (`PRO-S6-O2`)
- A filter on a column outside the first 32 reads every file — statistics columns and data skipping (`PRO-S6-O3`)
- Nobody schedules `OPTIMIZE` or `VACUUM` and storage keeps growing — managed tables with predictive optimization (`PRO-S6-O1`)
- A downstream table must pick up updates and deletes without a full rescan — change data feed and `MERGE` (`PRO-S6-O4`)
- A stage spills to disk at 200 shuffle partitions — partition sizing, AQE and `spark.sql.shuffle.partitions` (`PRO-S6-O5`)

## Defaults and limits

| Setting | Default or limit | Note |
|---|---|---|
| `spark.sql.autoBroadcastJoinThreshold` | 10 MB | static planning; `-1` disables broadcast |
| `spark.databricks.adaptive.autoBroadcastJoinThreshold` | 30 MB | AQE can switch to broadcast at runtime up to this size |
| `spark.sql.shuffle.partitions` | 200 | `auto` turns on auto-optimized shuffle |
| `spark.sql.adaptive.advisoryPartitionSizeInBytes` | 64 MB | target size when AQE coalesces partitions |
| AQE skew join | 5 × median and over 256 MB | a partition must exceed both to be split |
| Adaptive query execution | on | `spark.databricks.optimizer.adaptive.enabled` |
| Dynamic file pruning | on; large side ≥ 10 GB and ≥ 10 files | `spark.databricks.optimizer.dynamicFilePruning` |
| Columns with file statistics | first 32 | `delta.dataSkippingNumIndexedCols`; `delta.dataSkippingStatsColumns` overrides it |
| Liquid clustering keys | up to 4 | keys need statistics; not combinable with partitioning or `ZORDER` |
| `delta.targetFileSize` | none (autotuned) | autotune: 256 MB under 2.56 TB, rising to 1 GB above 10 TB |
| `delta.autoOptimize.autoCompact` | off unless set | `true` = 128 MB target; `auto` (recommended) tunes it |
| `delta.deletedFileRetentionDuration` | 7 days | what `VACUUM` keeps; `RETAIN` below it is refused |
| `delta.logRetentionDuration` | 30 days | table history; time travel needs both log and files |
| `UNDROP TABLE` window | 7 days | managed tables only |
| Predictive optimization | on for accounts created from 11 Nov 2024 | managed tables only; runs `OPTIMIZE`, `VACUUM`, `ANALYZE` |

## Why managed tables cost less to run — `PRO-S6-O1`

When Unity Catalog owns a table's layout it can maintain it: **predictive
optimization** runs `OPTIMIZE` (compaction and clustering), `VACUUM` and
`ANALYZE` (statistics) automatically, based on how the table is used, on serverless
jobs compute billed under a serverless jobs SKU. On an external table that work is
yours to schedule, and the usual failure is that nobody does until a query gets
slow or storage bills climb from files nobody references. Some features are
managed-only: predictive optimization, `CLUSTER BY AUTO` and `UNDROP TABLE`
(liquid clustering and deletion vectors work on external Delta tables too). And
the lifecycle follows the catalog: drop a managed table and the files go.

```sql
-- Managed: no LOCATION clause, Unity Catalog owns files and layout
CREATE TABLE main.sales.orders (order_id BIGINT, region STRING, amount DOUBLE)
  CLUSTER BY AUTO;                                -- keys chosen by predictive optimization

-- Set at catalog, schema or table level: ENABLE | DISABLE | INHERIT
ALTER SCHEMA main.sales ENABLE PREDICTIVE OPTIMIZATION;
DESCRIBE SCHEMA EXTENDED main.sales;              -- row "Predictive Optimization"

-- What it ran, and when
SELECT operation_type, operation_status, start_time
FROM system.storage.predictive_optimization_operations_history
WHERE table_name = 'orders';

UNDROP TABLE main.sales.orders;                   -- managed only, within 7 days
```

> **Measured on Free Edition:** `DESCRIBE SCHEMA EXTENDED workspace.de_prep`
> reports `ENABLE (inherited from METASTORE ...)`, so every managed table there is
> maintained without asking. `ALTER TABLE ... CLUSTER BY AUTO` on a table already
> clustered by `region` set `clusterByAuto` to `true` in `DESCRIBE DETAIL` and kept
> `region` as the current key until predictive optimization picks its own.

## Delta's optimisation features — `PRO-S6-O2`

- **Liquid clustering** replaces partitioning and `ZORDER` for layout: keys can
  be changed later with `ALTER TABLE ... CLUSTER BY`, the layout adapts
  incrementally, and there is no partition explosion. Choose keys that are
  **filtered on often**; up to four, each with statistics collected. A key that
  queries never filter on (a surrogate id nobody looks up) costs a rewrite and
  buys nothing. `OPTIMIZE` clusters incrementally; `OPTIMIZE ... FULL` reclusters
  everything, which you need after changing keys.
- **Deletion vectors** mark rows as deleted rather than rewriting files, making
  `DELETE`, `UPDATE` and `MERGE` much cheaper; reads apply the marks at query
  time. They are a **table feature** (`delta.enableDeletionVectors`): enabling them
  upgrades the table protocol, so a client without support can no longer read it,
  and `ALTER TABLE ... DROP FEATURE deletionVectors` is how you go back.
- **`OPTIMIZE`** compacts small files; **`VACUUM`** removes files no longer
  referenced by retained history.
- **Write-side file sizing** stops small files appearing in the first place.
  **Optimized writes** shuffle data before writing so each partition gets fewer,
  larger files; they are on by default for `MERGE` and for `UPDATE` / `DELETE`
  with subqueries, and for `CTAS` and `INSERT` on SQL warehouses. **Auto
  compaction** runs a small `OPTIMIZE` after a write when enough small files have
  built up. `delta.targetFileSize` pins the size both aim for; leave it unset and
  Databricks autotunes by table size.

```sql
ALTER TABLE main.sales.orders SET TBLPROPERTIES (
  'delta.targetFileSize'               = '128mb',   -- default: none, autotuned
  'delta.autoOptimize.optimizeWrite'   = 'true',
  'delta.autoOptimize.autoCompact'     = 'auto',    -- true | legacy | auto | false
  'delta.enableDeletionVectors'        = 'true',
  'delta.deletedFileRetentionDuration' = 'interval 7 days',    -- default
  'delta.logRetentionDuration'         = 'interval 30 days'    -- default
);

ALTER TABLE main.sales.orders CLUSTER BY (region, order_date);  -- max 4 keys
OPTIMIZE main.sales.orders FULL;        -- recluster existing data to the new keys
-- OPTIMIZE ... ZORDER BY on a clustered table is an error
```

### The deletion vector lifecycle

Three steps, and each one changes something different on disk:

| Step | What it writes | Rows still in storage? |
|---|---|---|
| `DELETE FROM t WHERE ...` | a deletion vector file beside the untouched data file | yes, in the **current** version's file |
| `REORG TABLE t APPLY (PURGE)` | a rewritten data file without the marked rows | yes, in the old file, now unreferenced |
| `VACUUM t` (after the retention window) | removes unreferenced files | no |

`OPTIMIZE` and auto compaction also rewrite files that carry deletion vectors, but
compaction skips files that do not qualify, so only `REORG ... APPLY (PURGE)`
guarantees every mark is applied. The trap is running `VACUUM` straight after the
`DELETE`: the file holding the deleted row is still part of the current version,
so `VACUUM` can never remove it.

![Deletion vectors, REORG PURGE, OPTIMIZE and VACUUM, commit by commit](visual:delta-commit-log?h=900)

```sql
DELETE FROM main.sales.orders WHERE customer_id = 42;
REORG TABLE main.sales.orders APPLY (PURGE);   -- WHERE allowed on partition columns only
VACUUM main.sales.orders;                      -- default retention: 7 days (168 hours)
VACUUM main.sales.orders DRY RUN;              -- list what would go, delete nothing
```

> **Measured on Free Edition:** a new table created on the SQL warehouse had
> `delta.enableDeletionVectors = true`, row tracking, v2 checkpoints and zstd
> compression without asking (`tableFeatures` included `deletionVectors`,
> `clustering`, `rowTracking`, `v2Checkpoint`; reader version 3, writer 7).
> Deleting 100 of 20,000 rows logged `numDeletionVectorsAdded: 1` and
> `numRemovedFiles: 0` in `DESCRIBE HISTORY`; `REORG ... APPLY (PURGE)` then logged
> one file removed, one added and `numDeletionVectorsRemoved: 1`. Errors seen:
> a fifth clustering key gives `DELTA_CLUSTER_BY_INVALID_NUM_COLUMNS`, a key
> outside `delta.dataSkippingStatsColumns` gives
> `DELTA_CLUSTERING_COLUMN_MISSING_STATS`, `ZORDER BY` on a clustered table gives
> `DELTA_CLUSTERING_WITH_ZORDER_BY`, and an invalid `autoCompact` value lists the
> four allowed ones.

## How queries stay fast on large tables — `PRO-S6-O3`

Delta records **min/max statistics, null counts and row counts per file** for the
**first 32 columns** of the schema. A filter can skip a file whose range excludes
the value, but only if the values are **clustered**: scatter every region across
every file and no file can be skipped. Data skipping therefore needs statistics
*and* locality, and clustering provides the locality. A filtered column beyond
the 32nd has no statistics and skips nothing until you widen the list; changing
the properties affects new writes only, so recompute for existing files.
File pruning is the same idea one level up: partition or cluster boundaries let
the planner ignore whole files without opening them. Column pruning comes from
the columnar format: a query pays only for the columns it references, which is
why `SELECT *` on a wide table is a cost problem, not a style problem.

**Dynamic file pruning** extends skipping to joins: the filter on the small side
(`WHERE d.is_core`) becomes, at runtime, a list of join-key values pushed into the
scan of the large Delta table, so files with none of those keys are never read.
It is on by default and triggers only when the large table is at least 10 GB and
10 files; in `MERGE`, `UPDATE` and `DELETE` it needs Photon.

**Disk cache vs `CACHE`.** The disk cache keeps copies of remote Parquet files on
worker local storage, automatically on first read, and drops them when the files
change. Spark's cache (`df.cache()`, `CACHE TABLE`) keeps a DataFrame in memory,
only when you ask, and until you `unpersist` it or it is evicted. The disk cache is
the one that helps repeated scans of the same table; on SQL warehouses it is
managed for you and `CACHE SELECT` is ignored.

Start every "why is this slow" with `DESCRIBE DETAIL`: `numFiles` and average file
size localise most problems before you open a query plan.

```sql
ALTER TABLE main.sales.events SET TBLPROPERTIES (
  'delta.dataSkippingNumIndexedCols' = '40'                -- default 32
);
ALTER TABLE main.sales.events SET TBLPROPERTIES (
  'delta.dataSkippingStatsColumns' = 'event_date,region'   -- overrides the count
);
ANALYZE TABLE main.sales.events COMPUTE DELTA STATISTICS;   -- recompute existing files

SET spark.databricks.optimizer.dynamicFilePruning = true;          -- default
SET spark.databricks.optimizer.deltaTableSizeThreshold = 10000000000;  -- 10 GB
SET spark.databricks.io.cache.enabled = true;                      -- disk cache, classic compute
```

> **Measured on Free Edition:** on the SQL warehouse, `SET` on
> `spark.databricks.io.cache.enabled` returns `CONFIG_NOT_AVAILABLE` and
> `CACHE TABLE` returns `NOT_SUPPORTED_WITH_DB_SQL`. `EXPLAIN` of a join to a
> four-row dimension on a one-file table showed no dynamic pruning filter, as
> expected below the 10 GB and 10-file thresholds. The pruning thresholds above
> are from the documentation only.

## Change Data Feed — `PRO-S6-O4`

`delta.enableChangeDataFeed` makes a table record its row-level changes
(`_change_type` of insert, update_preimage, update_postimage, delete, plus
`_commit_version` and `_commit_timestamp`) so a consumer can read *what changed*
since a version instead of rescanning. It addresses the case a streaming table
cannot handle: **updates and deletes to rows already consumed.** A downstream
`MERGE` driven by the change feed stays current with far less work and lower
latency than a periodic full refresh, and `table_changes('t', start_version)` is
how you read it in SQL.

Change data is recorded only from the version that enabled it, and it is not a
permanent archive: it is readable only while that table version is retained, so
`VACUUM` and log retention bound how far back a consumer can restart. A stream
reading the feed from a fresh checkpoint first returns the current snapshot as
inserts, then the changes. Non-additive schema changes (rename, drop, type change)
block reads across the version where they happen.

```sql
ALTER TABLE main.sales.orders SET TBLPROPERTIES (delta.enableChangeDataFeed = true);

SELECT * FROM table_changes('main.sales.orders', 5);       -- version 5 to latest
SELECT * FROM table_changes('main.sales.orders', 5, 9);    -- inclusive range
SELECT * FROM table_changes('main.sales.orders', '2026-10-01 00:00:00');  -- timestamps too
```

```python
(spark.readStream
    .option("readChangeFeed", "true")          # required
    .option("startingVersion", 5)              # or startingTimestamp; endingVersion for batch
    .table("main.sales.orders"))
```

> **Measured on Free Edition:** on a table with deletion vectors, a `DELETE` with
> change data feed on logged `numAddedChangeFiles: 0`, yet `table_changes` still
> returned the 100 `delete` rows (derived from the log); an `UPDATE` logged one
> change file and returned one `update_preimage` and one `update_postimage`.
> Reading from version 0, before the feed was enabled, failed with
> `DELTA_MISSING_CHANGE_DATA`.

## Reading a query profile — `PRO-S6-O5`

The numbers worth finding first, in order:

| Metric | Means |
|---|---|
| **Files pruned vs read** | whether data skipping worked at all |
| **Bytes read** vs bytes returned | whether you read columns you discard |
| **Spill** | the working set exceeded memory |
| **Shuffle bytes** | how much data moved between stages |
| **Join type** | broadcast (cheap) vs sort-merge with a shuffle on both sides |

A query that reads every file for a filtered column has a **layout** problem. A
query that reads far more bytes than it returns has a **projection** problem. A
join that shuffles a small dimension has a **broadcast** problem
(`spark.sql.autoBroadcastJoinThreshold`, default 10 MB, or an explicit
`broadcast()`). One task far slower than its siblings is **skew**, which adaptive
query execution can split at runtime.

| Symptom | Usual cause | Fix |
|---|---|---|
| Reads every file for a filter | no clustering on the filtered column | cluster on it |
| Thousands of tiny files | frequent small appends | `OPTIMIZE`, or predictive optimization |
| Reads far more bytes than returned | `SELECT *` on a wide table | project only what you need |
| Big shuffle on a join | small side not broadcast | broadcast it |
| Spill to disk | too few shuffle partitions for the data | more partitions, or `auto` |
| One task much slower than the rest | skewed join key | AQE skew join, or salt the key |
| Idle compute | always-on cluster for periodic work | job compute, or serverless |

A table can suffer several of these at once, and clustering fixes exactly one of
them. That is the point of this section's assignment.

### Anatomy of a slow query

Open it from **Query History** (or **See performance** under a notebook cell),
then **See query profile**. Read it top to bottom:

1. **Summary.** Wall-clock duration against aggregated task time: task time many
   times the wall-clock means the work ran in parallel; the two close together on
   a big query means a few tasks did most of it. The IO
   figures give bytes read, the share read from cache and the percentage of files
   pruned.
2. **Top operators.** The longest-running operators, sorted. Most slow queries
   have one operator taking most of the time; start there.
3. **The scan.** Files read against files pruned, rows read. Everything read for a
   selective filter means a layout or statistics problem (O3).
4. **The exchange.** Shuffle bytes written and read. A large exchange feeding a
   join of a small table means the broadcast did not happen.
5. **The join.** Broadcast hash join (one side shipped to every task) or sort-merge
   join (both sides shuffled and sorted). Per-task times far apart mean skew.
6. **Spill.** Any bytes spilled to disk on a sort, aggregate or join means its
   partitions are too big for memory.

Switch the graph's metric to **Time spent** to see the slow operator, and turn on
verbose mode when an operator you expect is hidden.

### Shuffle partitions and spill at two sizes

`spark.sql.shuffle.partitions` sets how many partitions a shuffle produces. AQE
can **coalesce** small partitions after the shuffle (towards 64 MB each) and
**split** skewed ones, but it does not raise the count when every partition is too
big.

| Shuffle size | At 200 partitions | What happens | Fix |
|---|---|---|---|
| 2 GB | about 10 MB each | 200 tiny tasks, scheduling overhead | AQE coalesces to about 32 partitions of 64 MB; nothing to do |
| 200 GB | about 1 GB each | each task's working set exceeds its memory, so it **spills** to disk | about 3,200 partitions (200 GB ÷ 64 MB), or `auto` |

```python
spark.conf.set("spark.sql.shuffle.partitions", "auto")      # default 200
spark.conf.set("spark.sql.adaptive.coalescePartitions.enabled", "true")      # default
spark.conf.set("spark.sql.adaptive.advisoryPartitionSizeInBytes", "64m")     # default
spark.conf.set("spark.sql.adaptive.skewJoin.skewedPartitionFactor", "5")     # default
spark.conf.set("spark.sql.autoBroadcastJoinThreshold", "10m")  # default; -1 disables

from pyspark.sql.functions import broadcast
facts.join(broadcast(dims), "region")
```

```sql
SELECT /*+ BROADCAST(d) */ f.region, sum(f.amount)
FROM main.sales.orders f JOIN main.sales.regions d ON f.region = d.region
GROUP BY f.region;
-- other join hints: SHUFFLE_MERGE, SHUFFLE_HASH, SHUFFLE_REPLICATE_NL
```

> **Measured on Free Edition:** the SQL warehouse refuses `SET` on
> `spark.sql.shuffle.partitions`, `spark.sql.adaptive.enabled` and
> `spark.sql.autoBroadcastJoinThreshold` with `CONFIG_NOT_AVAILABLE`, and its plans
> showed `hashpartitioning(..., 16)`, not 200. In a serverless notebook
> `spark.sql.shuffle.partitions` reads `auto` and can be set, while the AQE and
> broadcast thresholds are not available. `EXPLAIN` on the warehouse showed
> `AdaptiveSparkPlan` (AQE on), a `PhotonBroadcastHashJoin` for a four-row
> dimension, and a `SortMergeJoin` with a hash-partitioned exchange on both sides
> once `/*+ SHUFFLE_MERGE(d) */` forced it. The numeric defaults above are from
> the documentation.

### Where compute cost goes

**Job compute** starts for a run and terminates when its last task finishes, and is
billed at a lower DBU rate than **all-purpose compute**, which is meant for
interactive work and keeps billing while idle until auto termination. Databricks
does not recommend all-purpose compute for production jobs, and serverless compute
for jobs is the default for tasks that support it. A scheduled job on an
always-on all-purpose cluster pays twice: a higher rate and the idle hours.

```yaml
# Lakeflow Jobs task on job compute rather than an existing all-purpose cluster
tasks:
  - task_key: nightly
    job_cluster_key: nightly_cluster     # not existing_cluster_id
job_clusters:
  - job_cluster_key: nightly_cluster
    new_cluster: { spark_version: 16.4.x-scala2.12, num_workers: 2 }
```

## Further reading

Official documentation for what this section tests, one link per topic:

- [Managed tables](https://docs.databricks.com/aws/en/tables/managed) — what predictive optimization needs.
- [Liquid clustering](https://docs.databricks.com/aws/en/delta/clustering) — keys, `OPTIMIZE`, `CLUSTER BY AUTO`.
- [OPTIMIZE](https://docs.databricks.com/aws/en/delta/optimize) — compaction and target file size.
- [VACUUM](https://docs.databricks.com/aws/en/delta/vacuum) — retention and the deletion-vector trap.
- [Table history and retention](https://docs.databricks.com/aws/en/delta/history) — `logRetentionDuration` and `deletedFileRetentionDuration`.
- [Data skipping](https://docs.databricks.com/aws/en/delta/data-skipping) — file statistics and the 32-column default.
- [ANALYZE TABLE](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-aux-analyze-table) — `COMPUTE DELTA STATISTICS`.
- [Deletion vectors](https://docs.databricks.com/aws/en/delta/deletion-vectors) — soft deletes and `REORG ... APPLY (PURGE)`.
- [REORG TABLE](https://docs.databricks.com/aws/en/sql/language-manual/delta-reorg-table) — `APPLY (PURGE)` syntax and its `WHERE` limit.
- [Drop a Delta table feature](https://docs.databricks.com/aws/en/delta/drop-feature) — going back from deletion vectors.
- [Predictive optimization](https://docs.databricks.com/aws/en/optimizations/predictive-optimization) — what runs, on which tables.
- [Change data feed](https://docs.databricks.com/aws/en/delta/delta-change-data-feed) — `readChangeFeed`, `_change_type`, retention.
- [Tune file size](https://docs.databricks.com/aws/en/delta/tune-file-size) — optimized writes and auto compaction.
- [Dynamic file pruning](https://docs.databricks.com/aws/en/optimizations/dynamic-file-pruning) — the thresholds and the Photon requirement.
- [Adaptive query execution](https://docs.databricks.com/aws/en/optimizations/aqe) — coalescing, skew join, runtime broadcast.
- [Disk cache](https://docs.databricks.com/aws/en/optimizations/disk-cache) — how it differs from Spark's cache.
- [Query profile](https://docs.databricks.com/aws/en/sql/user/queries/query-profile) — reading the plan and its metrics.
- [Compute for jobs](https://docs.databricks.com/aws/en/jobs/compute) — job compute, all-purpose compute and serverless.
- [Optimization recommendations](https://docs.databricks.com/aws/en/optimizations/) — the overview page.
- [Photon](https://docs.databricks.com/aws/en/compute/photon) — what it accelerates and what falls out of it.

Videos for another angle on the hard parts (channel, length):

- [Delta tables: deletion vectors and liquid clustering](https://www.youtube.com/watch?v=qovye-vdn8I) — Ease With Data, 13 min. Both features side by side.
- [Deletion Vectors on Delta Lake tables: introduction](https://www.youtube.com/watch?v=fTj2iXTrp5Q) — Apostolos Athanasiou, 17 min. What a soft delete leaves on disk.
- [Understanding Spark UI in Depth: jobs, stages, tasks](https://www.youtube.com/watch?v=t-42lC167k4) — DataBeli, 19 min. The UI behind the query profile.
