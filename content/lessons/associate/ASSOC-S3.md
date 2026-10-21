# Data Transformation and Modeling — 22%

The heaviest section on the Associate exam. Most of it is joins, aggregation and the
bronze→silver→gold progression, and most of the traps are things that produce a
*wrong answer without an error*.

> **Names:** Lakeflow Spark Declarative Pipelines (Delta Live Tables, DLT), `from pyspark import pipelines as dp` with `@dp.expect` (`import dlt` with `@dlt.expect`), `CREATE STREAMING TABLE` (`CREATE STREAMING LIVE TABLE`), `CREATE MATERIALIZED VIEW` (`CREATE LIVE TABLE`), the `LIVE.` prefix is gone

## What the exam asks

- A bronze string column holds `'12 units'` and the cast to `INT` must not fail the job — ANSI mode raises, `try_cast` returns NULL (`ASSOC-S3-O1`)
- Orders joined to a customer dimension come back with more rows than there are orders — fan-out from two versions of one key (`ASSOC-S3-O2`)
- Find the customers who have never placed an order — `LEFT ANTI JOIN`, not `NOT IN` or an inner join (`ASSOC-S3-O2`)
- Keep only the newest record per `customer_id` — `row_number()` over a window, filtered to 1 (`ASSOC-S3-O4`)
- A dashboard reads a nightly aggregate hundreds of times an hour — a materialized view, not a view (`ASSOC-S3-O6`)
- Bad rows must stop the write in one table and be dropped with a metric in another — `CHECK` constraint vs pipeline expectation (`ASSOC-S3-O7`)

## Defaults and limits

| Setting | Default or limit | Note |
|---|---|---|
| `spark.sql.ansi.enabled` / `ANSI_MODE` | `true` | Databricks Runtime 17.0+, Spark 4, serverless and SQL warehouses |
| `spark.sql.shuffle.partitions` | `200` (`auto` on serverless) | `auto` turns on auto-optimized shuffle; AQE coalesces below the setting |
| `spark.sql.autoBroadcastJoinThreshold` | 10 MB (`10485760`) | `-1` disables automatic broadcast |
| `spark.databricks.adaptive.autoBroadcastJoinThreshold` | 30 MB | AQE's runtime switch from sort-merge to broadcast |
| `spark.sql.adaptive.enabled` | `true` | since Spark 3.2 |
| `spark.sql.broadcastTimeout` | 300 s | how long a broadcast may take before the join fails |
| `spark.default.parallelism` | total executor cores (at least 2) | RDD operations only; DataFrame shuffles use `shuffle.partitions` |
| `spark.driver.memory`, `spark.executor.memory` | sized from the node type | fixed at cluster start, not settable in a running session |
| `na.drop()` | `how='any'` | `how='all'`, `thresh=n` (overrides `how`), `subset=[...]` |
| `approx_count_distinct(col, rsd)` | `rsd` = 0.05 | maximum relative standard deviation |
| `summary()` statistics | count, mean, stddev, min, 25%, 50%, 75%, max | `describe()` is the same without the percentiles |
| Array index | `element_at` 1-based; `arr[i]` and `get` 0-based | `element_at(arr, 0)` raises `INVALID_INDEX_OF_ZERO`; negative counts from the end |
| `SCHEDULE EVERY n` | 1–72 `HOURS`, 1–31 `DAYS`, 1–8 `WEEKS` | `SCHEDULE CRON` takes a six-field Quartz expression |
| `TRIGGER ON UPDATE AT MOST EVERY` | 1 minute minimum | at most 10 upstream sources per materialized view |
| `REFRESH` | `SYNC` | `ASYNC` returns at once; `FULL` recomputes (truncates a streaming table) |
| Expectation without `ON VIOLATION` | warn | the row is kept and counted in the event log |
| Informational key | `NORELY` | `RELY` lets the optimizer trust a key nobody enforces |

## Cleaning bronze into silver — `ASSOC-S3-O1`

