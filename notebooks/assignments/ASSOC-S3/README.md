# Assignment — `ASSOC-S3` Data Transformation and Modeling

**Objectives:** `ASSOC-S3-O1`, `O2`, `O4`, `O6`, `O7`

## Before you start

Work through the three lessons in `notebooks/lessons/associate/S3/`, and make sure
the tables exist (`databricks bundle run generate_datasets_assoc_s3 -t free`).

> **The lesson's joins will not survive this data.** The lessons used clean
> dimensions — one row per key, every foreign key resolving. This source has neither.
> Copy the lesson and you will produce a table with the wrong number of rows.

## The task

Enrich `s3_assess_billing_events` with plan details from `s3_assess_plans` and produce
an analysis-ready gold table.

**Inspect both tables first.** In particular, check whether `plan_id` is unique in the
dimension, and what `amount_cents` actually contains.

## The output contract

Create **`workspace.de_prep.s3_gold_billing_enriched`** with exactly this schema, in
this order:

| Column | Type | Meaning |
|---|---|---|
| `billing_id` | `STRING` | Unique. One row per billing event |
| `account_id` | `STRING` | |
| `plan_id` | `STRING` | As recorded on the event |
| `event_date` | `DATE` | |
| `event_type` | `STRING` | `charge` or `refund` |
| `amount` | `DOUBLE` | The event amount **in currency units, not minor units** |
| `signed_amount` | `DOUBLE` | Negative for refunds, positive for charges |
| `plan_name` | `STRING` | From the plan version in effect **on the event date**. Null when unknown |
| `tier` | `STRING` | Same. Null when unknown |
| `plan_missing` | `BOOLEAN` | True when no plan version matched |

### Requirements

1. **Exactly one row per billing event.** Not one per event-plan pair.
2. **No event may be dropped**, including events whose plan is absent from the
   dimension. Flag those with `plan_missing`.
3. **Use the plan version in effect on the event date.** Plans change price over time.
4. **`amount` is in currency units.** Get this wrong and every total is 100x out, with
   no error.
5. **Column order matters** — the tests compare the whole schema.

## Grading

In the study app, open **Learn → ASSOC-S3** and press **Grade my assignment**: it
runs this section's checks against the tables you produced and shows what
passed and what didn't. The same job from a terminal:

```bash
databricks bundle run grade_assoc_s3 -t free --profile FREE
```

## Hints

<details><summary>My row count is 870, not 600</summary>

`plan_id` appears more than once in the dimension — it is slowly-changing. A join
returns one row per matching *pair*. Put the validity window in the join condition.
</details>

<details><summary>My row count is 580</summary>

An inner join dropped the events whose plan is missing. Requirement 2.
</details>

<details><summary>My totals look enormous</summary>

Requirement 4. Look at the raw column name.
</details>
