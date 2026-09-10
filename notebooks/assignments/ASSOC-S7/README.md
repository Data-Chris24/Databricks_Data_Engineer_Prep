# Assignment — `ASSOC-S7` Governance and Security

**Objectives:** `ASSOC-S7-O1`, `O2`, `O3`, `O4`

## Before you start

Work the two lessons in `notebooks/lessons/associate/S7/`, and generate the data
(`databricks bundle run generate_datasets_assoc_s7 -t free`).

> **The lesson's single mask will not satisfy this.** It had one sensitive column and
> one audience. This has three kinds of sensitivity and three audiences, and one of
> the requirements cannot be met by masking at all.

## The task

`workspace.de_prep.s7_assess_employees` holds employee records. Publish a governed
table that HR can use fully, regional managers can use for their own region, and
everyone else can use for headcount analysis without seeing anything personal.

| Column | Sensitivity | Required treatment |
|---|---|---|
| `national_id` | direct identifier | **Must not exist in the published table.** Publish an irreversible hash instead |
| `case_note` | free text, may contain anything | Suppressed outside HR |
| `salary` | aggregate-safe, row-unsafe | Null outside HR |
| `region` | scoping attribute | Rows restricted to the viewer's region |

## The output contract

**`workspace.de_prep.s7_governed_employees`**

| Column | Type |
|---|---|
| `employee_id` | `STRING` |
| `full_name` | `STRING` |
| `national_id_hash` | `STRING` |
| `region` | `STRING` |
| `department` | `STRING` |
| `salary` | `DOUBLE` |
| `case_note` | `STRING` |
| `hired_on` | `DATE` |

### Requirements

1. **`national_id` must not appear in the published table.** A mask is not enough —
   masks can be dropped by anyone who can alter the table. Hash it irreversibly.
2. **`salary` and `case_note` must carry column masks** that reveal them only to HR.
3. **A row filter must scope rows by region**, so a regional manager sees only theirs.
4. **Do not lock yourself out.** Every rule must keep a break-glass principal;
   a policy that excludes everyone is unauditable and unrecoverable.
5. Column order matters — the tests compare the whole schema.

## Grading

In the study app, open **Learn → ASSOC-S7** and press **Grade my assignment**: it
runs this section's checks against the tables you produced and shows what
passed and what didn't. The same job from a terminal:

```bash
databricks bundle run grade_assoc_s7 -t free --profile FREE
```

## Hints

<details><summary>Which group function do I use?</summary>

`is_account_group_member('x')` tests an **account**-level group; `is_member('x')`
tests a **workspace**-level one. They are different, and on Free Edition a workspace
admin belongs to no account group of that name. Pick wrong and your policy denies
everyone.
</details>

<details><summary>My table shows no rows at all</summary>

Requirement 4. Your row filter excluded you too.
</details>

<details><summary>Can I just mask national_id?</summary>

Requirement 1. Ask what happens when someone runs `ALTER TABLE ... DROP MASK`. A hash
removes the value from the data; a mask only hides it.
</details>