Bronze should be faithful to the source. CSV has no types, so a bronze table loaded
from CSV is honestly all `STRING`; typing it there just makes loads fail. Cast on the
way to silver instead.

What `CAST` does with a value that will not convert depends on ANSI mode. With ANSI
on (the default on serverless compute and Spark 4) it raises `CAST_INVALID_INPUT` and
the write fails; with ANSI off it returns `NULL` and the row survives, so a schema
change upstream shows up as a quietly growing null count. `try_cast()` returns `NULL`
in both modes and states the intent. Either way, count your nulls after casting.

**ANSI mode, expression by expression.** Each error message names its own way out,
which is how the exam phrases the right answer:

| Expression | ANSI on (default) | ANSI off | Tolerant form |
|---|---|---|---|
| `CAST('12 units' AS INT)` | `CAST_INVALID_INPUT` | `NULL` | `try_cast('12 units' AS INT)` |
| `1 / 0` | `DIVIDE_BY_ZERO` | `NULL` | `try_divide(1, 0)` |
| `2147483647 + 1` | `ARITHMETIC_OVERFLOW` | `-2147483648` (wraps) | `try_add`, `try_subtract`, `try_multiply` |
| `to_date('2026-13-45')` | `CAST_INVALID_INPUT` | `NULL` | `try_to_date`, `try_to_timestamp` |
| `element_at(array(1, 2), 5)` | `INVALID_ARRAY_INDEX_IN_ELEMENT_AT` | `NULL` | `try_element_at` |
| `array(1, 2)[5]` | `INVALID_ARRAY_INDEX` | `NULL` | `get(array(1, 2), 5)` |
| `sum(x)` overflowing `BIGINT` | `ARITHMETIC_OVERFLOW` | wraps | `try_sum`, `try_avg` |

> **Measured on Free Edition:** every ANSI-on row above was run on the serverless SQL
> warehouse (`SET ANSI_MODE` returns `true`) and on serverless notebooks
> (`spark.sql.ansi.enabled` = `true`); the ANSI-off column came from
> `spark.conf.set("spark.sql.ansi.enabled", "false")` in the same session. A missing
> map key, `element_at(map('a', 1), 'z')` or `map('a', 1)['z']`, returned `NULL` with
> ANSI on, although the ANSI reference says it throws.

**Dates.** `to_date` without a format accepts ISO `yyyy-MM-dd`, with or without a time
part; anything else needs a pattern, and under ANSI a string that does not match fails.
Patterns are case-sensitive: `MM` is month, `mm` is minute, `HH` is the 24-hour clock.

```sql
SELECT to_date('2026-10-20'),                                  -- 2026-10-20
       to_date('2026-10-20 13:45:00'),                         -- 2026-10-20
       to_date('20/10/2026', 'dd/MM/yyyy'),                    -- 2026-10-20
       to_timestamp('20/10/2026 13:45', 'dd/MM/yyyy HH:mm'),   -- 2026-10-20T13:45:00
       try_to_date('10/20/2026'),                              -- NULL; to_date raises
       date_format(DATE'2026-10-20', 'yyyy-MM');               -- '2026-10'
```

**Nulls have meanings.** Before filling one, ask whether it means *unknown* or
*a specific value*. A null discount that the business says means "no discount" should
become `0.0` — that records the meaning. Filling an *unknown* with a default invents
data. Same operation, opposite verdict.

The null-handling API has more variants than the exam's distractors admit. `dropna`
and `fillna` are aliases of `na.drop` and `na.fill`:

```python
df.na.drop()                          # how='any' (default): drop a row with any null
df.na.drop(how="all")                 # drop only rows that are null in every column
df.na.drop(thresh=2)                  # keep rows with at least 2 non-nulls; overrides how
df.na.drop(subset=["order_id"])       # look at these columns only
df.na.fill(0)                         # numeric columns only; strings untouched
df.na.fill("unknown")                 # string columns only; numbers untouched
df.fillna({"discount_pct": 0.0, "channel": "unknown"})   # per column
```

