# Databricks Intelligence Platform — 6%

The smallest section, but its ideas underpin everything else.

## Core components — `ASSOC-S1-O1`

**Delta Lake** is Parquet plus an ordered transaction log. Parquet gives columnar
storage and compression; the *log* gives everything that matters for reliability:

- **ACID transactions** — a write is atomic, so readers never see it half-finished
- **Time travel** — every version is numbered and queryable, so a bad load is
  recoverable with `RESTORE`
- **Schema enforcement** — writes that do not fit are rejected rather than silently
  reshaping the table

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

**The cost question is nearly always about idle time.** A 12-minute nightly job on job
compute costs 12 minutes; the same job on an all-purpose cluster left running costs 24
hours at a higher rate. When a question pairs a scheduled workload with "lowest cost",
job compute is the answer.

For many concurrent analysts running ad-hoc SQL, a SQL warehouse (serverless where
available) with autoscaling beats a fixed-size cluster — which is either wasteful when
idle or a bottleneck at peak. "High Concurrency" clusters are a retired cluster mode;
if a question offers one, the warehouse is the current answer.

> Free Edition is serverless-only, so compute *selection* cannot be practised there.
> Learn the trade-offs; you will be asked to reason about them rather than configure
> them.

## Further reading

Official documentation for what this section tests, one link per topic:

- [Databricks concepts](https://docs.databricks.com/aws/en/getting-started/concepts) — the vocabulary the whole exam assumes: workspace, account, metastore, compute plane.
- [What is Delta Lake?](https://docs.databricks.com/aws/en/delta/) — the transaction log, ACID and the feature list.
- [Table history and time travel](https://docs.databricks.com/aws/en/delta/history) — `DESCRIBE HISTORY`, `VERSION AS OF`, `RESTORE`.
- [Compute](https://docs.databricks.com/aws/en/compute/) — job vs all-purpose, access modes, policies.
- [Serverless compute](https://docs.databricks.com/aws/en/compute/serverless/) — what it removes from your hands and what it cannot do.
- [SQL warehouse types](https://docs.databricks.com/aws/en/compute/sql-warehouse/warehouse-types) — classic, pro and serverless warehouses.
- [Medallion architecture](https://docs.databricks.com/aws/en/lakehouse/medallion) — bronze, silver and gold as the exam defines them.
- [Exam page](https://www.databricks.com/learn/certification/data-engineer-associate) — official guide, section weights and policies.

Videos for another angle on the hard parts (channel, length):

- [Diving into Delta Lake: Unpacking the Transaction Log](https://www.youtube.com/watch?v=F91G4RoA8is) — Databricks, 53 min. The definitive walk through commits, checkpoints and optimistic concurrency.
- [Databricks Medallion Architecture Explained in 2 minutes](https://www.youtube.com/watch?v=RjC8LnvZsIc) — Tech With Yeshwanth, 2 min. The layer model in one sitting.
