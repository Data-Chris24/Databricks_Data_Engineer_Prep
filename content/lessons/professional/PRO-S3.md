# Data Transformation, Cleansing and Quality — 10%

Two objectives, and the exam's angle on both is *between rows*: window functions
that compute across neighbours without collapsing them, and quality processes
that keep the evidence instead of deleting it.

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
one produces a plausible number and no error.

The patterns the exam asks for by scenario:

- **Latest record per key:** `row_number()` over the key ordered by the sequence,
  keep `rn = 1`. Not `dropDuplicates`, which keeps an arbitrary row.
- **Change from the previous row:** `lag(col)` over the key ordered by time, then
  subtract. A cumulative meter that goes backwards, a balance that jumps, a gap
  longer than the cadence are all one `lag` away.
- **Running totals and moving averages:** an aggregate over
  `rowsBetween(Window.unboundedPreceding, 0)` or a bounded frame.
- **Joins at scale:** broadcast the small side deliberately; know that a join is
  one row per matching *pair*, so a duplicate key on the dimension fans out the
  fact table without an error (the Associate S3 trap, still true here).

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
VIOLATION DROP ROW` removes it; `ON VIOLATION FAIL UPDATE` stops the pipeline.
The quarantine pattern in a pipeline is two tables from one source: the clean one
with drop-row expectations, and a quarantine table selecting the inverse
condition. With **Auto Loader in a classic job**, malformed records land in
`_rescued_data` rather than being dropped, and a bad-records path or `try_cast`
plus a split does the same job.

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
- [Adaptive query execution](https://docs.databricks.com/aws/en/optimizations/aqe) — skew joins and partition coalescing.
- [pandas function APIs](https://docs.databricks.com/aws/en/pandas/pandas-function-apis) — `applyInPandas` and grouped transformations.
- [Pipeline expectations](https://docs.databricks.com/aws/en/ldp/expectations) — warn, drop, fail and the quarantine pattern.
- [Constraints](https://docs.databricks.com/aws/en/tables/constraints) — `CHECK` at write time vs expectations in a pipeline.
- [PIVOT](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-qry-select-pivot) — long to wide.

Videos for another angle on the hard parts (channel, length):

- [Data Quality as Code: Spark Declarative Pipelines expectations](https://www.youtube.com/watch?v=CjS6ILJZP7k) — DataMindAI with Ahmed, 46 min. Expectations end to end.
- [Watermarking and handling late data in window operations](https://www.youtube.com/watch?v=_qqMqlv8rW0) — itversity, 9 min. Why a window on an irregular series needs a time frame.