> **Measured on Free Edition:** on a four-row frame with one all-null row,
> `na.drop()` kept 1, `how="all"` kept 3, `thresh=2` kept 2 and `subset=["id"]` kept
> 3. `na.fill(0)` left the null string column alone and `na.fill("?")` left the null
> double column alone: the fill value's type decides which columns it touches.

## Joins — `ASSOC-S3-O2`

The exam probes join *cardinality* more than join syntax.

| Join | Keeps | Watch for |
|---|---|---|
| `INNER` | matching pairs only | silently drops unmatched rows |
| `LEFT` | all left rows, NULLs on the right | the usual choice when nothing may be lost |
| `LEFT SEMI` | left rows **with** a match, left columns only, each once | an `EXISTS` filter; never fans out |
| `LEFT ANTI` | left rows with **no** match | finding orphans |
| `CROSS` | every combination | almost always an accident |

```sql
SELECT c.* FROM customers c LEFT SEMI JOIN orders o ON c.customer_id = o.customer_id;  -- have ordered
SELECT c.* FROM customers c LEFT ANTI JOIN orders o ON c.customer_id = o.customer_id;  -- never ordered
```

```python
customers.join(orders, "customer_id", "left_semi")   # also "semi", "leftsemi"
customers.join(orders, "customer_id", "left_anti")   # also "anti", "leftanti"
orders.join(dim, ["customer_id", "region"], "left")  # multiple keys: a list of names
```

A semi join returns a left row once however many matches it has, which is why it is
the safe form of "filter to rows that exist over there". `NOT IN (subquery)` is the
trap form of the anti join: one NULL in the subquery makes it return nothing.

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

![Join orders to a dimension with two versions of one key, then fix the fan-out](visual:join-fanout?h=900)

**Broadcast joins.** A normal join shuffles both sides so matching keys meet. If one
side is small, broadcasting it to every executor avoids shuffling the large side at
all. Automatic below `spark.sql.autoBroadcastJoinThreshold` (10 MB default); `-1`
disables it.

**Join strategy chooser.** Sizes and the join condition go in; the strategy and its
shuffle come out:

| Situation | Strategy | Shuffle |
|---|---|---|
| Equi-join, one side under the threshold or hinted | broadcast hash join | none; the small side is copied to every executor |
| Equi-join, both sides large | sort-merge join (the default) | both sides shuffled and sorted |
| Equi-join, both large, `SHUFFLE_HASH` hint | shuffled hash join | both shuffled, no sort |
| Non-equi condition or `CROSS JOIN`, one side small | broadcast nested loop join | none, but every pair is compared |
| Non-equi condition, both sides large | cartesian product | the most expensive plan there is |

An outer join cannot broadcast the side it keeps in full: a `LEFT JOIN` can broadcast
only the right side, and a `FULL OUTER JOIN` cannot broadcast at all. Force a strategy
with a function in Python or a hint in SQL; hints are requests, and Spark ignores one
the join type cannot honour.

```python
from pyspark.sql.functions import broadcast
facts.join(broadcast(dim), "customer_id")        # same as dim.hint("broadcast")
facts.join(dim.hint("merge"), "customer_id")     # also "shuffle_hash", "shuffle_replicate_nl"
```

```sql
SELECT /*+ BROADCAST(d) */ *     -- aliases BROADCASTJOIN, MAPJOIN; also MERGE, SHUFFLE_HASH
FROM facts f JOIN dim d ON f.customer_id = d.customer_id;
```

> **Measured on Free Edition:** `EXPLAIN` showed `BroadcastHashJoin` for the
> `BROADCAST` hint and `SortMergeJoin` for `MERGE` on the same query, and a
> `crossJoin` of two ten-row frames planned as `BroadcastNestedLoopJoin`. On a
> `LEFT JOIN`, `BROADCAST` on the left (kept) side was ignored and the plan still read
> `BroadcastHashJoin ... LeftOuter, BuildRight`; on a `FULL OUTER JOIN` the same hint
> produced a `ShuffledHashJoin`. `NOT IN` against a subquery holding one NULL returned
> 0 rows.

