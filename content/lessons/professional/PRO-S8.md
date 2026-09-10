# Data Governance — 7%

Two objectives, one theme: **the catalog is a database about your data**, and the
answers to "what is this?" and "who can read it?" are queries. The trap in both
is a query that returns a plausible, complete-looking result that is wrong.

## Making data findable — `PRO-S8-O1`

Unity Catalog gives three places to record what something is, and one place to
read it back.

| Want | Use | Read it back from |
|---|---|---|
| Prose for a human | `COMMENT ON TABLE t IS '...'`, or `COMMENT` in the DDL | `information_schema.tables.comment`, `columns.comment` |
| A fact you can filter on | `ALTER TABLE t SET TAGS ('pii' = 'true')` | `information_schema.table_tags`, `column_tags` |
| Who is responsible | `ALTER TABLE t OWNER TO ...` | `tables.table_owner` |

Comments and tags are not alternatives. A **comment** says *what this is*; a
**tag** says *what class of thing this is*, and only the second is queryable at
scale: "show me every column holding PII" is a query over `column_tags`, not a
conversation. Every securable takes a comment (catalog, schema, table, column,
volume, function); tags go on tables and columns.

Two properties of `information_schema` to internalise before building on it:

1. **It lives inside each catalog.** `my_catalog.information_schema.tables`
   describes that catalog only; `system.information_schema` spans the metastore.
2. **It is filtered by the caller's privileges.** An inventory built by an admin
   and the same inventory built by an analyst are different inventories. A
   feature, and a trap if you forget it.

"Documented" is a **definition, not a column**. An inventory built on
`tables.comment` alone reports as undocumented every table whose purpose lives in
a tag or in its column comments, confidently and wrongly. Decide what documented
means for your organisation, write it down, then query for *that*.

## The permission inheritance model — `PRO-S8-O2`

Two rules explain almost every access question:

1. **A privilege granted on a container applies to everything inside it**, now
   and in the future: metastore → catalog → schema → table.
2. **You must be able to reach the object.** `SELECT` on a table is inert without
   `USE CATALOG` on its catalog *and* `USE SCHEMA` on its schema.

Rule 1 is the one people know. Rule 2 generates the support tickets.

**A privilege applies where it inherits; it lives where it was granted.** `SHOW
GRANTS ON TABLE t` lists an inherited grant with `ObjectType = SCHEMA` and the
schema as `ObjectKey`. Revoking it on the table (`REVOKE ... ON TABLE`) reports
success and removes nothing, because there was no table-level grant. Revoke it
where it lives. `information_schema.table_privileges` carries the same fact in
`inherited_from` (`NONE`, `SCHEMA` or `CATALOG`), and the obvious three-column
query simply does not select it.

**Traversal is the privilege you can hold and not use.** A principal can be
granted `SELECT` on every table in a catalog and read none of them, because it
lacks `USE SCHEMA`. `table_privileges` shows the `SELECT`; nothing in that view
says it is ineffective. Effective access is a conjunction across three levels,
and no single view computes it. One spelling trap on the way: you *grant* `USE
CATALOG` with a space and `information_schema` *records* it as `USE_CATALOG` with
an underscore, so a filter on the form you typed matches zero rows and looks like
nobody has access.

**Ownership beats everything.** An owner holds every privilege implicitly and
nothing in `SHOW GRANTS` says so. An access review that only reads grants makes
owners invisible.

| Question | Answer it with |
|---|---|
| Does this principal hold the privilege? | `information_schema.*_privileges` |
| Where is it granted, so I can revoke it? | `SHOW GRANTS` → `ObjectType`, or `table_privileges.inherited_from` |
| Can they actually read the table? | `USE CATALOG` **and** `USE SCHEMA` **and** the privilege |
| Who has it without a grant? | the owner: `*_owner` columns |

Groups make this manageable: grant to groups, and membership changes without
touching a grant. Service principals are principals like users, and appear in
`information_schema` by application id, so an audit deliverable has to join to a
display name.
