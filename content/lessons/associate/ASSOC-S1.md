# Databricks Intelligence Platform — 6%

The smallest section, but its ideas underpin everything else.

> **Names:** Data Intelligence Platform (Lakehouse Platform), Lakeflow Jobs (Workflows), SQL warehouse (SQL endpoint), Standard access mode (shared, `USER_ISOLATION`), Dedicated access mode (single user, `SINGLE_USER`), retired High Concurrency clusters. The API still accepts the old access-mode values, and old names still appear in distractors.

## What the exam asks

- A table needs reliable rollback, an audit trail, and one governed copy for AI and BI — Delta Lake for the guarantees, Unity Catalog for the governance (`ASSOC-S1-O1`)
- A bad load overwrote a table an hour ago — `DESCRIBE HISTORY`, then `RESTORE TABLE ... TO VERSION AS OF n`, itself a new version (`ASSOC-S1-O1`)
- Time travel to a version from three weeks ago fails after weekly `VACUUM` — VACUUM keeps 7 days of unreferenced files by default; the log keeps 30 days (`ASSOC-S1-O1`)
- Two workspaces in the same region must see the same tables and grants — attach both to one regional Unity Catalog metastore (`ASSOC-S1-O1`)
- A 12-minute nightly ETL job at lowest cost — job compute, which terminates when the run ends (`ASSOC-S1-O2`)
- Many analysts run ad-hoc SQL and queries queue at peak — a serverless SQL warehouse with more clusters (autoscaling), not a bigger fixed cluster (`ASSOC-S1-O2`)

## Defaults and limits

| Setting | Default or limit | Note |
|---|---|---|
| `delta.deletedFileRetentionDuration` | `interval 7 days` | how long `VACUUM` keeps files a current version no longer references; time travel past it is refused |
| `delta.logRetentionDuration` | `interval 30 days` | history older than this is cleaned up at checkpoints |
| Log vs file retention | log ≥ file retention | enforced from Databricks Runtime 18.0 (12.2 for Unity Catalog managed tables) |
| First table version | `0` | the `CREATE` itself; every later commit adds one |
| Metastores | one per region | linked to any number of workspaces in that region |
| All-purpose auto termination | 10 to 10,000 minutes; `0` disables | through the API, *unset* means the cluster never terminates |
| Terminated compute config | deleted after 30 days | unless pinned (up to 100 pinned per workspace) |
| SQL warehouse auto stop | serverless 10 min (UI min 5, API min 1); pro and classic 45 min (min 10) | |
| SQL warehouse scaling | min 1, max 1 cluster | raise the max for concurrency; about one cluster per 10 concurrent queries |
| SQL warehouse startup | serverless 2 to 6 s; pro and classic about 4 min | |
| Access mode `Auto` | Standard | Dedicated for ML runtimes, GPUs, or runtimes below 14.3 |

## Core components — `ASSOC-S1-O1`

### Architecture: where things run, where data sits

| Part | Runs in | Holds |
|---|---|---|
| **Control plane** | Databricks' account | the web app, notebooks' definitions, job scheduler, Unity Catalog metadata and permissions |
| **Classic compute plane** | *your* cloud account | clusters and pro or classic SQL warehouses — VMs you pay the cloud for, plus DBUs |
| **Serverless compute plane** | Databricks' account, same region as the workspace | serverless notebooks, jobs, pipelines and SQL warehouses |
| **Storage** | your cloud account (or default storage for serverless workspaces) | the Parquet files and `_delta_log` of your tables, and volumes |

The control plane never processes your data; the compute plane does. A question
asking "where does the data live" is answering *cloud object storage*, not the
workspace, and not the metastore — the metastore holds metadata and grants only.

The **metastore** is Unity Catalog's top-level container and is **regional**:
one per region, attachable to many workspaces in that region. That is how two
workspaces share one set of tables and grants. Under it sits the three-level
namespace `catalog.schema.object`.

```sql
SELECT current_metastore();   -- <cloud>:<region>:<metastore id>
SHOW CATALOGS;
DESCRIBE DETAIL main.sales.orders;   -- format, location, numFiles, tableFeatures
```

### Delta Lake: Parquet plus a log

**Delta Lake** is Parquet plus an ordered transaction log. Parquet gives columnar
storage and compression; the *log* gives everything that matters for reliability:

- **ACID transactions** — a write is atomic, so readers never see it half-finished
- **Time travel** — every version is numbered and queryable, so a bad load is
  recoverable with `RESTORE`
- **Schema enforcement** — a write with a column the table lacks, or a value that
  cannot be cast to the column's type, is rejected rather than silently reshaping
  the table. A write that
  is *missing* columns is accepted with `NULL`s: completeness is a `NOT NULL`
  constraint's job, not the schema's

The log lives in the table's `_delta_log/` directory. Each commit is one JSON
file named by its version (`00000000000000000000.json`, `...01.json`), listing
the data files it **adds** and **removes** plus metadata. A reader rebuilds the
table by replaying the log, so "the table" is whichever files the latest version
says are live. Every so often the log is summarised into a **Parquet checkpoint**
so readers need not replay every JSON file; Databricks says the checkpoint
frequency may change without notice, so do not memorise an interval. Old log
files are removed automatically after checkpointing, by `logRetentionDuration`,
not by `VACUUM`.

### What a commit is

Every successful write is exactly one commit, one new version, one row in
`DESCRIBE HISTORY`. Four statements against a fresh table:

```sql
CREATE TABLE t (id INT, amount DOUBLE, ts TIMESTAMP);           -- version 0
INSERT INTO t VALUES (1, 10.0, now()), (2, 20.0, now());        -- version 1
UPDATE t SET amount = 0 WHERE id = 1;                           -- version 2
RESTORE TABLE t TO VERSION AS OF 1;                             -- version 3

DESCRIBE HISTORY t;          -- version, timestamp, userName, operation,
                             -- operationParameters, readVersion, operationMetrics
```

| version | operation | operationParameters | operationMetrics (selected) |
|---|---|---|---|
| 0 | `CREATE TABLE` (`CREATE OR REPLACE TABLE` if replaced) | `isManaged`, `properties` | — |
| 1 | `WRITE` | `mode: Append` | `numOutputRows: 2`, `numFiles: 1` |
| 2 | `UPDATE` | `predicate` | `numUpdatedRows: 1` |
| 3 | `RESTORE` | `version: 1` | `numRestoredFiles`, `numRemovedFiles` |

Three things follow. An `INSERT` shows up as `WRITE`, not `INSERT`. `RESTORE` does
not rewind the version counter: it is a new commit (version 3) whose content
equals version 1, so version 2 is still there and the restore can itself be
undone. And because `RESTORE` is a data-changing commit, a downstream stream
reading the table may see the restored rows again as new data.

> **Measured on Free Edition:** the four statements above produced versions 0 to 3
> with operations `CREATE OR REPLACE TABLE`, `WRITE`, `UPDATE`, `RESTORE`. The
> `UPDATE` wrote a deletion vector instead of rewriting the file
> (`numDeletionVectorsAdded: 1`, `numCopiedRows: 0`), because new managed tables
> have `delta.enableDeletionVectors = true` and row tracking on. `RESTORE` returned
> `table_size_after_restore`, `num_of_files_after_restore`, `num_removed_files`,
> `num_restored_files`, `removed_files_size`, `restored_files_size`. `DESCRIBE
> DETAIL` showed an empty `location` for the managed table, so `_delta_log` cannot be
> browsed there.

### Time travel and its expiry date

```sql
SELECT * FROM t VERSION AS OF 1;
SELECT * FROM t@v1;                                -- same thing
SELECT * FROM t TIMESTAMP AS OF '2026-10-20';      -- date or timestamp string
SELECT * FROM t TIMESTAMP AS OF date_sub(current_date(), 1);

RESTORE TABLE t TO VERSION AS OF 1;
RESTORE TABLE t TO TIMESTAMP AS OF '2026-10-20 08:00:00';
```

Reading an old version needs **two** things to still exist: its log entries and
its data files. Each has its own clock:

- **Data files** — `VACUUM` deletes files that no current version references and
  that have been unreferenced longer than `delta.deletedFileRetentionDuration`
  (default **7 days**). After that, versions older than 7 days fail even though the
  log still lists them. Where predictive optimization is on (the default for newer
  accounts), it runs `VACUUM` on Unity Catalog managed tables for you, so assume
  it *will* run.
- **Log entries** — kept for `delta.logRetentionDuration` (default **30 days**), then
  cleaned up at the next checkpoint.

