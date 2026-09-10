# Assignment — `PRO-S6` Cost and Performance Optimization

**Objectives:** `PRO-S6-O1`, `O2`, `O3`, `O5`

## Before you start

Work the two lessons in `notebooks/lessons/professional/S6/`, and generate the data
(`databricks bundle run generate_datasets_pro_s6 -t free`).

> **The lesson's table was slow for one reason and clustering fixed it.** This one is
> slow for three unrelated reasons, and clustering addresses one of them. Applying
> the lesson's `ALTER TABLE ... CLUSTER BY` and stopping there gets a third of the
> marks and, on one of the columns, would make things worse.

## The task

`workspace.de_prep.pro_s6_assess_orders` is expensive to query. Diagnose **three
distinct causes** and recommend a fix for each.

You are graded on the **analysis**. Do not optimise the table — the current state is
the evidence.

## The output contract

**`workspace.de_prep.pro_s6_optimization_report`** — one row per finding.

| Column | Type | Meaning |
|---|---|---|
| `finding` | `STRING` | One of `small_files`, `wide_projection`, `bad_cluster_key` |
| `recommendation` | `STRING` | What to do about it |
| `metric` | `DOUBLE` | The number evidencing it (below) |
| `detail` | `STRING` | A sentence a colleague could act on |

### What `metric` must hold

| `finding` | `metric` |
|---|---|
| `small_files` | the number of files in the table |
| `wide_projection` | the number of columns |
| `bad_cluster_key` | that column's cardinality as a percentage of row count |

### Requirements

1. All three findings, one row each.
2. `bad_cluster_key`'s `recommendation` must **name the column that would be the
   wrong choice**, and the detail must say what to cluster on instead.
3. Do not modify the source table.
4. `detail` must cite a number.

## Grading

```bash
databricks bundle run grade_pro_s6 -t free --profile FREE
```

## Hints

<details><summary>Where do I start?</summary>

`DESCRIBE DETAIL` gives file count and total size in one row. Divide.
</details>

<details><summary>What makes a clustering key bad?</summary>

Count distinct values against row count. If nearly every row is unique, no file can
be skipped — clustering costs a rewrite and buys nothing.
</details>

<details><summary>Why is a wide table a problem if I filter well?</summary>

Filtering chooses rows. Projection chooses columns. `SELECT *` on 25 columns reads
all 25 regardless of how good your filter is.
</details>