**In SQL, `UNION` deduplicates and `UNION ALL` does not.** Deduplication means a
shuffle, so prefer `UNION ALL` and deduplicate deliberately. The DataFrame API is the
trap: `df.union()` matches columns by *position* and never deduplicates (it is
`UNION ALL`); `unionByName()` matches by name, with `allowMissingColumns=True` to fill
gaps with nulls. Without that flag a missing column raises
`UNRESOLVED_COLUMN_AMONG_FIELD_NAMES`.

**`EXCEPT` and `INTERSECT` follow the same rule.** In SQL they deduplicate unless you
write `ALL`; `MINUS` is a synonym for `EXCEPT`. The DataFrame names differ:

| SQL | DataFrame | Duplicates |
|---|---|---|
| `EXCEPT` / `MINUS` | `subtract()` | removed |
| `EXCEPT ALL` | `exceptAll()` | kept, counted off one for one |
| `INTERSECT` | `intersect()` | removed |
| `INTERSECT ALL` | `intersectAll()` | kept, the lower count of each |

```sql
SELECT customer_id FROM silver_customers
EXCEPT
SELECT customer_id FROM gold_customers;   -- in silver, missing from gold
```

> **Measured on Free Edition:** left `(1, 1, 2, 3)` against right `(1, 3, 3, 4)` gave
> `EXCEPT` → `2`, `exceptAll` → `1, 2`, `INTERSECT` → `1, 3`, `LEFT SEMI` → `1, 1, 3`
> and `LEFT ANTI` → `2`.

## Reshaping — `ASSOC-S3-O3`

`explode()` turns each array element into its own row, carrying the parent columns —
the standard way to change grain from one-row-per-container to one-row-per-item. Use
`explode_outer()` when an empty array should still produce a row. `posexplode()` adds
the element's 0-based position as a column named `pos` beside `col`; its `_outer` form
keeps empty arrays as a row of NULLs.

`split()` returns an array; index it for the parts. **Spark SQL arrays are 0-based** —
except in `element_at`, which counts from 1 and from the end with a negative index.

Indexing past the end **raises** `INVALID_ARRAY_INDEX` under ANSI semantics — it does
not return null — so one malformed row fails the batch. Use `get(arr, i)` when a
missing part is expected and should be null.

```sql
SELECT element_at(array(10, 20, 30), 1),    -- 10  (1-based)
       element_at(array(10, 20, 30), -1),   -- 30  (from the end)
       array(10, 20, 30)[0],                -- 10  (0-based)
       get(array(10, 20, 30), 5);           -- NULL, where [5] would raise

SELECT order_id, pos, item
FROM orders LATERAL VIEW posexplode(items) p AS pos, item;
```

The column and row operations the objective lists, with the names the options use:

```python
from pyspark.sql import functions as F
(df.withColumn("net", F.col("qty") * F.col("price"))        # add or replace one column
   .withColumns({"year": F.year("order_date"), "src": F.lit("web")})
   .withColumnRenamed("cust_id", "customer_id")
   .withColumnsRenamed({"amt": "amount", "ts": "event_ts"})
   .drop("raw_payload", "_rescued_data")                      # missing names are ignored
   .filter((F.col("qty") > 0) & F.col("region").isin("EU", "US"))   # where() is an alias
   .select("*", F.posexplode("items").alias("pos", "item")))
```

DataFrames are immutable. Every transformation returns a new one, and transformations
are lazy — nothing runs until an action.

## Dedup and aggregates — `ASSOC-S3-O4`

`dropDuplicates()` with no arguments compares *whole rows*, so two versions of a
record that differ anywhere are both kept. Deduplicate on the **business key**:
`dropDuplicates(["event_id"])`. When versions genuinely differ, order by an ingestion
timestamp and keep the newest rather than letting Spark pick.

