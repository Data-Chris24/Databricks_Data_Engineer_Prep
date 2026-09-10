# Assignment — `PRO-S10` Data Modeling

**Objectives:** `PRO-S10-O1`, `O2`, `O3`, `O4`

## Before you start

Work the lesson in `notebooks/lessons/professional/S10/`, and generate the data
(`databricks bundle run generate_datasets_pro_s10 -t free`).

> **The lesson's dimension does not change. This one does.** In the lesson,
> `customer_id` identified a customer *and* a row, so a natural-key join was correct
> and a surrogate key would have been ceremony. Here 34 of 80 customers have more than
> one version, and joining on `customer_id` alone matches every one of them.

## The task

Two tables:

- `workspace.de_prep.pro_s10_assess_customer_versions` — a Type 2 dimension source.
  Each row is one *version* of a customer, valid over `[valid_from, valid_to)`.
- `workspace.de_prep.pro_s10_assess_orders` — 900 orders across 2026.

Build a star schema: a customer dimension keyed so a row can be identified, and an
order fact joined to the customer as they were **on the order date**.

The trap is that the wrong answer is not an error. A join on `customer_id` to the
current version returns 900 rows, no nulls, and a revenue-by-segment breakdown that
looks entirely reasonable — while attributing January's revenue to the segment the
customer was moved into in June.

## The output contract

**`workspace.de_prep.pro_s10_dim_customer`** — one row per customer version.

| Column | Type | Meaning |
|---|---|---|
| `customer_sk` | `STRING` | surrogate key — identifies **one version** |
| `customer_id` | `STRING` | natural key — identifies the customer |
| `segment` | `STRING` | |
| `region` | `STRING` | |
| `valid_from` | `DATE` | inclusive |
| `valid_to` | `DATE` | exclusive |
| `is_current` | `BOOLEAN` | |

**`workspace.de_prep.pro_s10_fact_orders`** — one row per order.

| Column | Type | Meaning |
|---|---|---|
| `order_id` | `STRING` | |
| `customer_sk` | `STRING` | the version in effect on `ordered_on` |
| `customer_id` | `STRING` | kept for convenience, not for joining |
| `segment_at_order` | `STRING` | from that version |
| `region_at_order` | `STRING` | from that version |
| `amount` | `DOUBLE` | |
| `ordered_on` | `DATE` | |

### Requirements

1. **The surrogate key identifies a version, not a customer.** 80 customers, 114
   versions, 114 distinct keys.
2. **Make it deterministic.** Rebuilding the dimension must not renumber it, or every
   fact you have already published now points somewhere else. `monotonically_increasing_id()`
   fails this; a hash of the natural key plus `valid_from` does not.
3. **Join as of the fact's own date.** Put the validity window in the join condition.
4. **Preserve the grain.** 900 orders in, 900 rows out, no nulls, revenue unchanged.
   A row count that grows means the windows overlap; one that shrinks means a gap.
5. **Mind the boundary.** `valid_from <= ordered_on < valid_to` — asymmetric, or an
   order placed on a changeover date matches two versions.
6. Column order matters — the tests compare the whole schema.

## Grading

```bash
databricks bundle run grade_pro_s10 -t free
```

The tests are authoritative. The advisory AI review (`grading/rubrics/PRO-S10.yaml`)
judges whether the key is genuinely deterministic and whether you modelled the grain
deliberately — things a row count cannot see.
