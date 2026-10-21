# Monitoring and Alerting — 10%

Two halves. First, **which source answers which question**: that is what the
exam tests, more than syntax. Second, **designing an alert people will still
believe in a month**, which is a data question, not a tooling one.

> **Names:** Lakeflow Jobs (Workflows), Lakeflow Spark Declarative Pipelines
> (Delta Live Tables, DLT), `system.lakeflow` (`system.workflow`), SQL alerts
> (legacy alerts, which had an `UNKNOWN` state), Declarative Automation Bundles
> (Databricks Asset Bundles). Billing still labels pipeline usage
> `billing_origin_product = 'DLT'`.

## What the exam asks

- "Finance wants last month's spend in dollars, by team tag" — `system.billing.usage` joined to `system.billing.list_prices`, grouped on `custom_tags` (`PRO-S5-O1`)
- "Which job ran the slowest query, and did it spill?" — `system.query.history`, `query_source.job_info` and `spilled_local_bytes` (`PRO-S5-O1`)
- "One task in a stage takes ten minutes, the rest take seconds" — Spark UI stage task-duration distribution: skew (`PRO-S5-O2`)
- "Script a nightly check of the last 25 runs of a job" — `databricks jobs list-runs --job-id ... --limit 25`, or `GET /api/2.2/jobs/runs/list` (`PRO-S5-O3`)
- "How many rows did each expectation drop in the last update?" — `event_log()`, `event_type = 'flow_progress'`, `details:flow_progress.data_quality.expectations` (`PRO-S5-O4`)
- "The job went green but took four times as long" — `health` rule on `RUN_DURATION_SECONDS` plus `on_duration_warning_threshold_exceeded` (`PRO-S5-O6`)

## Defaults and limits

| Setting | Default or limit | Note |
|---|---|---|
| System tables free retention | 365 days | `list_prices` indefinite, `compute.node_timeline` 90 days |
| `job_run_timeline` row | at most one hour of a run | long runs are sliced; `result_state` is set only on the last slice |
| Job `timeout_seconds` | `0` | no timeout |
| Job `health` rule `op` | `GREATER_THAN` only | metrics: `RUN_DURATION_SECONDS`, `STREAMING_BACKLOG_BYTES` / `_RECORDS` / `_SECONDS` / `_FILES` |
| Streaming backlog notification | 10-minute average, repeated every 30 minutes | not supported on pipeline tasks |
| System destinations per job event type | 3 | Slack, Teams, PagerDuty, webhook; email addresses on top |
| `notification_settings` | `no_alert_for_skipped_runs`, `no_alert_for_canceled_runs` off | task level adds `alert_on_last_attempt` |
| SQL alert states | `OK`, `TRIGGERED`, `ERROR` | `UNKNOWN` was legacy only |
| SQL alert simultaneous active runs | 250 per workspace | runs over the limit are skipped, not queued |
| `{{QUERY_RESULT_TABLE}}` in an alert template | first 100 rows | only email renders the HTML |
| `event_log()` caller | the MV / streaming table owner | views over it cannot be shared |

## Where the signals live — `PRO-S5-O1`, `PRO-S5-O2`, `PRO-S5-O4`

| Source | Answers | Reach it with |
|---|---|---|
| System tables (`system.*`) | cost, usage, audit, lineage, workload | SQL |
| Job run history | which task, how long, how often it fails | Jobs UI, REST API, CLI |
| `DESCRIBE HISTORY` | what a table did and when | SQL, on any tier |
| Query profile | where time and bytes went in one query | SQL editor, or the query history of a serverless notebook or job |
| Spark UI | stages, tasks, skew, spill, shuffle | the run's Spark UI (classic compute only; serverless has none) |
| Pipeline event log | pipeline state, expectations, data quality counts | `event_log()` or the published event log table |

### Which table answers which question