That "keep the newest" is the `row_number` idiom. `rank()` is the wrong function for it:
two rows tied on the timestamp both get rank 1 and both survive.

```sql
SELECT *
FROM bronze_customers
QUALIFY row_number() OVER (PARTITION BY customer_id ORDER BY ingested_at DESC) = 1;
```

```python
from pyspark.sql.window import Window
w = Window.partitionBy("customer_id").orderBy(F.col("ingested_at").desc())
latest = df.withColumn("rn", F.row_number().over(w)).filter("rn = 1").drop("rn")
```

`count(*)` counts rows. `count(col)` counts non-nulls. `avg()` skips nulls — so it
divides by the non-null count, and an average comes out too high if a null really
meant zero.

`approx_count_distinct()` uses HyperLogLog for a bounded error at a fraction of the
cost of an exact distinct. When the business has agreed a tolerance, paying for
exactness is choosing to be slower for nothing. The optional second argument is the
maximum relative standard deviation, 0.05 by default.

`collect_list()` gathers a group's values into an array, duplicates kept;
`collect_set()` drops duplicates and does not promise an order. Both skip nulls.

```python
(df.groupBy("customer_id")
   .agg(F.count("*").alias("orders"),
        F.countDistinct("product_id").alias("products"),
        F.approx_count_distinct("session_id", 0.01).alias("sessions"),   # rsd 0.01
        F.mean("amount").alias("avg_amount"),                             # avg() is the same
        F.collect_set("channel").alias("channels")))
```

**`describe()` vs `summary()`.** Both profile a DataFrame. `describe()` returns count,
mean, stddev, min and max. `summary()` adds the 25%, 50% and 75% percentiles, and
accepts the statistics you want, including any percentile and
`approx_count_distinct`:

```python
df.describe("amount").show()
df.summary().show()
df.select("amount").summary("count", "min", "10%", "50%", "approx_count_distinct").show()
```

> **Measured on Free Edition:** `approx_count_distinct(id)` over `range(100000)`
> returned 95,546 (4.5% low, inside the default 0.05); with `0.01` it returned
> 100,425. `collect_set` over `1, 1, 2, NULL` gave `[1, 2]` and `collect_list` gave
> `[1, 1, 2]`.

## Tuning — `ASSOC-S3-O5`

| Setting | Does | Symptom it fixes |
|---|---|---|
| `spark.sql.shuffle.partitions` | post-shuffle partition count (default 200) | hundreds of sub-second tasks = too many; long spilling tasks = too few |
| `spark.default.parallelism` | default partition count for RDD operations | RDD code only; DataFrame and SQL shuffles ignore it |
| `spark.sql.autoBroadcastJoinThreshold` | auto-broadcast size limit | unnecessary shuffles, or driver OOM if too high |
| `spark.driver.memory` | driver heap; set at cluster creation, not at runtime | a bigger driver postpones a `collect()` OOM and more executors never help; bring less back instead |
| `spark.executor.memory` | executor heap | spill and GC pressure |

Session settings change with `spark.conf.set` or SQL `SET`; memory settings belong in
the cluster's Spark config because the JVMs already exist by the time your code runs.
"Re-measure" in the objective means compare the same query before and after, in the
plan and in the run time, not trust the setting:

```python
spark.conf.set("spark.sql.shuffle.partitions", "64")             # SET spark.sql.shuffle.partitions = 64
spark.conf.set("spark.sql.autoBroadcastJoinThreshold", "-1")     # disable auto-broadcast
spark.conf.get("spark.sql.shuffle.partitions")
df.explain("formatted")    # look for BroadcastHashJoin vs SortMergeJoin, and Exchange nodes
```

```text
# cluster > Advanced > Spark config (classic compute only)
spark.executor.memory 8g
spark.driver.memory 16g
spark.default.parallelism 64
```

