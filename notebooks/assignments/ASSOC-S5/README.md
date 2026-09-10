# Assignment — `ASSOC-S5` Implementing CI/CD

**Objectives:** `ASSOC-S5-O1`, `O2`, `O3`, `O4`

## Before you start

Work the two lessons in `notebooks/lessons/associate/S5/`, and generate the data
(`databricks bundle run generate_datasets_assoc_s5 -t free`).

> **The lesson hardcoded its destination.** That is fine for one environment and
> wrong for two. Copy it and staging gets production's data — or nothing at all.

## The task

Publish a channel summary to **two environments from one job definition**.

The two environments are two schemas on this workspace, standing in for staging and
production:

| Environment | Schema |
|---|---|
| staging | `workspace.de_prep_staging` |
| production | `workspace.de_prep` |

## Requirements

1. **One job definition.** Not two jobs, not two notebooks. The same resource,
   deployed to two targets.
2. **The destination comes from a bundle variable overridden per target** — the
   notebook must not contain either schema name.
3. **Both environments end up with the same summary**, each row stamped with the
   schema it was written to in an `environment` column.
4. The notebook must **fail loudly** if the parameters are missing, rather than
   quietly defaulting to one environment.

## The output contract

`s5_channel_summary`, in **both** schemas:

| Column | Type |
|---|---|
| `channel` | `STRING` |
| `txns` | `BIGINT` |
| `revenue` | `DOUBLE` |
| `environment` | `STRING` |

## Grading

In the study app, open **Learn → ASSOC-S5** and press **Grade my assignment**: it
runs this section's checks against the tables you produced and shows what
passed and what didn't. The same job from a terminal:

```bash
databricks bundle run grade_assoc_s5 -t free --profile FREE
```

The suite checks both schemas, that the numbers match, and that each row records the
environment it landed in — which is only possible if the destination was genuinely
parameterised.

## Hints

<details><summary>How does a target override a variable?</summary>

```yaml
variables:
  schema:
    default: de_prep

targets:
  staging:
    variables:
      schema: de_prep_staging
```
</details>

<details><summary>How does the notebook receive it?</summary>

`base_parameters` on the task, read with `dbutils.widgets.get()`.
</details>

<details><summary>Both schemas have identical `environment` values</summary>

The stamp is hardcoded rather than derived from the parameter.
</details>