| Question | Table | Columns that answer it |
|---|---|---|
| What did we spend, in DBUs? | `system.billing.usage` | `sku_name`, `usage_quantity`, `usage_unit`, `usage_date` |
| What did it cost in money? | `usage` joined to `system.billing.list_prices` | `pricing.effective_list.default`, `price_start_time`, `price_end_time` |
| Which job, warehouse or pipeline spent it? | `system.billing.usage` | `usage_metadata.job_id`, `.job_run_id`, `.warehouse_id`, `.dlt_pipeline_id`, `.notebook_path` |
| Whose budget? | `system.billing.usage` | `custom_tags`, `identity_metadata.run_as` |
| Who did what, and who was refused? | `system.access.audit` | `service_name`, `action_name`, `user_identity.email`, `request_params`, `response.status_code`, `source_ip_address` |
| What feeds this table, and who reads it? | `system.access.table_lineage` / `column_lineage` | `source_table_full_name`, `target_table_full_name`, `entity_type`, `created_by` |
| Which query was slow, and why? | `system.query.history` | `total_duration_ms`, `read_bytes`, `pruned_files`, `spilled_local_bytes`, `from_result_cache`, `query_source` |
| How often does a job fail, how long does it run? | `system.lakeflow.job_run_timeline`, `job_task_run_timeline` | `result_state`, `termination_code`, `period_start_time`, `period_end_time` |
| What does the job look like now? | `system.lakeflow.jobs` (SCD type 2) | latest `change_time` per `job_id`, then drop rows with `delete_time` |
| How did a pipeline update end? | `system.lakeflow.pipeline_update_timeline` | `result_state`, `trigger_type`, `full_refresh_selection` |
| How busy were the warehouses and clusters? | `system.compute.warehouse_events`, `node_timeline` | `event_type`, `cluster_count`; CPU and memory per minute |
| How many rows did an expectation drop? | not a system table: the pipeline **event log** | `details:flow_progress.data_quality` |

**System tables** are Unity Catalog-governed, read-only tables that the platform
maintains. Account admins who are also metastore admins see them by default;
anyone else needs `USE CATALOG` on `system`, then `USE SCHEMA` and `SELECT` on
the schema. They are not real-time: job timelines typically land within an hour.
The shape of the questions the exam asks most:

```sql
-- what is this costing, by SKU, this month
SELECT sku_name, sum(usage_quantity) AS dbus
FROM system.billing.usage
WHERE usage_date >= date_trunc('month', current_date())
GROUP BY sku_name ORDER BY dbus DESC;

-- DBUs to money: join on cloud and SKU, inside the price's validity window
SELECT u.billing_origin_product,
       sum(u.usage_quantity)                                   AS dbus,
       sum(u.usage_quantity * lp.pricing.effective_list.default) AS list_cost
FROM system.billing.usage u
JOIN system.billing.list_prices lp
  ON  u.cloud = lp.cloud
  AND u.sku_name = lp.sku_name
  AND u.usage_start_time >= lp.price_start_time
  AND (lp.price_end_time IS NULL OR u.usage_end_time <= lp.price_end_time)
WHERE u.usage_date >= current_date() - 30
GROUP BY 1 ORDER BY list_cost DESC;

-- who looked up this table in the last week
SELECT user_identity.email, count(*) AS lookups
FROM system.access.audit
WHERE service_name = 'unityCatalog' AND action_name = 'getTable'
  AND request_params.full_name_arg = 'workspace.de_prep.orders'
  AND event_date >= current_date() - 7
GROUP BY 1 ORDER BY lookups DESC;

-- the slowest statements this week, and the job that ran each
SELECT statement_id, executed_by, total_duration_ms, read_bytes,
       pruned_files, spilled_local_bytes, query_source.job_info.job_id
FROM system.query.history
WHERE start_time >= current_date() - 7 AND execution_status = 'FINISHED'
ORDER BY total_duration_ms DESC LIMIT 10;
```

`list_prices` is a **list** price: `pricing.default` is the long-run list price,
`pricing.effective_list.default` folds in any promotion and is what usage is
billed at before discounts. A price row with `price_end_time` NULL is current;
forget the time window in the join and every usage row matches every historical
price. `system.billing.account_prices` holds negotiated prices where they exist.

`system.query.history` records SQL warehouses, serverless notebooks and jobs,
and pipelines; `compute.type` is `WAREHOUSE`, `SERVERLESS_COMPUTE` or
`CLASSIC_COMPUTE`, and `execution_status` is `FINISHED`, `FAILED` or `CANCELED`.
Queries on classic clusters are not among its sources.

