# Data Modeling — 6%

A small section with two ideas the exam returns to: **state the grain before you
write code**, and **a natural key identifies an entity only while nothing about
it changes**. The rest is layout, where liquid clustering replaces the decisions
partitioning forced you to make once.

## Scalable models on Delta — `PRO-S10-O1`

Delta gives a model ACID writes, schema enforcement, time travel and concurrent
readers, so the modelling decisions are about **grain and keys**, not storage
mechanics. State the fact's grain in words first: "one row per sale" is a grain;
"sales data" is not. Design so a rebuild is deterministic: a surrogate key derived
from a hash of the natural key and validity start survives a rebuild;
`monotonically_increasing_id()` does not, and every fact already published then
points somewhere else. Keep bronze append-only and raw, silver conformed, gold
modelled; the model is the gold layer.

## Dimensional models — `PRO-S10-O4`

| | Holds | Grain | Grows |
|---|---|---|---|
| **Fact** | measurements and foreign keys | one row per event | continuously |
| **Dimension** | descriptive attributes | one row per entity (or version) | slowly |

| | |
|---|---|
| **Natural key** | the business identifier, `customer_id` |
| **Surrogate key** | a model-generated key identifying **one version** of a row |

A **star** keeps dimension attributes denormalised in one table: fewer joins,
some redundancy. A **snowflake** normalises them into sub-dimensions: less
redundancy, more joins. Star is the default for analytics; storage is cheap and
a four-join "revenue by region" is not.

**When the dimension changes, the natural key stops identifying a row.** A Type
2 dimension keeps one row per *version* with `valid_from` (inclusive) and
`valid_to` (exclusive), a surrogate key per version, and `is_current`. The fact
joins to the version in effect on its own date:

```sql
ON  f.customer_id = d.customer_id
AND f.ordered_on >= d.valid_from
AND f.ordered_on <  d.valid_to
```

The bounds are asymmetric on purpose: an order on a changeover date matches
exactly one version. **A dimension join must not change the fact's row count.**
More rows means the windows overlap; fewer means a gap. And the wrong answer here
is not an error: joining on `customer_id` to the current version returns every
order, no nulls, and a revenue-by-segment breakdown that quietly attributes
January's revenue to the segment the customer moved into in June.

## Layout with liquid clustering — `PRO-S10-O2`

`CLUSTER BY (col, ...)` records the keys on the table. There are no directories:
the engine groups rows into files by those columns and file-level statistics let
it skip the files that cannot match. Cluster a fact on what it is filtered by,
usually the date and the highest-traffic dimension key. `CLUSTER BY AUTO` lets
Databricks choose and revise keys from the query history, the honest default
when you do not yet know the access pattern.

On a clustered table, `OPTIMIZE` clusters **new data only**, so runs stay cheap
as the table grows. `ZORDER` is not incremental: it re-sorts everything it
touches every time. A table is partitioned or clustered, never both.

## Clustering over partitioning and ZORDER — `PRO-S10-O3`

| | Partitioning | ZORDER | Liquid clustering |
|---|---|---|---|
| Set at | create time, fixed | each `OPTIMIZE` | any time, `ALTER TABLE` |
| Physical form | directories | sort order within files | file grouping |
| Incremental | n/a | **no** | **yes**, new data only |
| Skew | one big partition | tolerated | spread across files |
| Small files | the classic cause | does not fix the layout | targets file size |
| Change your mind | rewrite the table | free, but pay the sort | metadata change |

Partitioning splits the table into one directory per distinct value, a good
trade only when each directory holds enough data to be worth opening (rule of
thumb: not below about 1 GB per partition). A hot key becomes a straggler
directory; a fine-grained key becomes thousands of tiny files. Clustering keys
can be changed later; a partition column cannot without rewriting the table, and
on a fact table that grows for years that difference compounds.

Partitioning still wins when partitions are large, when you need to **drop or
overwrite whole slices cheaply** (`REPLACE WHERE` on a partition column drops the
old slice's files by metadata alone and writes only the new slice; on a clustered
table the same statement has to read files to find the matching rows and rewrite
the survivors), or when an external consumer
depends on the directory layout. "Always cluster" is not the lesson; "cluster
unless you can name the reason to partition" is.

## Further reading

Official documentation for what this section tests, one link per topic:

- [Delta Lake best practices](https://docs.databricks.com/aws/en/delta/best-practices) — layout, compaction and MERGE advice.
- [Liquid clustering](https://docs.databricks.com/aws/en/delta/clustering) — choosing keys and changing them.
- [Upsert with MERGE](https://docs.databricks.com/aws/en/delta/merge) — the SCD patterns and `WHEN NOT MATCHED BY SOURCE`.
- [MERGE INTO](https://docs.databricks.com/aws/en/sql/language-manual/delta-merge-into) — the full syntax.
- [AUTO CDC](https://docs.databricks.com/aws/en/ldp/cdc) — SCD type 2 without writing the MERGE.
- [Generated columns](https://docs.databricks.com/aws/en/delta/generated-columns) — derived keys for clustering and partitioning.
- [Constraints](https://docs.databricks.com/aws/en/tables/constraints) — informational primary keys with `RELY`.
- [Selective overwrite](https://docs.databricks.com/aws/en/delta/selective-overwrite) — `replaceWhere` and dynamic partition overwrite.
- [Medallion architecture](https://docs.databricks.com/aws/en/lakehouse/medallion) — where the model lives.

Videos for another angle on the hard parts (channel, length):

- [Slowly Changing Dimension Type 2 in Databricks (PySpark)](https://www.youtube.com/watch?v=WVVa1BuR0tY) — Apostolos Athanasiou, 18 min. An SCD2 MERGE built step by step.
- [Slowly Changing Dimensions: types 0 to 4 explained](https://www.youtube.com/watch?v=1JswR_4XUdU) — SleekData, 7 min. The vocabulary.
- [Databricks Liquid Clustering Introduction](https://www.youtube.com/watch?v=na3Wp-j855g) — Apostolos Athanasiou, 13 min. Clustering versus partitioning and Z-order.