`collect()` pulls every row to the driver. Cluster size is irrelevant — the driver is
one JVM. Write the result to a table; `collect()` is for a handful of rows.

> **Measured on Free Edition:** serverless notebooks report
> `spark.sql.shuffle.partitions` = `auto` and accept a new value (`8` read back as
> `8`). Reading or setting `spark.default.parallelism`,
> `spark.sql.autoBroadcastJoinThreshold`, `spark.sql.adaptive.enabled`,
> `spark.executor.memory` or `spark.driver.memory` raises `CONFIG_NOT_AVAILABLE`, and
> `spark.sparkContext` raises `JVM_ATTRIBUTE_NOT_SUPPORTED`. On the SQL warehouse even
> `SET spark.sql.shuffle.partitions` is `CONFIG_NOT_AVAILABLE`. The exam still asks what
> each one does on classic compute; serverless just manages them for you.

## Gold objects — `ASSOC-S3-O6`

| Object | Computed | Choose when |
|---|---|---|
| View | every query | source changes as often as it is read |
| Materialized view | on refresh | read far more often than written |
| Streaming table | incrementally, once per row | append-oriented, continuously arriving data |
| Table | whenever your job writes it | you need `MERGE`, your own schedule, or writers outside a pipeline |

Match the object to the read/write ratio. A dashboard hitting a nightly aggregate
hundreds of times an hour should not recompute it hundreds of times.

**Gold object decision tree.** Ask the questions in this order and stop at the first
yes:

1. **Must every read see the source as it is right now, and is the query cheap or
   rarely run?** A view. It stores nothing, so it is never stale and never refreshed.
2. **Is the source append-only, and should each new row be processed once?** A
   streaming table. A source that updates or deletes rows breaks the stream (unless
   the reader sets `skipChangeCommits`), so this is for events, logs and files.
3. **Is it an aggregate or join read many times between source changes?** A
   materialized view, refreshed on a `SCHEDULE` or `TRIGGER ON UPDATE`. Databricks
   refreshes it incrementally where the query allows and recomputes where it does not.
4. **Do you need to control the writes yourself** (a `MERGE`, an SCD type 2 load, a job
   that also does other things)? A Delta table written by a job.

Both pipeline-backed objects can be created in SQL from a SQL warehouse or a notebook on
serverless compute, as well as inside a pipeline, and Databricks runs a serverless
pipeline behind each create and refresh. `EXPLAIN CREATE MATERIALIZED VIEW` tells you
whether a query can refresh incrementally:

```sql
CREATE OR REPLACE MATERIALIZED VIEW gold.sales_by_region
  SCHEDULE EVERY 1 HOUR                       -- or SCHEDULE CRON '0 0 2 * * ?' AT TIME ZONE 'UTC'
  -- or TRIGGER ON UPDATE AT MOST EVERY INTERVAL 5 MINUTES
AS SELECT region, sum(net_amount) AS revenue FROM silver.orders GROUP BY region;

CREATE OR REPLACE STREAMING TABLE silver.orders_st
  SCHEDULE CRON '0 */15 * * * ?' AT TIME ZONE 'UTC'   -- EVERY has no MINUTES unit
AS SELECT * FROM STREAM read_files('/Volumes/main/raw/orders/', format => 'json');

REFRESH MATERIALIZED VIEW gold.sales_by_region;          -- SYNC by default
REFRESH STREAMING TABLE silver.orders_st ASYNC;          -- return at once
REFRESH STREAMING TABLE silver.orders_st FULL;           -- truncate and reprocess all
ALTER MATERIALIZED VIEW gold.sales_by_region DROP SCHEDULE;
DESCRIBE TABLE EXTENDED gold.sales_by_region;            -- shows refresh status
```

A `FULL` refresh of a streaming table reprocesses only what the source still holds,
so it loses data from a source with short retention such as Kafka. A plain table for
BI is a `CREATE TABLE ... AS SELECT` or a `MERGE` in a scheduled job; grant `SELECT` on
it to the analysts' group.

