# Troubleshooting, Monitoring and Optimization — 10%

Reading what the platform tells you, and knowing which knob matches which symptom.

## Monitoring jobs — `ASSOC-S6-O1`, `ASSOC-S6-O2`

Run history is where an investigation starts. Comparing a slow run's task durations
against previous runs localises the problem before you open a single log — if one task
went from 2 minutes to 70 while the rest held steady, you know where to look.

**A successful run can still be unhealthy.** A job that normally takes 20 minutes and
took 90 has told you something, even though it went green. Left alone that becomes a
missed SLA or a quota breach.

The DAG view shows upstream blockers; the run list shows failure rates over time.

## Reading the Spark UI — `ASSOC-S6-O3`

| Symptom in the UI | Means |
|---|---|
| One task far slower than the rest, max shuffle read >> median | **data skew** — one key holds disproportionate data |
| "spill (disk)" on a stage | working set exceeded memory; correct but slow |
| Hundreds of sub-second tasks | over-partitioned; per-task overhead dominates |
| Long shuffle read/write times | too much data moving between stages |

**Skew** is the classic. Adaptive Query Execution with skew join handling splits
oversized partitions at runtime, which fixes the cause with no code change — try that
before hand-salting keys.

**Spill** is Spark surviving rather than failing: it writes to disk instead of raising
OOM. The result is right and slow. Causes are partitions that are too large or a skewed
key; fixes are more partitions, less data per task, or addressing the skew.

## Layout optimization — `ASSOC-S6-O4`

**Liquid clustering** is now preferred over partitioning for most tables. A partition
column is a decision you are stuck with — changing it means rewriting the table — and
choosing badly gives you either huge skewed partitions or millions of tiny files.
Clustering keys can be changed with `ALTER TABLE`, and the layout adapts incrementally.

**Predictive optimization** runs maintenance — `OPTIMIZE`, `VACUUM` and statistics
collection — automatically, and only on Unity Catalog *managed* tables, because the
catalog owns their layout; external tables are yours to maintain.

**Deletion vectors** mark rows as deleted rather than rewriting files, making deletes
and updates much cheaper; the files are cleaned up later during maintenance.

## Compute failures — `ASSOC-S6-O5`

| Failure | Usual cause |
|---|---|
| Cluster will not start | cloud quota, a bad init script, an unavailable instance type |
| Library conflict | two libraries pinning incompatible versions of a shared dependency |
| Driver OOM | `collect()` or `toPandas()` on a large result |
| Executor OOM | partitions too large, or heavy skew |

**Driver OOM is not fixed by a bigger cluster.** `collect()` pulls every row into a
single JVM; more executors do not help. Write the result to a table instead.

> On serverless compute there are no clusters to configure, so these particular
> failures cannot occur — and cannot be practised. This objective is theory on Free
> Edition.

## Further reading

Official documentation for what this section tests, one link per topic:

- [Monitor jobs](https://docs.databricks.com/aws/en/jobs/monitor) — run history, matrix view and duration trends.
- [Diagnose cost and performance with the Spark UI](https://docs.databricks.com/aws/en/optimizations/spark-ui-guide/) — the guided walk from job to stage to task.
- [Skew and spill](https://docs.databricks.com/aws/en/optimizations/spark-ui-guide/long-spark-stage-page) — the two fingerprints and how to tell them apart.
- [Liquid clustering](https://docs.databricks.com/aws/en/delta/clustering) — `CLUSTER BY`, changing keys, `OPTIMIZE`.
- [OPTIMIZE and compaction](https://docs.databricks.com/aws/en/delta/optimize) — small files and the target size.
- [VACUUM](https://docs.databricks.com/aws/en/delta/vacuum) — the 7-day default and what it does to time travel.
- [Predictive optimization](https://docs.databricks.com/aws/en/optimizations/predictive-optimization) — managed tables only, and what it runs.
- [Deletion vectors](https://docs.databricks.com/aws/en/delta/deletion-vectors) — why deletes stopped rewriting files.
- [Compute configuration best practices](https://docs.databricks.com/aws/en/compute/cluster-config-best-practices) — the sizing and failure-mode advice.
- [Libraries](https://docs.databricks.com/aws/en/libraries/) — notebook-scoped vs cluster-scoped, and init scripts.

Videos for another angle on the hard parts (channel, length):

- [Understanding Spark UI in Depth: jobs, stages, tasks](https://www.youtube.com/watch?v=t-42lC167k4) — DataBeli, 19 min. Reading the UI the way the exam expects.
- [Databricks Liquid Clustering Introduction](https://www.youtube.com/watch?v=na3Wp-j855g) — Apostolos Athanasiou, 13 min. Clustering versus partitioning and Z-order, demonstrated.
