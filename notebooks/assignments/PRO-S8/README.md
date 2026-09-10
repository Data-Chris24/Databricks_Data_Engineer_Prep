# Assignment — `PRO-S8` Data Governance

**Objectives:** `PRO-S8-O1`, `PRO-S8-O2`

## Before you start

Work both lessons in `notebooks/lessons/professional/S8/`, and build the structures
(`databricks bundle run generate_datasets_pro_s8 -t free`).

> **In the lesson, every grant sat on the table it named.** That made
> `information_schema.table_privileges` a complete and truthful answer, and the audit
> query three columns long. The catalog you are auditing now is not built that way.

## The task

Audit `pro_s8_assess`. It has two schemas, five tables, and four principals — the
service principals `de_prep_analyst`, `de_prep_engineer`, `de_prep_auditor` and
`de_prep_intern`. Produce two tables.

Somebody in that list holds `SELECT` on every table in the catalog and can read none
of them. Your report has to say so.

## The output contract

**`workspace.de_prep.pro_s8_access_report`** — one row per (principal, table,
privilege) that applies, inherited ones included.

| Column | Type | Meaning |
|---|---|---|
| `principal` | `STRING` | the **display name**, not the application id |
| `table_schema` | `STRING` | |
| `table_name` | `STRING` | |
| `privilege` | `STRING` | `SELECT`, `MODIFY`, … |
| `granted_at_level` | `STRING` | `TABLE`, `SCHEMA` or `CATALOG` — where the grant actually lives |
| `has_use_catalog` | `BOOLEAN` | can the principal traverse the catalog |
| `has_use_schema` | `BOOLEAN` | can it traverse *this* schema |
| `is_effective` | `BOOLEAN` | `has_use_catalog AND has_use_schema` |

Only the four `de_prep_*` principals. Ignore `account users` and the owner.

**`workspace.de_prep.pro_s8_documentation`** — one row per table.

| Column | Type | Meaning |
|---|---|---|
| `table_schema` | `STRING` | |
| `table_name` | `STRING` | |
| `has_table_comment` | `BOOLEAN` | |
| `column_count` | `INT` | |
| `documented_columns` | `INT` | columns with a comment |
| `tag_count` | `INT` | table-level tags |
| `has_pii_column` | `BOOLEAN` | any column tagged `pii = 'true'` |
| `is_documented` | `BOOLEAN` | see the definition below |

**`is_documented`** — because "documented" is a definition, not a column:

> a table comment **or** a table tag named `description`, **and** at least one
> column carrying a comment.

### Requirements

1. **`granted_at_level` must be where the grant lives**, not where it applies. A
   privilege that applies to a table is not necessarily granted on it — and revoking
   it at the wrong level succeeds and changes nothing.
2. **`is_effective` must account for traversal.** Holding `SELECT` is not the same as
   being able to read.
3. **Name the principals.** Application ids are not an audit deliverable.
4. Column order matters — the tests compare the whole schema.

## Grading

```bash
databricks bundle run grade_pro_s8 -t free
```

The tests are authoritative. The advisory AI review (`grading/rubrics/PRO-S8.yaml`)
judges whether you audited the model or just queried one view.

## What this section creates in your workspace

Unlike every other section, PRO-S8 needs real principals — Unity Catalog will not
grant to a workspace-local group. The generator creates four **service principals**
(`de_prep_analyst`, `de_prep_engineer`, `de_prep_auditor`, `de_prep_intern`) and two
**catalogs** (`pro_s8_teach`, `pro_s8_assess`). None of them can sign in or run
anything; they exist only to be granted privileges.

To remove it all afterwards:

```sql
DROP CATALOG pro_s8_teach  CASCADE;
DROP CATALOG pro_s8_assess CASCADE;
```

then delete the four service principals from **Settings → Identity and access →
Service principals**.