Views are also the simplest governance boundary: select the permitted columns, grant
on the view, withhold on the table. No duplicate data, always current.

## Quality — `ASSOC-S3-O7`

A `CHECK` constraint is enforced on write — a violating row fails the transaction
rather than landing and being cleaned up later. Adding one validates existing rows,
so it fails if the table already violates it. `NOT NULL` and `CHECK` are the only
enforced constraints; `PRIMARY KEY` and `FOREIGN KEY` are informational.

```sql
CREATE TABLE silver.orders (order_id INT NOT NULL, customer_id INT, quantity INT);
ALTER TABLE silver.orders ADD CONSTRAINT positive_qty CHECK (quantity >= 1);
ALTER TABLE silver.orders DROP CONSTRAINT positive_qty;
SHOW TBLPROPERTIES silver.orders;       -- delta.constraints.positive_qty = quantity >= 1

CREATE TABLE gold.dim_customer (
  customer_id INT NOT NULL,
  name STRING,
  CONSTRAINT dim_customer_pk PRIMARY KEY (customer_id) RELY   -- NORELY is the default
);
ALTER TABLE silver.orders
  ADD CONSTRAINT fk_customer FOREIGN KEY (customer_id) REFERENCES gold.dim_customer;
```

**`RELY`** tells the optimizer it may trust an informational key to rewrite queries
(dropping a join that cannot change the result, for example), on Photon compute.
Nobody checks the key, so if duplicates exist a query can return wrong results. Mark a
key `RELY` only when your pipeline already guarantees it, for instance with the
`row_number` dedup above.