The audit query finds metadata lookups; `system.access.table_lineage` also
records plain reads, as a row with `source_table_full_name` set,
`target_table_full_name` NULL and the reader in `created_by`. Only audit has
`response.status_code` (403 for a refused attempt) and `source_ip_address`.

> **Measured on Free Edition:** `system.*` is there with real rows (`access`,
> `billing`, `compute`, `lakeflow`, `query` and more), and the queries above
> run on the Serverless Starter Warehouse. The list-price join turned thirty
> days of this workspace's DBUs into about 38 USD at list. `usage_metadata.job_id`
> and `job_run_id` were filled for serverless job usage; `record_type` was
> `ORIGINAL` on every row (corrections arrive as `RETRACTION` and
> `RESTATEMENT` rows). `job_run_timeline` showed `result_state` values
> `SUCCEEDED`, `ERROR`, `CANCELLED` and `SKIPPED`, with termination codes such
> as `RUN_EXECUTION_ERROR`, `USER_CANCELLED` and `MAX_CONCURRENT_RUNS_EXCEEDED`.

**Query profile** is per query: which operator took the time, how many bytes were
read versus pruned, whether a join broadcast or shuffled. **Spark UI** is per job
run: the stage whose one task is far slower than the rest (skew), "spill (disk)"
(working set exceeded memory), hundreds of sub-second tasks (over-partitioned).

```text
Query profile            Spark UI (classic compute)
-------------            --------------------------
Top operators by time    Jobs > Stages > a stage > Summary Metrics
Rows / bytes read        Task duration: Min, 25th, Median, 75th, Max
Files read vs pruned       Max far above Median          -> skew
Spill to disk              Spill (Memory) / Spill (Disk) -> under-sized partitions
Join: broadcast or shuffle Shuffle Read / Write sizes    -> wide transformation cost
```

### Spill and shuffle as an alert

Both profiles answer "what happened in this run". To hear about spill and heavy
shuffles without opening either, query `system.query.history` on a schedule:
`spilled_local_bytes` is what a statement wrote to local disk,
`shuffle_read_bytes` what it sent over the network between stages.

```sql
-- top spillers this week, and the job behind each
SELECT statement_id, executed_by, total_duration_ms, spilled_local_bytes,
       query_source.job_info.job_id AS job_id,
       left(statement_text, 80) AS statement
FROM system.query.history
WHERE start_time >= current_timestamp() - INTERVAL 7 DAYS
  AND execution_status = 'FINISHED' AND spilled_local_bytes > 0
ORDER BY spilled_local_bytes DESC LIMIT 20;

-- shuffle-heavy: over 1 GB moved, and more than 3x the bytes read
SELECT statement_id, read_bytes, shuffle_read_bytes,
       round(shuffle_read_bytes / nullif(read_bytes, 0), 1) AS shuffle_to_read,
       query_source.job_info.job_id AS job_id
FROM system.query.history
WHERE start_time >= current_timestamp() - INTERVAL 7 DAYS
  AND execution_status = 'FINISHED'
  AND shuffle_read_bytes > 1024 * 1024 * 1024
  AND shuffle_read_bytes > 3 * read_bytes
ORDER BY shuffle_read_bytes DESC LIMIT 20;
```

As a SQL alert (see `PRO-S5-O5`), reduce it to one number per evaluation and
fire when it is above zero:

```sql
-- alert query: statements that spilled more than 1 GB in the last hour
SELECT count(*)                              AS spilling_queries,
       coalesce(max(spilled_local_bytes), 0) AS worst_spill_bytes
FROM system.query.history
WHERE start_time >= current_timestamp() - INTERVAL 1 HOUR
  AND execution_status = 'FINISHED'
  AND spilled_local_bytes > 1024 * 1024 * 1024;
```

```json
"evaluation": {
  "source": { "name": "spilling_queries" },
  "comparison_operator": "GREATER_THAN",
  "threshold": { "value": { "double_value": 0 } },
  "empty_result_state": "OK",
  "notification": { "retrigger_seconds": 3600 }
},
"schedule": { "quartz_cron_schedule": "0 0 * * * ?", "timezone_id": "UTC" }
```

An hourly schedule over a one-hour window sees each statement once, as long as
the rows have landed by then. The same per-query totals come from the query
history API, under other names:

```bash
databricks api get "/api/2.0/sql/history/queries?include_metrics=true&max_results=100" \
  | jq -r '.res[] | [.query_id, .metrics.spill_to_disk_bytes,
                    .metrics.network_sent_bytes, .metrics.task_total_time_ms] | @tsv' \
  | sort -t$'\t' -k2,2nr | head
```

**No system table records skew.** Skew lives in the spread of task inputs within
one stage, and both `system.query.history` and the API keep one total per
statement, with no per-task data. A skewed query and an even one with the same
totals look the same there. Skew needs the Spark UI's Summary Metrics (Max far
above the 75th percentile) or the query profile.

> **Measured on Free Edition:** both queries and the alert query run on the
> Serverless Starter Warehouse, and an alert with the evaluation above was
> accepted by `databricks alerts-v2` (created paused, then deleted). They return
> nothing to alert on: across all ~8,730 statements in `system.query.history`
> since 2026-08, `spilled_local_bytes` and `shuffle_read_bytes` are 0 on every
> row. Two deliberately skewed probes on the 2X-Small warehouse (a 60M-row GROUP
> BY on a skewed key; a window sort with 30M rows in one partition, 19.7 s of
> task time) also reported `spill_to_disk_bytes` 0 and `network_sent_bytes` 0
> through the API. An empty result here does not mean the query is wrong: this
> workspace does not report spill or shuffle bytes.

## Monitoring through the API and CLI — `PRO-S5-O3`

```bash
databricks jobs list-runs --job-id <id> --limit 25 --active-only
databricks jobs list-runs --job-id <id> --completed-only --start-time-from <epoch-ms>
databricks jobs get-run <run-id>
databricks jobs get-run-output <task-run-id>
databricks pipelines get <pipeline-id>
databricks pipelines list-updates <pipeline-id>
databricks pipelines list-pipeline-events <pipeline-id> --filter "level='ERROR'"
```

The same calls exist as REST endpoints (`/api/2.2/jobs/runs/list`,
`/runs/get`, `/runs/get-output`, `/api/2.0/pipelines/{id}/events`). The API is
how monitoring outlives a person watching a dashboard: run durations pulled on a
schedule become a trend you can alert on, and `runs/get-output` returns a
notebook's exit value, which is how this repo's app reads a grade.
`get-run-output` takes a **task** run id; called with the id of a job run it is
refused, even for a single-task job.

## Pipeline event logs — `PRO-S5-O4`

**Pipeline event logs** record every update of a declarative pipeline: which
flows ran, how many rows each expectation dropped or flagged, and pipeline-level
errors. Query them as a table to trend data-quality counts over time rather than
reading one run's page.

```sql
-- by the dataset, or by the pipeline
SELECT * FROM event_log(TABLE(workspace.sales.orders_clean));
SELECT * FROM event_log('<pipeline-id>');

-- rows passed and failed per expectation, in the latest update
WITH latest AS (
  SELECT origin.update_id AS id
  FROM event_log('<pipeline-id>')
  WHERE event_type = 'create_update'
  ORDER BY timestamp DESC LIMIT 1
)
SELECT e.dataset, e.name,
       sum(e.passed_records) AS passed,
       sum(e.failed_records) AS failed
FROM (
  SELECT explode(from_json(
           details:flow_progress.data_quality.expectations,
           'array<struct<name: string, dataset: string,
                         passed_records: int, failed_records: int>>')) AS e
  FROM event_log('<pipeline-id>'), latest
  WHERE event_type = 'flow_progress' AND origin.update_id = latest.id
)
GROUP BY 1, 2;
```

The columns are `id`, `sequence`, `origin` (pipeline, update, flow),
`timestamp`, `message`, `level` (`INFO`, `WARN`, `ERROR`, `METRICS`),
`maturity_level`, `error`, `details` (a JSON string) and `event_type`. The
types to know: `create_update` (an update started, and why), `update_progress`
(its state changes, including `FAILED` with the error), `flow_progress` (per
flow: rows and data quality), `flow_definition`, `user_action`,
`cluster_resources` and `autoscale`.

### Reading one `flow_progress` event

