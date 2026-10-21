# Structured Streaming in depth

**Objectives:** `PRO-S1-O4`, `PRO-S1-O8`

The Professional exam assumes you can run a stream by hand: pick its trigger and
output mode, bound its state with a watermark, join two streams, and say what
the checkpoint holds and when it has to be thrown away. Declarative pipelines
manage most of this for you, which is why a question that offers a pipeline as
the answer usually also tests whether you know what it is managing.

## Triggers

The trigger decides *when* a micro-batch runs, not what it reads.

```python
q = (df.writeStream
       .option("checkpointLocation", "/Volumes/main/chk/orders")
       .trigger(availableNow=True)            # everything available now, in rate-limited batches, then stop
       # .trigger(processingTime="1 minute")  # a batch every minute, forever
       # .trigger(once=True)                  # deprecated: one batch, ignores rate limits
       # .trigger(realTime="5 minutes")       # real-time mode, low latency, long-running batches
       .toTable("main.silver.orders"))
```

| Trigger | Runs | Stops |
|---|---|---|
| none set (default) | next micro-batch as soon as the last ends (`processingTime` 0) | never |
| `processingTime="1 minute"` | one micro-batch per interval | never |
| `availableNow=True` | all data available at start, split by `maxFilesPerTrigger` / `maxOffsetsPerTrigger` | when caught up |
| `once=True` | one batch with everything, rate limits ignored | after it; deprecated in favour of `availableNow` |
| `continuous=...` | Spark's continuous processing | not supported on Databricks; use real-time mode |

`availableNow` is how a stream runs on a schedule: a job starts it, it catches
up, it stops, and the checkpoint carries the position to the next run.

> **Measured on Free Edition:** on serverless, the default trigger and
> `processingTime` both failed with `INFINITE_STREAMING_TRIGGER_NOT_SUPPORTED`
> ("Trigger type ProcessingTime is not supported for this cluster type"), and so did
> `continuous`. `availableNow` and `once` ran. Pipelines are not bound by this.

## Output modes

| Mode | Writes each batch | Allowed with |
|---|---|---|
| `append` (default) | only new rows that will never change | no aggregation, or an aggregation **with** a watermark |
| `update` | rows that changed in this batch | aggregations; not every sink supports it (Delta needs `foreachBatch` + `MERGE`) |
| `complete` | the whole result table, every batch | aggregations only |

```python
(events.withWatermark("event_time", "10 minutes")
    .groupBy(F.window("event_time", "5 minutes"), "device")
    .count()
    .writeStream.outputMode("append")      # a window is written once, when it is final
    .option("checkpointLocation", "/Volumes/main/chk/device_counts")
    .toTable("main.gold.device_counts"))
```

Append with an aggregation emits a window only when the watermark has passed the
window's end, because only then can no late row change it. That is why an
aggregation in append mode looks "stuck": nothing is written until event time
moves on.

> **Measured on Free Edition:** an aggregation in `append` without a watermark
> failed with `STREAMING_OUTPUT_MODE.UNSUPPORTED_OPERATION`; with a watermark it ran.
> `complete` without an aggregation failed with the same error class. `update` into
> a Delta table failed with `DELTA_UNSUPPORTED_OUTPUT_MODE`: the Delta sink takes
> `append` and `complete` only.

## Watermarks, worked

`withWatermark("event_time", "10 minutes")` sets

> watermark = (latest event time seen so far) − 10 minutes

and the watermark is recomputed at the end of each micro-batch, so it applies to
the *next* one. A row whose event time is older than the watermark is late: it
may be dropped, and the state for windows that end before the watermark is
discarded. "May" is the docs' word; Spark guarantees not to drop rows newer than
the watermark, not to drop every row older than it.

Five-minute tumbling windows, a ten-minute watermark, append mode, three
micro-batches:

| Batch | Rows arrive (event time) | Watermark during batch | Outcome | Written |
|---|---|---|---|---|
| 1 | 12:20 | none yet | window [12:20, 12:25) opened; watermark becomes 12:20 − 10 min = 12:10 | nothing |
| 2 | 12:05, 12:15 | 12:10 | 12:05 is older than the watermark: dropped. 12:15 opens [12:15, 12:20) | nothing: both windows end after 12:10 |
| 3 | 12:31 | 12:10, then 12:21 | watermark becomes 12:31 − 10 min = 12:21, past the end of [12:15, 12:20) | [12:15, 12:20) with count 1 |

