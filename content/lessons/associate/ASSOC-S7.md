# Governance and Security — 15%

Unity Catalog: who can reach what, and how restrictions travel with the data.

## Managed vs external tables — `ASSOC-S7-O1`

The difference is **lifecycle ownership**:

| | Managed | External |
|---|---|---|
| Storage layout | Unity Catalog owns it | you own it |
| `DROP TABLE` | **deletes the data** | removes only the registration |
| Maintenance | automatic — compaction, clustering, vacuum | yours |

Prefer managed unless something outside Databricks also needs to own the files.
Predictive optimization can only maintain a table whose layout Unity Catalog controls,
which is exactly the operational work teams otherwise carry.

A dropped managed table can be recovered with `UNDROP` within the retention window —
a safety net, not a licence to be casual.

## Privileges — `ASSOC-S7-O2`

**Traversal is required.** Reaching an object needs privileges on every container
above it:

```
USE CATALOG  →  USE SCHEMA  →  SELECT
```

A grant on the table alone leaves the user unable to get to it. This is the most
common Unity Catalog puzzle, and the error rarely names the missing traversal
privilege.

**Inheritance is dynamic.** Privileges flow metastore → catalog → schema → table, and
objects created *later* are covered too. A broad grant at catalog level silently
covers everything anyone adds afterwards — which is why least privilege usually means
granting at schema or table level.

**Use service principals for pipelines.** The pipeline survives the person leaving,
its access is scoped to what the job needs rather than everything its author had, and
audit logs attribute the work to the pipeline. Service principals are subject to
exactly the same permission checks — they are not a bypass.

## Masking and row filters — `ASSOC-S7-O3`

| Need | Mechanism |
|---|---|
| Hide or transform a **value** | column mask |
| Remove **rows** | row filter |

Both attach to the **table** and are evaluated per querying user, typically with
`is_account_group_member()`. Because they attach to the table, every path to the data
inherits them — notebook, SQL editor, dashboard, someone else's view built on top.
That is what makes them governance rather than convention.

A view can also expose a permitted subset, and is the simplest answer when a whole
group should see a fixed slice. It stops being enough when different users need
different slices *of the same rows*.

## ABAC — `ASSOC-S7-O4`

Attribute-based policies bind rules to **tags** rather than to named objects. Tag a
column as PII, and every policy targeting that tag applies to it immediately, wherever
it lives.

The failure this removes is the one that actually happens: a new table shipping
unprotected because someone forgot a step. Per-object masks scale linearly with objects
and depend on human diligence every time. The governance question shifts from "did
someone protect this table" to "is the data classified correctly", which is far easier
to audit.
