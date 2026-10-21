# Data Transformation, Cleansing and Quality — 10%

Two objectives, and the exam's angle on both is *between rows*: window functions
that compute across neighbours without collapsing them, and quality processes
that keep the evidence instead of deleting it.

> **Names:** Lakeflow Spark Declarative Pipelines (Delta Live Tables, DLT),
> `from pyspark import pipelines as dp` and `@dp.expect` (`import dlt` and
> `@dlt.expect`), `CREATE OR REFRESH STREAMING TABLE` (`CREATE STREAMING LIVE
> TABLE`), the `LIVE.` prefix (gone: name the dataset bare), Lakeflow Jobs
> (Workflows). Old names still appear in distractors.

## What the exam asks

- Keep only the latest row per key, in one query with no subquery — `QUALIFY row_number() OVER (...) = 1` (`PRO-S3-O1`)
- A large fact joins a small dimension and both sides shuffle — broadcast the small side with a hint or `F.broadcast` (`PRO-S3-O1`)
- One key holds most of the rows and one task runs for hours — AQE skew join for shuffle joins, salting when that is not enough (`PRO-S3-O1`)
- Subtotals per region, per region and product, and a grand total in one pass — `ROLLUP` vs `CUBE` and `grouping_id()` (`PRO-S3-O1`)
- Bad rows must be kept for review while good rows flow on — drop expectations on the clean table plus an inverse quarantine table (`PRO-S3-O2`)
- How many rows each expectation failed in the last update — `event_log()` and `details:flow_progress.data_quality` (`PRO-S3-O2`)

## Defaults and limits

| Setting | Default or limit | Note |
|---|---|---|
| `spark.sql.autoBroadcastJoinThreshold` | 10 MB | planning-time broadcast, from table statistics; `-1` disables |
| `spark.databricks.adaptive.autoBroadcastJoinThreshold` | 30 MB | AQE's runtime threshold, from the real shuffle size |
| `spark.sql.shuffle.partitions` | 200 | `auto` lets AQE pick the count |
| AQE (`spark.databricks.optimizer.adaptive.enabled`) | on | needs at least one exchange; not used for streaming queries |
| `spark.sql.adaptive.skewJoin.enabled` | true | sort merge and shuffle hash joins only, never broadcast |
| `spark.sql.adaptive.skewJoin.skewedPartitionFactor` | 5 | skewed = larger than factor × median **and** the threshold |
| `spark.sql.adaptive.skewJoin.skewedPartitionThresholdInBytes` | 256 MB | |
| `spark.sql.adaptive.advisoryPartitionSizeInBytes` | 64 MB | target size when AQE coalesces or splits |
| Window frame with `ORDER BY`, no frame given | `RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW` | ties share one value; no `ORDER BY` means the whole partition |
| Expectation with no `ON VIOLATION` | warn | row kept, violation counted |
| `ON VIOLATION FAIL UPDATE` | rolls the table update back | records no metrics, because the update fails |
| `cloudFiles.schemaEvolutionMode` | `addNewColumns`; `none` when you give a schema | `rescue` never evolves, `failOnNewColumns` stops |
| `_rescued_data` | on when Auto Loader infers the schema | with a supplied schema, set `rescuedDataColumn` yourself |
| `mode` (JSON, CSV) | `PERMISSIVE` | `DROPMALFORMED` drops, `FAILFAST` raises |
| `columnNameOfCorruptRecord` | `_corrupt_record` | only filled if the column is in the schema |
| `cloudFiles.inferColumnTypes` | false | JSON and CSV columns infer as strings |

## Advanced transformations — `PRO-S3-O1`

A `groupBy` collapses rows; a **window** computes across rows and keeps them.

| Function | Gives you |
|---|---|
| `lag` / `lead` | the neighbouring row's value |
| `row_number` | position in the ordered partition (ties broken arbitrarily) |
| `rank` / `dense_rank` | position with ties kept, with or without gaps |
| an aggregate `over` a frame | a rolling calculation |

**Frames are where the quiet bugs live.** `rowsBetween` counts *rows*;
`rangeBetween` counts *values of the ordering column*. On an irregular time series
they differ sharply: five rows back is not five minutes back. Choosing the wrong
one produces a plausible number and no error. Leaving the frame out is a choice
too: with an `ORDER BY` the default is a `RANGE` frame, so rows that tie on the
ordering column get the same running total.

