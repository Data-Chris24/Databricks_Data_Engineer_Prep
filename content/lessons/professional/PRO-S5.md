# Monitoring and Alerting — 10%

Two halves. First, **which source answers which question**: that is what the
exam tests, more than syntax. Second, **designing an alert people will still
believe in a month**, which is a data question, not a tooling one.

## Where the signals live — `PRO-S5-O1`, `PRO-S5-O2`, `PRO-S5-O4`

| Source | Answers | Reach it with |
|---|---|---|
| System tables (`system.*`) | cost, usage, audit, lineage, workload | SQL |
| Job run history | which task, how long, how often it fails | Jobs UI, REST API, CLI |
| `DESCRIBE HISTORY` | what a table did and when | SQL, on any tier |
| Query profile | where time and bytes went in one query | SQL editor |
| Spark UI | stages, tasks, skew, spill, shuffle | the run's Spark UI |
| Pipeline event log | pipeline state, expectations, data quality counts | SQL on the event log |

**System tables** are Unity Catalog-governed, read-only tables that the platform
maintains: `system.billing.usage` (DBUs by SKU, workspace, tag), `system.access.audit`
(who did what), `system.access.table_lineage` and `column_lineage`,
`system.compute.*` (clusters, warehouses, node timelines) and
`system.lakeflow.*` (jobs, job runs, pipelines). The shape of the two questions
the exam asks most:

```sql
-- what is this costing, by SKU, this month
SELECT sku_name, sum(usage_quantity) AS dbus
FROM system.billing.usage
WHERE usage_date >= date_trunc('month', current_date())
GROUP BY sku_name ORDER BY dbus DESC;

-- who read this table in the last week
SELECT user_identity.email, count(*) AS reads
FROM system.access.audit
WHERE action_name = 'getTable' AND event_date >= current_date() - 7
GROUP BY 1 ORDER BY reads DESC;
```

**Query profile** is per query: which operator took the time, how many bytes were
read versus pruned, whether a join broadcast or shuffled. **Spark UI** is per job
run: the stage whose one task is far slower than the rest (skew), "spill (disk)"
(working set exceeded memory), hundreds of sub-second tasks (over-partitioned).

**Pipeline event logs** record every update of a declarative pipeline: which
flows ran, how many rows each expectation dropped or flagged, and pipeline-level
errors. Query them as a table to trend data-quality counts over time rather than
reading one run's page.

> Free Edition exposes `system.*` too (`billing`, `access`, `lakeflow`, `compute`
> and more, with real rows), so the queries below can be run there. The exam asks
> which table answers which question. `DESCRIBE HISTORY` works on every table,
> whatever the tier.

## Monitoring through the API and CLI — `PRO-S5-O3`

```bash
databricks jobs list-runs --job-id <id> --limit 25
databricks jobs get-run <run-id>
databricks jobs get-run-output <task-run-id>
databricks pipelines get <pipeline-id>
```

The same calls exist as REST endpoints (`/api/2.2/jobs/runs/list`,
`/runs/get`, `/runs/get-output`). The API is how monitoring outlives a person
watching a dashboard: run durations pulled on a schedule become a trend you can
alert on, and `runs/get-output` returns a notebook's exit value, which is how
this repo's app reads a grade.

## SQL Alerts on data quality — `PRO-S5-O5`

A SQL Alert is a saved query plus a condition on its result, evaluated on a
schedule, notifying a destination when the condition holds.

```sql
-- the query behind an alert
SELECT count(*) AS breaches
FROM metrics
WHERE run_date = current_date() AND rows_processed < 880;
```

Fire when `breaches > 0`. A **fixed threshold is honest only when the metric is
stationary**. When it has a cycle or drifts, the design rules below apply.

Four rules for an alert worth keeping:

1. **Compare like with like.** A rolling baseline moves with the metric and
   survives a level shift. On a seasonal metric, compare the same day of week; a
   Saturday against a Friday is a weekend against a weekday.
2. **Alert on direction, not deviation.** A campaign doubling volume is not an
   incident; the same deviation downward usually is.
3. **Require persistence.** One low day is noise, three consecutive low days is
   a trend. You trade a day of latency for an alert people believe.
4. **Notify a channel, not a person.** People go on holiday.

```sql
-- fire only when the last 3 days are all below their baseline
SELECT count(*) AS consecutive_low
FROM (
  SELECT run_date, rows_processed,
         avg(rows_processed) OVER (
           PARTITION BY day_type ORDER BY run_date
           ROWS BETWEEN 6 PRECEDING AND 1 PRECEDING
         ) AS baseline
  FROM typed_metrics
)
WHERE run_date >= current_date() - 2 AND rows_processed < baseline * 0.9;
```

An alert that fires too often is ignored within a fortnight, and the real one is
ignored with it. An alert that never fires is indistinguishable from none.

## Job notifications — `PRO-S5-O6`

Jobs carry notifications at the job or task level: on start, success, failure,
and **duration warnings** (a threshold after which a still-running run notifies)
and **streaming backlog** thresholds. Destinations are email, Slack, Teams,
PagerDuty or a webhook, configured once as notification destinations and reused.
In the API and in bundles this is the `email_notifications`,
`webhook_notifications` and `health` blocks on the job; a run that exceeds
`RUN_DURATION_SECONDS` is the standard "it went green but took four times as
long" catch.

## Further reading

Official documentation for what this section tests, one link per topic:

- [System tables](https://docs.databricks.com/aws/en/admin/system-tables/) — the catalogue of `system.*` schemas.
- [Billable usage](https://docs.databricks.com/aws/en/admin/system-tables/billing) — `system.billing.usage` and `list_prices`.
- [Audit logs](https://docs.databricks.com/aws/en/admin/system-tables/audit-logs) — `system.access.audit` actions and columns.
- [Lineage system tables](https://docs.databricks.com/aws/en/admin/system-tables/lineage) — table and column lineage.
- [Jobs system tables](https://docs.databricks.com/aws/en/admin/system-tables/jobs) — `system.lakeflow` run and task timelines.
- [Query history system table](https://docs.databricks.com/aws/en/admin/system-tables/query-history) — `system.query.history`.
- [Monitor jobs](https://docs.databricks.com/aws/en/jobs/monitor) — run history and trends.
- [Job notifications](https://docs.databricks.com/aws/en/jobs/notifications) — email, webhooks and the streaming backlog metrics.
- [SQL alerts](https://docs.databricks.com/aws/en/sql/user/alerts/) — conditions, schedules and destinations.
- [Pipeline event log](https://docs.databricks.com/aws/en/ldp/observability) — `event_log()` and the `flow_progress` payload.
- [Query profile](https://docs.databricks.com/aws/en/sql/user/queries/query-profile) — where a single query's time went.

Videos for another angle on the hard parts (channel, length):

- [Monitoring Databricks with System Tables](https://www.youtube.com/watch?v=VfqLBJvqomM) — Dustin Vannoy, 16 min. Usage and audit queries you can copy.
- [Lineage System Table in Unity Catalog](https://www.youtube.com/watch?v=bZXswjZ0avA) — Databricks, 32 min. Lineage as data.