```json
{
  "flow_progress": {
    "status": "COMPLETED",
    "metrics": { "num_output_rows": 3 },
    "data_quality": {
      "dropped_records": 2,
      "expectations": [
        { "name": "positive_amount", "dataset": "orders_clean",
          "passed_records": 2, "failed_records": 2 },
        { "name": "has_amount", "dataset": "orders_clean",
          "passed_records": 3, "failed_records": 1 }
      ]
    }
  }
}
```

Read it top down: the flow finished; `dropped_records` counts rows removed by
`ON VIOLATION DROP ROW` expectations; each entry in `expectations` reports
passed and failed rows for one constraint. A warn-only expectation (no `ON
VIOLATION`) still counts `failed_records` but drops nothing, which is why
`dropped_records` and the sum of `failed_records` differ. A `FAIL UPDATE`
expectation stops the update: the counts are missing and the reason is in the
`update_progress` event's `error`. The `:` path syntax works on the string
`details` column directly; `from_json` turns the array into rows.

By default only the pipeline's run-as user (and, for `event_log(TABLE(...))`,
the owner of the table) can query it. To share it, publish the event log to a
named Unity Catalog table in the pipeline settings and grant on a view:

```json
"event_log": { "catalog": "ops", "schema": "pipelines", "name": "orders_event_log" }
```

## SQL Alerts on data quality — `PRO-S5-O5`

A SQL Alert is a saved query plus a condition on its result, evaluated on a
schedule, notifying a destination when the condition holds.

```sql
-- the query behind an alert
SELECT count(*) AS breaches
FROM metrics
WHERE run_date = current_date() AND rows_processed < 880;
```

Fire when `breaches > 0`. The condition has four parts: a **column** of the
result, an **aggregation** over its rows (`SUM`, `COUNT`, `COUNT_DISTINCT`,
`AVG`, `MEDIAN`, `MIN`, `MAX`, `STDDEV`, or none, which takes the first row), an
**operator** (`>`, `>=`, `<`, `<=`, `=`, `!=`, `IS NULL`), and a **threshold**
that is either a static value (the default) or another column of the result.
Then the options:

```json
{
  "display_name": "orders: low volume",
  "query_text": "SELECT count(*) AS breaches FROM ...",
  "warehouse_id": "<warehouse-id>",
  "evaluation": {
    "source": { "name": "breaches", "aggregation": "MAX" },
    "comparison_operator": "GREATER_THAN",
    "threshold": { "value": { "double_value": 0 } },
    "empty_result_state": "OK",
    "notification": {
      "notify_on_ok": true,
      "retrigger_seconds": 3600,
      "subscriptions": [ { "destination_id": "<slack-destination-id>" } ]
    }
  },
  "schedule": {
    "quartz_cron_schedule": "0 0 6 * * ?",
    "timezone_id": "UTC",
    "pause_status": "UNPAUSED"
  }
}
```

- **Empty result state** (`OK`, `TRIGGERED` or `ERROR`) decides what a query
  returning no rows means. A data-quality alert whose source table stopped
  loading returns nothing; set it to `TRIGGERED` when silence is the problem.
- **Notify on OK** sends the "back to normal" message.
- **Retrigger** (`retrigger_seconds`) repeats the notification while the alert
  stays `TRIGGERED`; without it, you hear once.
- The **schedule** is a Quartz cron; an alert can also run as an alert task in
  a job, right after the job that loads its table.
- The notification template takes `{{ALERT_STATUS}}`, `{{ALERT_CONDITION}}`,
  `{{ALERT_THRESHOLD}}`, `{{QUERY_RESULT_VALUE}}` and `{{QUERY_RESULT_TABLE}}`.
- Alerts do not take query parameters, and each alert owns its query text
  rather than pointing at a saved query.

> **Measured on Free Edition:** through `databricks alerts-v2`, all seven
> operators and eight aggregations above were accepted, as was a threshold that
> names a column; `empty_result_state: "UNKNOWN"` was refused. A scratch alert
> was created paused and deleted again.

A **fixed threshold is honest only when the metric is stationary**. When it has
a cycle or drifts, the design rules below apply.

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
PagerDuty or a webhook, configured once as notification destinations by a
workspace admin and reused, up to three system destinations per event type.
Editing them needs `CAN MANAGE` on the job.