```sql
SELECT device_id, read_ts, value,
       value - lag(value) OVER (PARTITION BY device_id ORDER BY read_ts) AS delta,
       avg(value) OVER (PARTITION BY device_id ORDER BY read_ts
                        ROWS BETWEEN 4 PRECEDING AND CURRENT ROW)       AS avg_last_5_rows,
       avg(value) OVER (PARTITION BY device_id ORDER BY read_ts
                        RANGE BETWEEN INTERVAL 10 MINUTES PRECEDING
                                  AND CURRENT ROW)                      AS avg_last_10_min
FROM readings;
-- Python: w = Window.partitionBy("device_id").orderBy("read_ts")
--         w.rowsBetween(-4, Window.currentRow)
--         w.rangeBetween(Window.unboundedPreceding, Window.currentRow)
```

A named `WINDOW w AS (...)` clause works for `OVER w`, but `OVER (w ROWS ...)`
is a syntax error: the frame goes in the full specification.

> **Measured on Free Edition:** with rows at 00:00, 00:05 and 01:00, the 01:00
> row's five-row average was 3.0 and its ten-minute average was 5.0 (only itself).
> `sum(v) OVER (ORDER BY t)` over `t` = 1, 2, 2, 3 gave 10, 60, 60, 100: the two
> tied rows share the `RANGE` default, where a `ROWS` frame gave 30 then 60.

`QUALIFY` filters on a window function the way `HAVING` filters on an aggregate,
so the latest-row pattern needs no subquery:

```sql
SELECT * FROM readings
QUALIFY row_number() OVER (PARTITION BY device_id ORDER BY read_ts DESC) = 1;
```

The patterns the exam asks for by scenario:

- **Latest record per key:** `row_number()` over the key ordered by the sequence,
  keep `rn = 1` (or `QUALIFY ... = 1`). Not `dropDuplicates`, which keeps an
  arbitrary row.
- **Change from the previous row:** `lag(col)` over the key ordered by time, then
  subtract. A cumulative meter that goes backwards, a balance that jumps, a gap
  longer than the cadence are all one `lag` away.
- **Running totals and moving averages:** an aggregate over
  `rowsBetween(Window.unboundedPreceding, 0)` or a bounded frame.
- **Joins at scale:** broadcast the small side deliberately; know that a join is
  one row per matching *pair*, so a duplicate key on the dimension fans out the
  fact table without an error (the Associate S3 trap, still true here).

### Which join will Spark pick

For an equi-join with no hint, Spark broadcasts a side whose estimated size is
under `autoBroadcastJoinThreshold` (10 MB), and otherwise shuffles both sides
into a **sort merge join**. AQE can still turn a sort merge join into a broadcast
at run time once a side turns out to be under 30 MB. A join with no equality
condition (`a.k > b.k`) can only be a **broadcast nested loop** or a cartesian
product. Hints override the size rule:

| Hint (aliases) | Strategy | Shuffles |
|---|---|---|
| `BROADCAST` (`BROADCASTJOIN`, `MAPJOIN`) | broadcast hash join | neither side |
| `MERGE` (`SHUFFLE_MERGE`, `MERGEJOIN`) | sort merge join | both, then sorts |
| `SHUFFLE_HASH` | shuffled hash join | both, no sort |
| `SHUFFLE_REPLICATE_NL` | nested loop over a cartesian product | replicates |

```sql
SELECT /*+ BROADCAST(d) */ f.*, d.name
FROM facts f JOIN dims d ON f.k = d.k;
-- Python: facts.join(F.broadcast(dims), "k")   or   dims.hint("broadcast")
--         facts.hint("merge"), dims.hint("shuffle_hash")
```

Three rules settle most "which plan" questions:

1. **Priority.** Different hints on the two sides resolve as `BROADCAST` over
   `MERGE` over `SHUFFLE_HASH` over `SHUFFLE_REPLICATE_NL`.
2. **A hint is a request.** The side that must be preserved in an outer join
   cannot be the broadcast side: a left join can broadcast only the right side,
   and a full outer join cannot broadcast at all. Spark picks another plan and
   raises no error.
3. **Read the plan, not the hint.** `EXPLAIN` shows `BroadcastHashJoin ...
   BuildRight` or `SortMergeJoin`; the build side is the one broadcast.

> **Measured on Free Edition:** on the serverless SQL warehouse, `EXPLAIN` of a
> 1,000,000-row table joined to a 100-row one gave `PhotonBroadcastHashJoin`
> with no hint; `MERGE` gave `SortMergeJoin`, `SHUFFLE_HASH` gave
> `PhotonShuffledHashJoin`, `SHUFFLE_REPLICATE_NL` gave `CartesianProduct`, and
> a non-equi condition gave `PhotonBroadcastNestedLoopJoin`. `BROADCAST(a), MERGE(b)`
> broadcast `a`. `BROADCAST` on the left side of a `LEFT JOIN` was ignored (the
> plan built the right side) and `BROADCAST` on a `FULL OUTER JOIN` produced a
> shuffled hash join. A sort merge join is not supported by Photon: the plan
> explanation says so and that stage falls back to Spark. The warehouse also
> refuses `SET` on the join and AQE settings above (`CONFIG_NOT_AVAILABLE`), so
> on Free Edition hints are the lever you have.

