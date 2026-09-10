# Assignment — `ASSOC-S6` Troubleshooting, Monitoring and Optimization

**Objectives:** `ASSOC-S6-O1`, `O2`, `O3`, `O4`

## Before you start

Work the two lessons in `notebooks/lessons/associate/S6/`, and generate the data
(`databricks bundle run generate_datasets_assoc_s6 -t free`).

> **The lesson's `GROUP BY` finds one of three problems here.** Two of them leave the
> row count and the distinct-key count looking perfectly normal.

## The task

`workspace.de_prep.s6_assess_orders` is unhealthy in **three distinct ways**. Diagnose
all three and publish a report.

You are graded on the **diagnosis**, not on a fix. Do not clean the table.

## The output contract

**`workspace.de_prep.s6_health_report`** — one row per finding.

| Column | Type | Meaning |
|---|---|---|
| `finding` | `STRING` | One of `duplicate_keys`, `null_regression`, `skew` |
| `column_name` | `STRING` | The column the finding concerns |
| `metric` | `DOUBLE` | The number that evidences it (see below) |
| `detail` | `STRING` | A sentence a colleague could act on |

### What `metric` must hold

| `finding` | `metric` |
|---|---|
| `duplicate_keys` | how many rows are redeliveries |
| `null_regression` | how many nulls appear **after** the regression begins |
| `skew` | the largest group's share of all rows, as a percentage |

### Requirements

1. **All three findings**, one row each.
2. Each names the **right column**.
3. Each `metric` is correct.
4. `detail` is non-trivial — a colleague should know what to do next.

## Grading

```bash
databricks bundle run grade_assoc_s6 -t free --profile FREE
```

## Hints

<details><summary>I only found the skew</summary>

That is the one the lesson's query finds. Ask two more questions: does the row count
equal the distinct key count, and is the null rate the same across the whole date
range?
</details>

<details><summary>How do I find a regression date?</summary>

Group by date and compute the null rate per day. The regression is where it jumps.
</details>

<details><summary>Duplicates or a legitimate repeat?</summary>

Compare `count(*)` with `count(distinct order_id)`. If they differ, some order id
appears more than once.
</details>