[12:20, 12:25) is still open after batch 3 and needs an event at 12:35 or later.
Batch 3's window is written in a *no-data batch*: when the watermark moves,
Spark runs one more batch with no input to evict and emit what has closed.

With several input streams, each has its own watermark and the query uses the
**minimum** by default (`spark.sql.streaming.multipleWatermarkPolicy=min`), so the
slowest stream holds state back; `max` drops more late data from the slower one.

> **Measured on Free Edition:** the table above is a real run, one `availableNow`
> run per batch on serverless. Batch 2 reported `numRowsDroppedByWatermark` 1, and
> each run that moved the watermark ended with an extra batch of 0 input rows in
> which the watermark changed (12:10 after the first run, 12:21 after the third)
> and, in the third, the closed window was written.

Step through a longer run below. Set the delay, switch between append and
update, and watch which rows are dropped, what is written each batch and which
windows are still held in state.

![Micro-batches against an event-time axis: the watermark, late rows, and when each window is written and released](visual:watermark-timeline?h=720)

For a windowed aggregation, "late" is decided per window: a row is dropped only
when the window it falls in has already ended at the watermark. A row slightly
older than the watermark whose window is still open is counted. With sliding
windows a row can be dropped from one window and counted in another.

> **Measured on Free Edition:** the diagram's rows, one `availableNow` run per
> batch, 10-minute delay. With the watermark at 12:04, a row at 12:03 was counted
> in [12:00, 12:05) and not dropped; at 12:23, a row at 12:22 was counted and one
> at 12:19 was dropped (`numRowsDroppedByWatermark` 1). A row at 12:12 arriving in
> the same batch as 12:33 was counted, because that batch ran under the previous
> watermark (12:11). Every run that moved the watermark ended with a no-data
> batch, including runs where no window closed. Update mode wrote each changed
> window in its data batch and nothing in the no-data batches. With 10-minute
> windows sliding every 5, the 12:19 row was dropped from [12:10, 12:20) and
> counted in [12:15, 12:25).

## Stateful operations

Anything that remembers across batches keeps state in the checkpoint: streaming
aggregations, `dropDuplicates`, stream-stream joins, and arbitrary stateful
operators (`transformWithState`, and the older `applyInPandasWithState`). Without
a watermark that state grows forever.

```python
(events.withWatermark("event_time", "1 hour")
    .dropDuplicatesWithinWatermark(["event_id"]))    # state for event_id kept for about an hour
```

`dropDuplicates(["event_id"])` alone deduplicates over the whole stream and keeps
every key it has ever seen. Include the event-time column in the key, or use
`dropDuplicatesWithinWatermark`, to bound it.

## Stream-stream joins

| Join | Watermark and time-range condition |
|---|---|
| inner | optional; without them state is never cleaned up |
| left outer | required on the **right** side, plus a time-range condition |
| right outer | required on the **left** side, plus a time-range condition |
| full outer | required on at least one side, plus a time-range condition |
| left semi | as left outer |

```python
imps = impressions.withWatermark("imp_time", "2 hours")
clks = clicks.withWatermark("click_time", "3 hours")

imps.join(
    clks,
    F.expr("""
        click_ad_id = imp_ad_id AND
        click_time BETWEEN imp_time AND imp_time + INTERVAL 1 HOUR
    """),
    "left_outer",            # an unmatched impression is written with NULLs once the watermark passes
)
```

The outer row for an impression with no click is only written once the watermark
guarantees no click can still arrive, so outer results are late by design. A
stream-static join (stream joined to a Delta table) holds no state: each batch
reads the table's latest version.