> **Measured on Free Edition:** a table with
> `PRIMARY KEY (customer_id) RELY` accepted two rows with `customer_id = 1`, and a
> `FOREIGN KEY` was added to a table holding a `customer_id` absent from the
> dimension. `CHECK (quantity >= 1)` rejected `quantity = NULL` as well as `0`
> (`DELTA_VIOLATE_CONSTRAINT_WITH_VALUES`), and a two-row insert with one bad row
> landed neither. Adding `CHECK (quantity >= 100)` to a table already holding `3`
> failed with `DELTA_NEW_CHECK_CONSTRAINT_VIOLATION`. `CREATE TABLE` refused a `CHECK`
> written inline ("Only PRIMARY KEY and FOREIGN KEY constraints are currently
> supported"), so add it with `ALTER TABLE`.

**Constraint vs expectation, the same rule twice.** `quantity >= 1` as a Delta
constraint stops the write; as a pipeline expectation it decides what happens to each
bad row and records how many there were:

```sql
-- Delta CHECK constraint: the whole insert fails, nothing lands
ALTER TABLE silver.orders ADD CONSTRAINT positive_qty CHECK (quantity >= 1);
INSERT INTO silver.orders VALUES (1, 1, 2), (2, 1, 0);   -- DELTA_VIOLATE_CONSTRAINT_WITH_VALUES

-- Expectation on a streaming table or materialized view: the row is handled
CREATE OR REPLACE STREAMING TABLE silver.orders_st (
  CONSTRAINT positive_qty EXPECT (quantity >= 1) ON VIOLATION DROP ROW,   -- or FAIL UPDATE
  CONSTRAINT known_customer EXPECT (customer_id IS NOT NULL)              -- warn: keep and count
) AS SELECT * FROM STREAM bronze.orders;
```

```python
from pyspark import pipelines as dp

@dp.table
@dp.expect_or_drop("positive_qty", "quantity >= 1")        # expect / expect_or_drop / expect_or_fail
@dp.expect_all({"known_customer": "customer_id IS NOT NULL"})   # expect_all_or_drop / _or_fail
def orders_st():
    return spark.readStream.table("bronze.orders")
```

| | `CHECK` constraint | Expectation |
|---|---|---|
| Lives on | the Delta table, for every writer | one pipeline dataset's definition |
| Bad row | fails the transaction | warn (default), `DROP ROW` or `FAIL UPDATE` |
| Evidence | the error message | violation counts in the pipeline event log |
| Choose when | no writer may ever land the row | the pipeline should keep running and report |

The strongest signal of *silent* degradation is a jump in null rate: the job still
succeeds, the row count still looks right, and the data is quietly wrong.

After a join meant to enrich without changing grain, assert the row count is
unchanged. One cheap check catches both fan-out and unintended drops.

## Further reading

Official documentation for what this section tests, one link per topic:

- [Transform data](https://docs.databricks.com/aws/en/transform/) — the overview of DataFrame and SQL transformation.
- [PySpark basics](https://docs.databricks.com/aws/en/pyspark/basics) — select, filter, join, groupBy and friends with examples.
- [ANSI compliance in Databricks Runtime](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-ansi-compliance) — what raises under ANSI mode and the `try_` functions.
- [ANSI_MODE](https://docs.databricks.com/aws/en/sql/language-manual/parameters/ansi_mode) — the SQL warehouse parameter and its default.
- [Datetime patterns](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-datetime-pattern) — the letters `to_date` and `date_format` accept.
- [Join hints](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-qry-select-hints) — `BROADCAST`, `MERGE`, `SHUFFLE_HASH` and when Spark ignores them.
- [JOIN clause](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-qry-select-join) — semi, anti and cross joins in SQL.
- [Set operators](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-qry-select-setops) — `UNION`, `EXCEPT`, `INTERSECT`, with and without `ALL`.
- [element_at function](https://docs.databricks.com/aws/en/sql/language-manual/functions/element_at) — the 1-based accessor, against [get](https://docs.databricks.com/aws/en/sql/language-manual/functions/get), the 0-based one.
- [Window functions](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-window-functions) — `row_number`, frames, `PARTITION BY`.
- [QUALIFY clause](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-qry-select-qualify) — filter on a window function without a subquery.
- [PIVOT clause](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-qry-select-pivot) — reshaping long to wide.
- [LATERAL VIEW and explode](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-qry-select-lateral-view) — reshaping wide to long.
- [DataFrame.summary](https://docs.databricks.com/aws/en/pyspark/reference/classes/dataframe/summary) — the statistics it accepts, against `describe()`.
- [Adaptive query execution](https://docs.databricks.com/aws/en/optimizations/aqe) — why 200 shuffle partitions is a ceiling, not a count.
- [Set Spark configuration properties](https://docs.databricks.com/aws/en/spark/conf) — where session settings end and cluster settings begin, and what serverless lets you set.
- [Materialized views](https://docs.databricks.com/aws/en/views/materialized) — when a gold object should be recomputed rather than queried.
- [CREATE MATERIALIZED VIEW](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-materialized-view) — `SCHEDULE`, `TRIGGER ON UPDATE` and expectations in the definition.
- [CREATE STREAMING TABLE](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-streaming-table) — the append-only gold object.
- [REFRESH](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-refresh-full) — `FULL`, `SYNC` and `ASYNC`.
- [Constraints on Databricks](https://docs.databricks.com/aws/en/tables/constraints) — `NOT NULL`, `CHECK`, informational primary keys.
- [CONSTRAINT clause](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-table-constraint) — `RELY` and `NORELY` on primary and foreign keys.
- [Pipeline expectations](https://docs.databricks.com/aws/en/ldp/expectations) — warn, drop or fail, and where the metrics go.

Videos for another angle on the hard parts (channel, length):

- [Medallion Architecture in Data Lakehouse](https://www.youtube.com/watch?v=29FJvrulEAM) — Ease With Data, 3 min. What each layer is allowed to change.
- [Slowly Changing Dimensions: types 0 to 4 explained with real examples](https://www.youtube.com/watch?v=1JswR_4XUdU) — SleekData, 7 min. The modelling vocabulary behind the dimension questions.
