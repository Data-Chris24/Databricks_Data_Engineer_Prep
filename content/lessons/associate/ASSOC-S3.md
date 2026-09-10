# Data Transformation and Modeling — 22%

The heaviest section on the Associate exam. Most of it is joins, aggregation and the
bronze→silver→gold progression, and most of the traps are things that produce a
*wrong answer without an error*.

## Cleaning bronze into silver — `ASSOC-S3-O1`

Bronze should be faithful to the source. CSV has no types, so a bronze table loaded
from CSV is honestly all `STRING`; typing it there just makes loads fail. Cast on the
way to silver instead.

`CAST` returns `NULL` when a value will not convert — it does not raise and does not
drop the row. So a schema change upstream shows up as a quietly growing null count,
not as a failure. Count your nulls after casting; `try_cast()` makes the intent
explicit.

**Nulls have meanings.** Before filling one, ask whether it means *unknown* or
*a specific value*. A null discount that the business says means "no discount" should
become `0.0` — that records the meaning. Filling an *unknown* with a default invents
data. Same operation, opposite verdict.

## Joins — `ASSOC-S3-O2`

The exam probes join *cardinality* more than join syntax.

| Join | Keeps | Watch for |
|---|---|---|
| `INNER` | matching pairs only | silently drops unmatched rows |
| `LEFT` | all left rows, NULLs on the right | the usual choice when nothing may be lost |
| `LEFT ANTI` | left rows with **no** match | finding orphans |
| `CROSS` | every combination | almost always an accident |

**Fan-out is the one to internalise.** A join returns one row per matching *pair*. If
the dimension has two rows for a key, every fact row with that key comes back twice —
the count goes *up* and nothing errors. Slowly-changing dimensions cause this
constantly. The fix is a point-in-time join that puts the validity window in the join
condition:

```sql
ON  e.plan_id = p.plan_id
AND e.event_date >= p.valid_from
AND e.event_date <  p.valid_to
```

Note the asymmetric bounds — `>=` and `<` — so an event on a boundary date matches
exactly one version.

**Broadcast joins.** A normal join shuffles both sides so matching keys meet. If one
side is small, broadcasting it to every executor avoids shuffling the large side at
all. Automatic below `spark.sql.autoBroadcastJoinThreshold` (10 MB default); `-1`
disables it.

**`UNION` deduplicates, `UNION ALL` does not.** Deduplication means a shuffle, so
prefer `UNION ALL` and deduplicate deliberately.

## Reshaping — `ASSOC-S3-O3`

`explode()` turns each array element into its own row, carrying the parent columns —
the standard way to change grain from one-row-per-container to one-row-per-item. Use
`explode_outer()` when an empty array should still produce a row.

`split()` returns an array; index it for the parts. **Spark SQL arrays are 0-based.**

Indexing past the end **raises** `INVALID_ARRAY_INDEX` under ANSI semantics — it does
not return null — so one malformed row fails the batch. Use `get(arr, i)` when a
missing part is expected and should be null.

DataFrames are immutable. Every transformation returns a new one, and transformations
are lazy — nothing runs until an action.

## Dedup and aggregates — `ASSOC-S3-O4`

`dropDuplicates()` with no arguments compares *whole rows*, so two versions of a
record that differ anywhere are both kept. Deduplicate on the **business key**:
`dropDuplicates(["event_id"])`. When versions genuinely differ, order by an ingestion
timestamp and keep the newest rather than letting Spark pick.

`count(*)` counts rows. `count(col)` counts non-nulls. `avg()` skips nulls — so it
divides by the non-null count, and an average comes out too high if a null really
meant zero.

`approx_count_distinct()` uses HyperLogLog for a bounded error at a fraction of the
cost of an exact distinct. When the business has agreed a tolerance, paying for
exactness is choosing to be slower for nothing.

## Tuning — `ASSOC-S3-O5`

| Setting | Does | Symptom it fixes |
|---|---|---|
| `spark.sql.shuffle.partitions` | post-shuffle partition count (default 200) | hundreds of sub-second tasks = too many; long spilling tasks = too few |
| `spark.sql.autoBroadcastJoinThreshold` | auto-broadcast size limit | unnecessary shuffles, or driver OOM if too high |
| `spark.driver.memory` | driver heap | **not** the fix for `collect()` on a big result |
| `spark.executor.memory` | executor heap | spill and GC pressure |

`collect()` pulls every row to the driver. Cluster size is irrelevant — the driver is
one JVM. Write the result to a table; `collect()` is for a handful of rows.

## Gold objects — `ASSOC-S3-O6`

| Object | Computed | Choose when |
|---|---|---|
| View | every query | source changes as often as it is read |
| Materialized view | on refresh | read far more often than written |
| Streaming table | incrementally, once per row | append-oriented, continuously arriving data |

Match the object to the read/write ratio. A dashboard hitting a nightly aggregate
hundreds of times an hour should not recompute it hundreds of times.

Views are also the simplest governance boundary: select the permitted columns, grant
on the view, withhold on the table. No duplicate data, always current.

## Quality — `ASSOC-S3-O7`

A `CHECK` constraint is enforced on write — a violating row fails the transaction
rather than landing and being cleaned up later. Adding one validates existing rows,
so it fails if the table already violates it.

The strongest signal of *silent* degradation is a jump in null rate: the job still
succeeds, the row count still looks right, and the data is quietly wrong.

After a join meant to enrich without changing grain, assert the row count is
unchanged. One cheap check catches both fan-out and unintended drops.