> **Measured on Free Edition:** an inner stream-stream join on the key alone ran. A
> left outer join on the key alone failed ("not supported without a watermark in
> the join keys, or a watermark on the nullable side and an appropriate range
> condition"); with watermarks and a `BETWEEN` range it ran.

## What the checkpoint holds, and when to reset it

A checkpoint folder holds `offsets/` (what each batch will read, written before
the batch), `commits/` (batches finished), `metadata` (the query id), `sources/`
and `state/` (the state store). On restart the query resumes after the last
commit, which is where exactly-once comes from. One checkpoint per query, never
shared.

| Change | Same checkpoint? |
|---|---|
| add or remove a filter, change a projection in a stateless query | yes |
| change the trigger or its interval | yes |
| change `maxFilesPerTrigger` / `maxOffsetsPerTrigger` | yes |
| change the number or type of sources, a Kafka topic or an Auto Loader path | **no** |
| change grouping keys, aggregates or another stateful operator's schema | **no** |
| change the output sink type, or a file sink's path | **no** |
| change `spark.sql.shuffle.partitions` | ignored for a stateful query: the count is fixed when the checkpoint is created |

Resetting means a new checkpoint location and a decision about where to start
reading (the whole source again, or a starting version or timestamp), because the
old position is lost with it. In a pipeline the same reset is a **full refresh**
of that table.

> **Measured on Free Edition:** changing `groupBy("k")` to `groupBy("id")` on the
> same checkpoint failed with `STATE_STORE_KEY_SCHEMA_NOT_COMPATIBLE.FIELD_REMOVED`.
> Adding a `filter` to a stateless stream on the same checkpoint ran and picked up
> where it left off. `spark.sql.shuffle.partitions` on serverless read back as
> `auto` rather than 200. Dropping and re-creating the *source* table under the same name
> failed with `DIFFERENT_DELTA_TABLE_READ_BY_STREAMING_SOURCE`: the checkpoint
> records the table id, not its name.

## Exactly-once, end to end

Exactly-once needs three things together: a **replayable source** (Delta, Kafka,
files through Auto Loader), the **checkpoint**, and an **idempotent sink**. The
Delta sink is idempotent on its own. `foreachBatch` is not: it gives at-least-once,
and a batch replayed after a failure runs your function again.

```python
def upsert(batch_df, batch_id):
    batch_df.createOrReplaceTempView("updates")
    batch_df.sparkSession.sql("""
        MERGE INTO main.silver.customers t
        USING updates s ON t.id = s.id
        WHEN MATCHED THEN UPDATE SET *
        WHEN NOT MATCHED THEN INSERT *
    """)                                                   # MERGE is idempotent by key
    (batch_df.write.format("delta")
        .option("txnAppId", "customers_audit")             # a stable id for this query
        .option("txnVersion", batch_id)                    # Delta skips a (txnAppId, txnVersion) it has seen
        .mode("append")
        .saveAsTable("main.audit.customer_changes"))       # a plain append made idempotent

(stream.writeStream
    .foreachBatch(upsert)
    .option("checkpointLocation", "/Volumes/main/chk/customers")
    .start())
```

Each write inside `foreachBatch` that appends needs its own `txnAppId` and
`txnVersion = batch_id`. A `MERGE` keyed on the business key is already safe to
repeat; an append is not.

> **Measured on Free Edition:** appending the same one-row DataFrame twice with
> `txnAppId = "app1"`, `txnVersion = 5` left one row; `txnVersion = 4` afterwards was
> also skipped (Delta skips any version not above the last one for that app id);
> `txnVersion = 6` appended.

## Further reading

- [Triggers](https://docs.databricks.com/aws/en/structured-streaming/triggers) — every trigger, and what serverless supports.
- [Output modes](https://docs.databricks.com/aws/en/structured-streaming/output-mode) — append, update and complete.
- [Watermarks](https://docs.databricks.com/aws/en/structured-streaming/watermarks) — late data, state cleanup and multiple watermarks.
- [Stateful streaming](https://docs.databricks.com/aws/en/structured-streaming/stateful-streaming) — state stores and shuffle partitions.
- [Stream-stream joins (Spark guide)](https://spark.apache.org/docs/latest/streaming/apis-on-dataframes-and-datasets.html) — watermark rules per join type.
- [Checkpoints](https://docs.databricks.com/aws/en/structured-streaming/checkpoints) — contents and the changes that need a new one.
- [foreachBatch](https://docs.databricks.com/aws/en/structured-streaming/foreach) — `txnAppId` / `txnVersion` idempotent writes.
- [Serverless compute limitations](https://docs.databricks.com/aws/en/compute/serverless/limitations) — the triggers serverless refuses.