```yaml
# a job in a bundle (the same keys in the Jobs API JSON)
resources:
  jobs:
    nightly_orders:
      timeout_seconds: 7200                  # default 0: no timeout
      health:
        rules:
          - metric: RUN_DURATION_SECONDS     # op is always GREATER_THAN
            op: GREATER_THAN
            value: 3600
          - metric: STREAMING_BACKLOG_SECONDS
            op: GREATER_THAN
            value: 600
      email_notifications:
        on_start: []
        on_success: []
        on_failure: [data-oncall@example.com]
        on_duration_warning_threshold_exceeded: [data-oncall@example.com]
        on_streaming_backlog_exceeded: [data-oncall@example.com]
      webhook_notifications:
        on_failure:
          - id: <notification-destination-id>
      notification_settings:
        no_alert_for_skipped_runs: true      # default false
        no_alert_for_canceled_runs: true     # default false
      tasks:
        - task_key: load
          notification_settings:
            alert_on_last_attempt: true      # stay quiet through retries
```

Three distinctions the exam leans on:

- **`health` warns, `timeout_seconds` kills.** A duration rule notifies and
  lets the run finish; a timeout cancels it as `TIMED_OUT`. A duration warning
  needs a `health` rule; the notification list alone does nothing.
- **Job level vs task level.** Job-level muting does not silence task-level
  notifications, and a task retried after a failure does not fire the job-level
  failure notification until the run itself fails.
- **"Succeeded with failures" is a success.** Notify on success to hear about
  it.

> **Measured on Free Edition:** a job created with `databricks jobs create`
> stored the `health` rules and every notification key above, read back
> `timeout_seconds: 0` on the job and the task once none was set, and was given
> `queue: {"enabled": true}` and `max_concurrent_runs: 1` without asking. A
> `health` rule with `op: LESS_THAN` was refused (only `GREATER_THAN` is
> accepted). The scratch job never ran and was deleted.

## Further reading

Official documentation for what this section tests, one link per topic:

- [System tables](https://docs.databricks.com/aws/en/admin/system-tables/) — the catalogue of `system.*` schemas, retention and access.
- [Billable usage](https://docs.databricks.com/aws/en/admin/system-tables/billing) — `system.billing.usage` and `usage_metadata`.
- [Pricing system table](https://docs.databricks.com/aws/en/admin/system-tables/pricing) — `list_prices` and the price window.
- [Monitor costs with system tables](https://docs.databricks.com/aws/en/admin/usage/system-tables) — ready-made usage-to-dollars queries.
- [Audit logs](https://docs.databricks.com/aws/en/admin/system-tables/audit-logs) — `system.access.audit` actions and columns.
- [Lineage system tables](https://docs.databricks.com/aws/en/admin/system-tables/lineage) — table and column lineage.
- [Jobs system tables](https://docs.databricks.com/aws/en/admin/system-tables/jobs) — `system.lakeflow` run and task timelines.
- [Query history system table](https://docs.databricks.com/aws/en/admin/system-tables/query-history) — `system.query.history`.
- [Monitor jobs](https://docs.databricks.com/aws/en/jobs/monitor) — run history and trends.
- [Job notifications](https://docs.databricks.com/aws/en/jobs/notifications) — email, webhooks and the streaming backlog metrics.
- [Notification destinations](https://docs.databricks.com/aws/en/admin/workspace-settings/notification-destinations) — Slack, Teams, PagerDuty and webhooks set up once.
- [SQL alerts](https://docs.databricks.com/aws/en/sql/user/alerts/) — what an alert is and its states.
- [Create an alert](https://docs.databricks.com/aws/en/sql/user/alerts/create) — condition, empty result, retrigger and templates.
- [Pipeline event log](https://docs.databricks.com/aws/en/ldp/monitor-event-logs) — event types, the data quality query and publishing.
- [`event_log` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/event_log) — the table-valued function and who can call it.
- [Query profile](https://docs.databricks.com/aws/en/sql/user/queries/query-profile) — where a single query's time went.

Videos for another angle on the hard parts (channel, length):

- [Monitoring Databricks with System Tables](https://www.youtube.com/watch?v=VfqLBJvqomM) — Dustin Vannoy, 16 min. Usage and audit queries you can copy.
- [Lineage System Table in Unity Catalog](https://www.youtube.com/watch?v=bZXswjZ0avA) — Databricks, 32 min. Lineage as data.