### Skew: AQE first, salting second

A skewed key puts most of a shuffle into one partition, so one task runs long
while the rest sit idle. **AQE's skew join** splits a partition that is both more
than 5 × the median and over 256 MB, and replicates the matching partition on the
other side. It works only on shuffle joins (sort merge, shuffle hash), and only
on the side that is not preserved by an outer join: either side of an inner join,
the left side of a left join, neither side of a full outer join. A broadcast join
has no shuffle to be skewed.

When AQE cannot help (a full outer join, a skewed aggregation, a hot key so large
that even split partitions are slow), **salt** the key: spread the hot key over
*n* random values on the big side and replicate each row of the small side *n*
times so every pair still meets.

```sql
WITH f AS (SELECT *, CAST(floor(rand() * 8) AS INT) AS salt FROM facts),
     d AS (SELECT dims.*, s.salt
           FROM dims CROSS JOIN (SELECT explode(sequence(0, 7)) AS salt) s)
SELECT * FROM f JOIN d ON f.k = d.k AND f.salt = d.salt;
```

The cost is *n* copies of the small side, so salt only the hot keys when the
dimension is not small. The older `/*+ SKEW('table') */` hint still parses but
AQE replaced it; reach for the setting before the hint.

> **Measured on Free Edition:** the salted join above, on 1,000 fact rows where
> 900 share one key, returned exactly 1,000 rows, the same as the unsalted join.
> `/*+ SKEW('a') */` was accepted with no error and no change to the plan.

### Aggregations: `ROLLUP`, `CUBE`, `GROUPING SETS`

All three compute several `GROUP BY`s in one pass and mark the rolled-up columns
`NULL`:

| Clause | Groups for `(region, product)` |
|---|---|
| `ROLLUP (region, product)` | `(region, product)`, `(region)`, `()`: the hierarchy, left to right |
| `CUBE (region, product)` | every combination: also `(product)` |
| `GROUPING SETS ((region), (product), ())` | exactly the sets listed |

```sql
SELECT region, product, sum(amount) AS total,
       grouping_id() AS gid          -- bit per column, 1 = rolled up
FROM sales
GROUP BY ROLLUP (region, product);
-- Python: sales.rollup("region", "product").agg(F.sum("amount"), F.grouping_id())
--         sales.cube("region", "product")...
```

A real `NULL` in the data and a subtotal `NULL` look the same; `grouping(col)` or
`grouping_id()` tells them apart. The last column listed is the lowest bit, so
for `ROLLUP (region, product)` detail rows are 0, region subtotals 1 and the
grand total 3.

> **Measured on Free Edition:** on three rows (two regions, two products),
> `ROLLUP` returned 6 rows with `grouping_id()` 0, 1 and 3, `CUBE` returned 8,
> and `GROUPING SETS ((r), (c), ())` returned 5.

### Higher-order functions

Arrays get their own operators, so you do not `explode` and regroup to change
every element:

| Function | Does |
|---|---|
| `transform(arr, x -> ...)` | maps every element |
| `filter(arr, x -> ...)` | keeps matching elements |
| `exists(arr, x -> ...)` / `forall(arr, x -> ...)` | any / every element matches |
| `aggregate(arr, start, (acc, x) -> ...)` (alias `reduce`) | folds to one value |

```sql
SELECT transform(readings, r -> r * 1.8 + 32)    AS fahrenheit,
       filter(readings, r -> r IS NOT NULL)       AS present,
       exists(readings, r -> r < 0)               AS any_negative,
       aggregate(readings, 0D, (acc, r) -> acc + r) AS total
FROM sensor_batches;
-- Python: F.transform("readings", lambda r: r * 1.8 + 32), F.filter, F.exists,
--         F.forall, F.aggregate
```

`explode` turns one row into many; the higher-order functions keep the row and
are what the exam means by an efficient array transformation. `aggregate` is
plain SQL arithmetic, so one `NULL` element makes the result `NULL`: filter first.

> **Measured on Free Edition:** on `array(10.0, -1.0, NULL)`, `transform` kept
> the `NULL` in place, `filter(... IS NOT NULL)` returned two elements, `exists(... < 0)`
> was true and `aggregate` returned `NULL`.

