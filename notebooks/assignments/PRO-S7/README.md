# Assignment — `PRO-S7` Data Security and Compliance

**Objectives:** `PRO-S7-O3`, `O4`, `O5`

## Before you start

Work the two lessons in `notebooks/lessons/professional/S7/`, and generate the data
(`databricks bundle run generate_datasets_pro_s7 -t free`).

> **The lesson masked the columns it knew held PII.** That approach leaves this
> dataset non-compliant in three separate ways.

## The task

Publish a compliant version of `workspace.de_prep.pro_s7_assess_records`.

Today's date, for retention purposes, is **2026-03-31**.

## The output contract

**`workspace.de_prep.pro_s7_compliant_records`**

| Column | Type |
|---|---|
| `record_id` | `STRING` |
| `subject_hash` | `STRING` |
| `record_type` | `STRING` |
| `case_note` | `STRING` |
| `created_on` | `DATE` |

### Requirements

1. **Subjects in `pro_s7_assess_erasure_requests` must be gone**, not masked. A
   masked row is a retained row.
2. **Retention differs by `record_type`** — expire anything older than its own limit:

   | `record_type` | Retain for |
   |---|---|
   | `support_ticket` | 365 days |
   | `marketing_event` | 90 days |
   | `transaction_log` | 2555 days |

3. **`case_note` is free text and some of it contains PII** — email addresses and
   phone numbers. It must not survive.
4. **`subject_id` and `full_name` must not appear.** Publish a salted hash of the
   subject instead, so records remain groupable by subject.
5. Column order matters — the tests compare the whole schema.

## Grading

```bash
databricks bundle run grade_pro_s7 -t free --profile FREE
```

## Hints

<details><summary>Does order matter?</summary>

Yes. Purge erasure subjects first — masking them and then deleting is wasted work,
and masking them *instead* of deleting is the mistake requirement 1 is testing.
</details>

<details><summary>How do I find PII inside prose?</summary>

Pattern matching. `rlike` finds it; `regexp_replace` removes it. Test that none
survives rather than assuming your pattern caught everything.
</details>

<details><summary>Why hash the subject rather than drop it?</summary>

Requirement 4 — records must stay groupable by subject. Suppression would destroy
that; a deterministic hash preserves it.
</details>