So time travel's real expiry date is **7 days**, vacuumed or not. On Unity
Catalog managed tables (and on any table from Databricks Runtime 18.0) a query for
a version older than `deletedFileRetentionDuration` is refused outright, even while
its files still exist; the 30-day log only matters once file retention is raised.
To keep a longer window, raise both properties, log at least as long as files:

```sql
ALTER TABLE t SET TBLPROPERTIES (
  'delta.logRetentionDuration'         = 'interval 90 days',
  'delta.deletedFileRetentionDuration' = 'interval 90 days'
);
VACUUM t;               -- uses the table's retention (7 days by default)
VACUUM t RETAIN 168 HOURS;
VACUUM t DRY RUN;       -- lists what would be deleted, deletes nothing
```

Time travel is a recovery tool, not an archive: for long-term history, write
snapshots to their own table.

![Step through a table's commits and see what time travel can still reach](visual:delta-commit-log?h=900)

> **Measured on Free Edition:** a version number that does not exist fails with
> `DELTA_VERSION_NOT_FOUND` and lists the available range (`[0, 3]`); a timestamp
> before the first commit fails with `DELTA_TIMESTAMP_EARLIER_THAN_COMMIT_RETENTION`.
> `VACUUM ... RETAIN 0 HOURS` is refused on serverless, and the retention safety
> check cannot be switched off there. `VACUUM` itself adds two versions to the
> history, `VACUUM START` and `VACUUM END`, even when it deletes nothing. With
> `deletedFileRetentionDuration` lowered to `interval 0 hours`, `VERSION AS OF 1`
> failed while its files were still on storage, with
> `DELTA_UNSUPPORTED_TIME_TRAVEL_BEYOND_DELETED_FILE_RETENTION_DURATION`, and after a
> `VACUUM`, `RESTORE` to an old version failed because its files had been deleted.

### Clones

A clone is a new table, with its **own history starting at version 0**, made from
a source table (or one of its versions).

| | Shallow clone | Deep clone |
|---|---|---|
| Copies | metadata only; points at the source's data files | metadata and data files |
| Cost to create | cheap | full copy |
| Depends on source | yes: vacuuming the source can break it | no |
| Copies history | no | no |
| Suits | testing a change, short-lived experiments | backups, migration, a fixed copy to hand over |

```sql
CREATE TABLE t_dev  SHALLOW CLONE t;                  -- metadata only
CREATE TABLE t_bak  DEEP CLONE t VERSION AS OF 2;     -- CLONE alone means DEEP
CREATE TABLE t_snap DEEP CLONE t TIMESTAMP AS OF '2026-10-20';
CREATE OR REPLACE TABLE t_bak DEEP CLONE t;           -- re-sync from the source
```

Both copy schema, partitioning, constraints and table properties; neither copies
the table description, history or Unity Catalog tags. On Unity Catalog, a shallow
clone cannot be overwritten with `CREATE OR REPLACE`: drop it and recreate it.
Streaming tables and materialized views cannot be cloned.

> **Measured on Free Edition:** both clones of a managed table worked. Each started
> at version 0 with operation `CLONE` and `operationParameters` recording `source`,
> `sourceVersion` and `isShallow`. The shallow clone copied 0 files; the deep clone
> of version 2 copied 2 files.

### Generated columns

A generated column is computed from other columns on every write; you never
supply it. An identity column is a generated surrogate key.

```sql
CREATE TABLE events (
  id         BIGINT GENERATED ALWAYS AS IDENTITY,       -- or BY DEFAULT AS IDENTITY
  event_ts   TIMESTAMP,
  event_date DATE GENERATED ALWAYS AS (CAST(event_ts AS DATE))
);
INSERT INTO events (event_ts) VALUES (now());           -- id and event_date filled in
```

A supplied value that disagrees with the expression is rejected. `GENERATED
ALWAYS AS IDENTITY` refuses any explicit value; `GENERATED BY DEFAULT AS IDENTITY`
accepts one. Identity values are unique and increasing but not guaranteed
consecutive.

> **Measured on Free Edition:** inserting `event_date` that did not match
> `CAST(event_ts AS DATE)` failed with `DELTA_VIOLATE_CONSTRAINT_WITH_VALUES` (the
> generated column is enforced as a CHECK constraint); an explicit value for a
> `GENERATED ALWAYS AS IDENTITY` column failed with
> `DELTA_IDENTITY_COLUMNS_EXPLICIT_INSERT_NOT_SUPPORTED`.

### Unity Catalog

**Unity Catalog** governs across workspaces: a three-level namespace
(`catalog.schema.table`), one permission model for tables, volumes, models and
functions, plus lineage and audit.

Pair them and you have the answer to a whole family of exam questions: *reliable
rollback, audit trail, and one governed copy for both AI and BI* is Delta Lake for the
guarantees, Unity Catalog for the governance.

## Compute — `ASSOC-S1-O2`

| Type | Lives | Suits | Billed |
|---|---|---|---|
| Job compute | created per run, terminates after | scheduled ETL | lower DBU rate |
| All-purpose | until stopped | interactive development | higher DBU rate |
| SQL warehouse | until idle timeout | BI and ad-hoc SQL | its own rate |
| Serverless | Databricks' own compute plane; a variant of the three above, not a fourth type | fast start, no configuration, no init scripts or JVM access | per second while in use |

**DBU** (Databricks Unit) is the billing unit: processing capability per hour,
at a rate set by compute type and size. On classic compute you pay DBUs to
Databricks *and* the VMs to your cloud provider; on serverless the DBU rate covers
both. Same work, different rate: that is why job compute is cheaper than
all-purpose for the same cluster.

**The cost question is nearly always about idle time.** A 12-minute nightly job on job
compute costs 12 minutes; the same job on an all-purpose cluster left running costs 24
hours at a higher rate. When a question pairs a scheduled workload with "lowest cost",
job compute is the answer.

For many concurrent analysts running ad-hoc SQL, a SQL warehouse (serverless where
available) with autoscaling beats a fixed-size cluster — which is either wasteful when
idle or a bottleneck at peak. "High Concurrency" clusters are a retired cluster mode;
if a question offers one, the warehouse is the current answer.

### Access modes

| Access mode | API value (old alias) | Users | Languages | Unity Catalog |
|---|---|---|---|---|
| **Standard** (was shared) | `DATA_SECURITY_MODE_STANDARD` (`USER_ISOLATION`) | many, isolated from each other | Python, SQL, Scala | yes |
| **Dedicated** (was single user) | `DATA_SECURITY_MODE_DEDICATED` (`SINGLE_USER`) | one user or one group | Python, SQL, Scala, R | yes |
| **Auto** | `DATA_SECURITY_MODE_AUTO` | picks Standard, or Dedicated for ML runtimes, GPUs, runtime < 14.3 | | yes |
| No isolation shared | legacy | many, not isolated | all | **no** |

Databricks recommends Standard unless you need something it lacks: R, ML
runtimes, GPUs, RDD APIs. "Needs R" or "needs an ML runtime" points at Dedicated;
"several engineers share one Unity Catalog cluster" points at Standard.

### Photon and warehouse tiers

**Photon** is Databricks' vectorized query engine, written in C++, used under the
existing Spark APIs without code changes. It is always on for serverless compute
and SQL warehouses, on by default for classic clusters (`runtime_engine: PHOTON`
must be set explicitly through the API), and bills at its own DBU rate. It speeds
up SQL and DataFrame work on large data; it does not speed up Python UDFs, RDDs,
or queries that already finish in under two seconds.

| Warehouse type | Compute plane | Startup | Photon | Predictive IO | Intelligent workload management |
|---|---|---|---|---|---|
| **Serverless** | Databricks' | 2 to 6 s | yes | yes | yes |
| **Pro** | yours | about 4 min | yes | yes | no |
| **Classic** | yours | about 4 min | yes | no | no |

Serverless is the default type where the account allows it. Size (`2X-Small` to
`4X-Large`) is for query *latency*; the number of clusters is for *concurrency*.

```jsonc
// all-purpose cluster (Clusters API) — the option names questions use
{
  "cluster_name": "dev-shared",
  "spark_version": "16.4.x-scala2.12",
  "data_security_mode": "DATA_SECURITY_MODE_STANDARD",
  "runtime_engine": "PHOTON",
  "autoscale": {"min_workers": 1, "max_workers": 4},
  "autotermination_minutes": 30          // unset through the API = never terminates
}

// SQL warehouse (Warehouses API)
{
  "name": "bi",
  "cluster_size": "Small",               // latency
  "min_num_clusters": 1,                 // concurrency: defaults 1 and 1
  "max_num_clusters": 4,
  "auto_stop_mins": 10,                  // serverless default 10, pro/classic 45
  "enable_serverless_compute": true,
  "warehouse_type": "PRO"                // or "CLASSIC"; serverless ones report PRO
}
```

### Choosing compute in three questions

1. **Is it SQL for people or BI tools?** Yes → SQL warehouse, serverless where
   available; more clusters for more users, a bigger size for slower queries.
2. **Does it run on a schedule with nobody watching?** Yes → job compute (or
   serverless jobs): it exists only for the run, at the lower rate. Never an
   all-purpose cluster.
3. **Is someone developing interactively?** Yes → all-purpose compute with auto
   termination, Standard access mode if it is shared, Dedicated if it needs R, ML
   runtimes or GPUs. Serverless notebooks if nothing needs init scripts, custom
   JARs or a particular runtime.

If the question stresses "no infrastructure to manage" or "start in seconds",
serverless; if it stresses "custom libraries via init scripts" or "a specific
runtime", classic.

> **Measured on Free Edition:** Free Edition is serverless-only, so compute
> *selection* cannot be practised there. Its one warehouse, Serverless Starter
> Warehouse, reports `warehouse_type: PRO`, `enable_serverless_compute: true`,
> `cluster_size: 2X-Small`, `auto_stop_mins: 10`, `min_num_clusters` and
> `max_num_clusters` both 1, and `enable_photon: true` — the documented serverless
> defaults apart from the size. Learn the trade-offs; you will be asked to reason
> about them rather than configure them.

## Further reading

Official documentation for what this section tests, one link per topic:

- [Databricks concepts](https://docs.databricks.com/aws/en/getting-started/concepts) — the vocabulary the whole exam assumes: workspace, account, metastore, compute plane.
- [High-level architecture](https://docs.databricks.com/aws/en/getting-started/high-level-architecture) — control plane, classic and serverless compute planes, workspace storage.
- [Create a Unity Catalog metastore](https://docs.databricks.com/aws/en/data-governance/unity-catalog/create-metastore) — one metastore per region, linked to many workspaces.
- [What is Delta Lake?](https://docs.databricks.com/aws/en/delta/) — the transaction log, ACID and the feature list.
- [Table history and time travel](https://docs.databricks.com/aws/en/delta/history) — `DESCRIBE HISTORY`, `VERSION AS OF`, `RESTORE`, retention properties.
- [VACUUM](https://docs.databricks.com/aws/en/tables/operations/vacuum) — the 7-day threshold and what it does to time travel.
- [Clone a table](https://docs.databricks.com/aws/en/tables/operations/clone) — shallow vs deep, and the Unity Catalog limits.
- [Generated columns](https://docs.databricks.com/aws/en/tables/features/generated-columns) — computed and identity columns.
- [Compute](https://docs.databricks.com/aws/en/compute/) — job vs all-purpose, access modes, policies.
- [Compute configuration reference](https://docs.databricks.com/aws/en/compute/configure) — access modes, Photon, auto termination.
- [What is Photon?](https://docs.databricks.com/aws/en/compute/photon) — what it accelerates and what it does not.
- [Serverless compute](https://docs.databricks.com/aws/en/compute/serverless/) — what it removes from your hands and what it cannot do.
- [SQL warehouse types](https://docs.databricks.com/aws/en/compute/sql-warehouse/warehouse-types) — classic, pro and serverless warehouses.
- [Create a SQL warehouse](https://docs.databricks.com/aws/en/compute/sql-warehouse/create) — size, scaling and auto stop defaults.
- [Medallion architecture](https://docs.databricks.com/aws/en/lakehouse/medallion) — bronze, silver and gold as the exam defines them.
- [Exam page](https://www.databricks.com/learn/certification/data-engineer-associate) — official guide, section weights and policies.

Videos for another angle on the hard parts (channel, length):

- [Diving into Delta Lake: Unpacking the Transaction Log](https://www.youtube.com/watch?v=F91G4RoA8is) — Databricks, 53 min. The definitive walk through commits, checkpoints and optimistic concurrency.
- [Databricks Medallion Architecture Explained in 2 minutes](https://www.youtube.com/watch?v=RjC8LnvZsIc) — Tech With Yeshwanth, 2 min. The layer model in one sitting.
