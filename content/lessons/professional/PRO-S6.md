# Cost and Performance Optimization — 13%

The second-heaviest Professional section. Most optimisation questions are really
"which of these is happening?", and the answer comes from `DESCRIBE DETAIL` and
the query profile rather than intuition. Learn the symptoms, the source that
shows each one, and the fix that matches.

## Why managed tables cost less to run — `PRO-S6-O1`

When Unity Catalog owns a table's layout it can maintain it: **predictive
optimization** runs `OPTIMIZE` (compaction and clustering) and `VACUUM`
automatically, based on how the table is used. On an external table that work is
yours to schedule, and the usual failure is that nobody does until a query gets
slow or storage bills climb from files nobody references. Some features are
managed-only: predictive optimization, `CLUSTER BY AUTO` and `UNDROP TABLE`
(liquid clustering and deletion vectors work on external Delta tables too). And
the lifecycle follows the catalog: drop a managed table and the files go.

## Delta's optimisation features — `PRO-S6-O2`

- **Liquid clustering** replaces partitioning and `ZORDER` for layout: keys can
  be changed later with `ALTER TABLE ... CLUSTER BY`, the layout adapts
  incrementally, and there is no partition explosion. Choose keys that are
  **filtered on often and have low-to-moderate cardinality**. Clustering on a
  near-unique column (an id) costs a rewrite and buys nothing: every file holds
  a distinct range, so no file can be skipped.
- **Deletion vectors** mark rows as deleted rather than rewriting files, making
  deletes and updates much cheaper; the marked rows are cleaned up later during
  maintenance (`REORG TABLE ... APPLY (PURGE)` forces it).
- **`OPTIMIZE`** compacts small files; **`VACUUM`** removes files no longer
  referenced by retained history.

## How queries stay fast on large tables — `PRO-S6-O3`

Delta records **min/max statistics per column per file**. A filter can skip a
file whose range excludes the value, but only if the values are **clustered**:
scatter every region across every file and no file can be skipped. Data skipping
therefore needs statistics *and* locality, and clustering provides the locality.
File pruning is the same idea one level up: partition or cluster boundaries let
the planner ignore whole files without opening them. Column pruning comes from
the columnar format: a query pays only for the columns it references, which is
why `SELECT *` on a wide table is a cost problem, not a style problem.

Start every "why is this slow" with `DESCRIBE DETAIL`: `numFiles` and average file
size localise most problems before you open a query plan.

## Change Data Feed — `PRO-S6-O4`

`delta.enableChangeDataFeed` makes a table record its row-level changes
(`_change_type` of insert, update_preimage, update_postimage, delete) so a
consumer can read *what changed* since a version instead of rescanning. It
addresses the case a streaming table cannot handle: **updates and deletes to
rows already consumed.** A downstream `MERGE` driven by the change feed stays
current with far less work and lower latency than a periodic full refresh, and
`table_changes('t', start_version)` is how you read it in SQL.

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
| Idle compute | always-on cluster for periodic work | job compute, or serverless |

A table can suffer several of these at once, and clustering fixes exactly one of
them. That is the point of this section's assignment.

## Further reading

Official documentation for what this section tests, one link per topic:

- [Managed tables](https://docs.databricks.com/aws/en/tables/managed) — what predictive optimization needs.
- [Liquid clustering](https://docs.databricks.com/aws/en/delta/clustering) — keys, `OPTIMIZE`, `CLUSTER BY AUTO`.
- [OPTIMIZE](https://docs.databricks.com/aws/en/delta/optimize) — compaction and target file size.
- [VACUUM](https://docs.databricks.com/aws/en/delta/vacuum) — retention and the deletion-vector trap.
- [Data skipping](https://docs.databricks.com/aws/en/delta/data-skipping) — file statistics and the 32-column default.
- [Deletion vectors](https://docs.databricks.com/aws/en/delta/deletion-vectors) — soft deletes and `REORG ... APPLY (PURGE)`.
- [Predictive optimization](https://docs.databricks.com/aws/en/optimizations/predictive-optimization) — what runs, on which tables.
- [Change data feed](https://docs.databricks.com/aws/en/delta/delta-change-data-feed) — `readChangeFeed`, `_change_type`, retention.
- [Tune file size](https://docs.databricks.com/aws/en/delta/tune-file-size) — optimized writes and auto compaction.
- [Query profile](https://docs.databricks.com/aws/en/sql/user/queries/query-profile) — reading the plan and its metrics.
- [Optimization recommendations](https://docs.databricks.com/aws/en/optimizations/) — the overview page.
- [Photon](https://docs.databricks.com/aws/en/compute/photon) — what it accelerates and what falls out of it.

Videos for another angle on the hard parts (channel, length):

- [Delta tables: deletion vectors and liquid clustering](https://www.youtube.com/watch?v=qovye-vdn8I) — Ease With Data, 13 min. Both features side by side.
- [Deletion Vectors on Delta Lake tables: introduction](https://www.youtube.com/watch?v=fTj2iXTrp5Q) — Apostolos Athanasiou, 17 min. What a soft delete leaves on disk.
- [Understanding Spark UI in Depth: jobs, stages, tasks](https://www.youtube.com/watch?v=t-42lC167k4) — DataBeli, 19 min. The UI behind the query profile.
