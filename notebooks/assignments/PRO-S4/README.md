# Assignment — `PRO-S4` Data Sharing and Federation

**Objectives:** `PRO-S4-O1`, `PRO-S4-O2`, `PRO-S4-O3`

## Before you start

Work both lessons in `notebooks/lessons/professional/S4/`, and build the objects
(`databricks bundle run generate_datasets_pro_s4 -t free`).

> **In the lesson, the tables shared however you asked.** Deletion vectors were off,
> so `WITHOUT HISTORY` just worked, and one statement per table was enough. Three of
> the four objects here will not cooperate on the first attempt.

## The task

You are the provider. A partner is being onboarded, and legal has been specific.
Configure it, exactly.

### The share — `pro_s4_partner_share`

| Source | Shared as | Terms |
|---|---|---|
| `workspace.de_prep.pro_s4_assess_orders` | `partner.orders` | **no history** — current state only |
| `workspace.de_prep.pro_s4_assess_customers` | `partner.customers` | history **kept** |
| `workspace.de_prep.pro_s4_assess_events` | `partner.events` | the partner needs the **change feed** |
| `workspace.de_prep.pro_s4_assess_files` (volume) | `partner.files` | — |
| `workspace.de_prep.pro_s4_assess_salaries` | — | **must not be shared** |

### The recipient — `pro_s4_partner`

- Databricks-to-Databricks. There is no second metastore here, so target **this**
  workspace's own sharing identifier — read it from the metastore summary rather
  than typing it.
- Granted `SELECT` on the share, and nothing else granted to anyone else.

### Requirements

1. **Every object is aliased into `partner.`** The partner must not see your catalog
   or schema names. Set the alias when you add the object — `REMOVE TABLE` takes the
   *shared* name, so this is not fixable afterwards from the source path.
2. **`partner.orders` must carry no history.** The shortest statement gives you
   history, silently.
3. **`partner.events` must share its change feed.** The clause you would reach for
   first is refused here; find what actually controls it.
4. **`pro_s4_assess_salaries` must not be reachable through any share.** There is
   nothing to write for this requirement, which is why it is the one that gets missed.
5. Nothing about a wrong answer here raises an error. Check the configuration you
   produced, don't assume it.

## Grading

```bash
databricks bundle run grade_pro_s4 -t free
```

The tests read the live configuration — the share's contents and terms, the
recipient, and the grants. The advisory AI review (`grading/rubrics/PRO-S4.yaml`)
judges whether you understood *why* each object needed different handling.

## What Free Edition cannot do here

Measured, not assumed — see `docs/free-edition-constraints.md`:

- **Open-protocol sharing is disabled** on this metastore, so `TOKEN` recipients
  cannot be created. `PRO-S4-O3` is theory here.
- **The consumer side needs a second metastore.** Sharing to your own metastore
  produces no provider, so `CREATE CATALOG ... USING SHARE` cannot be run.
- **Lakehouse Federation's query path does not work.** Connections, foreign catalogs
  and their grants all succeed; the first query fails with `FAILED_JDBC.CONNECTION`,
  including against this workspace's own SQL warehouse. `PRO-S4-O2` is hands-on for
  everything except reading data through it.

## Cleaning up

```sql
DROP SHARE pro_s4_partner_share;
```
then delete the recipient (`databricks recipients delete pro_s4_partner`). Note a
table cannot be dropped while it is in a share — remove it from the share first.
