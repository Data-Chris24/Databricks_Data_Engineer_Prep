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
| Serverless | managed entirely by Databricks | fast start, no configuration | per use |

**The cost question is nearly always about idle time.** A 12-minute nightly job on job
compute costs 12 minutes; the same job on an all-purpose cluster left running costs 24
hours at a higher rate. When a question pairs a scheduled workload with "lowest cost",
job compute is the answer.

For many concurrent analysts running ad-hoc SQL, high concurrency with autoscaling
beats a fixed-size cluster — which is either wasteful when idle or a bottleneck at
peak.

> Free Edition is serverless-only, so compute *selection* cannot be practised there.
> Learn the trade-offs; you will be asked to reason about them rather than configure
> them.
