# Assignment — `PRO-S1` Developing Code for Data Processing

**Objectives:** `PRO-S1-O3`, `O4`, `O6`, `O7`, `O8`, `O11`

## Before you start

Work the two lessons in `notebooks/lessons/professional/S1/`, and generate the data
(`databricks bundle run generate_datasets_pro_s1 -t free`).

> **The lesson's pipeline reads a snapshot.** This source is a *change feed* — rows
> are events *about* rows. Transform-and-write produces a table of events, not of
> customers.

## The task

`workspace.de_prep.pro_s1_assess_changes` is a change feed with `insert`, `update` and
`delete` operations. Reduce it to **current state**, applying by hand what `AUTO CDC`
would do for you.

Three things make this harder than a dedup:

1. **The feed is out of order.** Row order carries no meaning; `seq_num` does.
2. **Deletes are tombstones.** A key whose latest event is a delete must be **absent**,
   not present with a flag.
3. **Some keys were deleted and later updated.** Those must be present, because their
   highest sequence is the update — not the delete.

## The output contract

**`workspace.de_prep.pro_s1_current_customers`**

| Column | Type | Meaning |
|---|---|---|
| `customer_id` | `STRING` | Unique |
| `tier` | `STRING` | From the winning event |
| `balance` | `DOUBLE` | From the winning event |
| `last_seq` | `INT` | The `seq_num` of the winning event |
| `last_event_ts` | `TIMESTAMP` | Its timestamp |

### Requirements

1. **One row per surviving key.**
2. **The winning event is the highest `seq_num`**, not the last row encountered.
3. **Keys whose latest event is a delete are absent.**
4. **Keys deleted and later updated are present.**
5. Column order matters — the tests compare the whole schema.

## Grading

In the study app, open **Learn → PRO-S1** and press **Grade my assignment**: it
runs this section's checks against the tables you produced and shows what
passed and what didn't. The same job from a terminal:

```bash
databricks bundle run grade_pro_s1 -t free --profile FREE
```

## Hints

<details><summary>I have 300 rows</summary>

That is one arbitrary event per key — a plain `dropDuplicates(["customer_id"])`. It
keeps tombstoned keys and ignores sequencing entirely. Requirements 2 and 3.
</details>

<details><summary>How do I pick the winning event?</summary>

A window partitioned by the key, ordered by `seq_num` descending, taking row 1.
</details>

<details><summary>Should a deleted-then-updated key survive?</summary>

Requirement 4. Ask which event has the higher `seq_num`.
</details>