## Quarantining bad data — `PRO-S3-O2`

Filtering bad rows away loses the evidence. **Quarantine** keeps it somewhere a
human can look, and lets the good data flow on, so neither blocks the other. Two
rules make a quarantine useful:

1. **Keep the raw values.** A quarantine row that has already been through the
   transformation you are debugging is not evidence. `try_cast` decides good from
   bad without raising; the original strings ride along.
2. **Record why.** A `reason` or the source file turns a pile of rejects into a
   list of things to fix upstream.

In a **declarative pipeline** the same idea is an expectation:

```sql
CONSTRAINT valid_reading EXPECT (reading >= 0) ON VIOLATION DROP ROW
```

`EXPECT` alone records violations in the event log and keeps the row; `ON
VIOLATION DROP ROW` removes it; `ON VIOLATION FAIL UPDATE` stops the update.
The quarantine pattern in a pipeline is two tables from one source: the clean one
with drop-row expectations, and a quarantine table selecting the inverse
condition. With **Auto Loader in a classic job**, values that do not fit the
schema land in `_rescued_data` rather than being dropped, a line that does not
parse at all needs `_corrupt_record`, and a bad-records path or `try_cast` plus a
split does the same job.

### Expectation semantics side by side

| | Warn | Drop | Fail |
|---|---|---|---|
| SQL | `EXPECT (cond)` | `... ON VIOLATION DROP ROW` | `... ON VIOLATION FAIL UPDATE` |
| Python, one rule | `@dp.expect(name, cond)` | `@dp.expect_or_drop(name, cond)` | `@dp.expect_or_fail(name, cond)` |
| Python, a dict of rules | `@dp.expect_all({...})` | `@dp.expect_all_or_drop({...})` | `@dp.expect_all_or_fail({...})` |
| Violating row | written | not written | update stops; table update rolled back |
| Metrics in the event log | passed and failed per rule | passed and failed per rule, plus dropped | none, the update failed |
| Other flows | carry on | carry on | in a triggered pipeline, parallel flows still finish |

The condition is a SQL boolean string, with no Python UDFs or subqueries.
Decorators stack, so one table can drop on one rule and fail on another.
Expectations act per row: a rule that needs two rows (a uniqueness check, a
count comparison) goes on a materialized view that aggregates first, with an
`expect_or_fail` on the aggregate.

```python
from pyspark import pipelines as dp
from pyspark.sql import functions as F

RULES = {"has_device": "device_id IS NOT NULL",
         "non_negative": "reading_num >= 0"}
QUARANTINE = "NOT ({})".format(" AND ".join(f"({c})" for c in RULES.values()))

@dp.table()
@dp.expect_all_or_drop(RULES)
def readings_clean():
    return spark.readStream.table("readings_typed")

@dp.table()
def readings_quarantine():
    return (spark.readStream.table("readings_typed")
            .filter(f"coalesce({QUARANTINE}, true)"))   # NULL counts as bad
```

`NOT (cond)` is `NULL` when the condition is `NULL`, and a `filter` drops `NULL`,
so without the `coalesce` a row whose value failed to cast falls out of both
tables. The docs' version of the pattern writes one table with an
`is_quarantined` column and two views over it; either way, the rules live in one
dict so the clean and quarantine sides cannot drift apart.

### Reading expectation metrics

Every flow writes `flow_progress` events to the pipeline's **event log**; the
expectation counts sit in the JSON `details` column.

```sql
SELECT e.dataset, e.name,
       sum(e.passed_records) AS passed, sum(e.failed_records) AS failed
FROM (
  SELECT explode(from_json(details:flow_progress:data_quality:expectations,
           'array<struct<name:string, dataset:string,
                         passed_records:bigint, failed_records:bigint>>')) AS e
  FROM event_log('<pipeline-id>')          -- or event_log(TABLE(catalog.schema.table))
  WHERE event_type = 'flow_progress'
) GROUP BY e.dataset, e.name;
-- dropped rows: details:flow_progress:data_quality:dropped_records
```

`dropped_records` is one number per flow, not per rule; the per-rule array has
only passed and failed counts. Metrics exist for streaming tables, materialized
views and temporary views, not for sinks, and not for a flow run that wrote
nothing. A fail expectation leaves no metrics, only the error event.

> **Measured on Free Edition:** the `coalesce` matters: on the SQL warehouse,
> `WHERE NOT (x >= 0)` returned 0 rows for a `NULL` `x` and `WHERE coalesce(NOT
> (x >= 0), true)` returned 1.

### Auto Loader without a pipeline

In a classic job, Auto Loader's options do the sorting:

```python
(spark.readStream.format("cloudFiles")
   .option("cloudFiles.format", "json")
   .option("cloudFiles.schemaLocation", checkpoint + "/schema")
   .schema("id INT, reading DOUBLE")
   .option("rescuedDataColumn", "_rescued_data")   # not added for you once you give a schema
   .option("cloudFiles.schemaEvolutionMode", "rescue")
   .load(source))
# reader modes: mode = PERMISSIVE (default) | DROPMALFORMED | FAILFAST
#               columnNameOfCorruptRecord = _corrupt_record, badRecordsPath = <path>
```

| Option | Catches | Row |
|---|---|---|
| `_rescued_data` | a value of the wrong type, a column not in the schema, a column in a different case | kept; the field is `NULL` and the original goes into the JSON blob with `_file_path` |
| `_corrupt_record` (in the schema) | a line that does not parse at all | kept, every field `NULL`, the raw line in the column |
| `badRecordsPath` | both | removed from the result and written to the path with the exception; not transactional |
| `mode => 'DROPMALFORMED'` | both | removed, no trace |

> **Measured on Free Edition:** `read_files` over one JSON file with a good row,
> `"reading":"abc"` for a `DOUBLE`, an extra `Extra` column and the line `{bad
> json`. With a supplied schema and **no** `rescuedDataColumn`, `abc` became a
> silent `NULL` and the extra column vanished. With `rescuedDataColumn`, the
> blob held `{"reading":"abc","_file_path":...}` and `{"Extra":"x",...}`, but the
> unparseable line came back as an all-`NULL` row with an empty `_rescued_data`;
> only adding `_corrupt_record STRING` to the schema kept the line. `badRecordsPath`
> returned the two good rows and wrote the other two, each with its exception
> class, under `<path>/bad_records/`. `DROPMALFORMED` returned the same two rows
> with nothing written, and `FAILFAST` raised
> `MALFORMED_RECORD_IN_PARSING.CANNOT_PARSE_STRING_AS_DATATYPE`.

**Row-level rules are not the whole story.** Every rule above checks one row at a
time. A dataset where every value casts, nothing is null and nothing is negative
can still be wrong *between* rows: a cumulative value that decreases, a 15-minute
cadence with a gap, two readings at the same instant. Those are window checks,
and they are what this section's assignment is about.

## Further reading

Official documentation for what this section tests, one link per topic:

- [Transform data](https://docs.databricks.com/aws/en/transform/) — the transformation overview.
- [Window functions](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-window-functions) — frames, `rowsBetween` vs `rangeBetween`.
- [window function (time windows)](https://docs.databricks.com/aws/en/sql/language-manual/functions/window) — tumbling and sliding windows over event time.
- [QUALIFY clause](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-qry-select-qualify) — filtering on a window function.
- [Hints](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-qry-select-hints) — join and partitioning hints, their aliases and priority.
- [Adaptive query execution](https://docs.databricks.com/aws/en/optimizations/aqe) — skew joins, runtime broadcast and partition coalescing.
- [GROUP BY clause](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-qry-select-groupby) — `ROLLUP`, `CUBE` and `GROUPING SETS`.
- [Lambda functions](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-lambda-functions) — the syntax `transform`, `filter` and `aggregate` take.
- [pandas function APIs](https://docs.databricks.com/aws/en/pandas/pandas-function-apis) — `applyInPandas` and grouped transformations.
- [Pipeline expectations](https://docs.databricks.com/aws/en/ldp/expectations) — warn, drop, fail and the quarantine pattern.
- [Expectation patterns](https://docs.databricks.com/aws/en/ldp/expectation-patterns) — quarantine, row-count and primary-key checks.
- [Pipeline event log](https://docs.databricks.com/aws/en/ldp/monitor-event-logs) — `event_log()` and the data quality query.
- [Auto Loader schema inference and evolution](https://docs.databricks.com/aws/en/ingestion/cloud-object-storage/auto-loader/schema) — evolution modes and the rescued data column.
- [Constraints](https://docs.databricks.com/aws/en/tables/constraints) — `CHECK` at write time vs expectations in a pipeline.
- [PIVOT](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-qry-select-pivot) — long to wide.

Videos for another angle on the hard parts (channel, length):

- [Data Quality as Code: Spark Declarative Pipelines expectations](https://www.youtube.com/watch?v=CjS6ILJZP7k) — DataMindAI with Ahmed, 46 min. Expectations end to end.
- [Watermarking and handling late data in window operations](https://www.youtube.com/watch?v=_qqMqlv8rW0) — itversity, 9 min. Why a window on an irregular series needs a time frame.
