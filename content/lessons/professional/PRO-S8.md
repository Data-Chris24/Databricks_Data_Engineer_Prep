# Data Governance — 7%

Two objectives, one theme: **the catalog is a database about your data**, and the
answers to "what is this?" and "who can read it?" are queries. The trap in both
is a query that returns a plausible, complete-looking result that is wrong.

> **Names:** Catalog Explorer (Data Explorer), governed tags (tag policies; the API and CLI still say `tag-policies`), AI-generated comments (AI-generated documentation), workspace bindings (workspace-catalog binding).

## What the exam asks

- An auditor needs every column holding PII across the metastore — tag the columns, query `system.information_schema.column_tags` (`PRO-S8-O1`)
- Teams spell the same tag three ways and the PII report misses tables — a governed tag with allowed values, applied with `ASSIGN` (`PRO-S8-O1`)
- Before dropping a table, find every downstream table and job that reads it — `system.access.table_lineage` (`PRO-S8-O1`)
- A group has `SELECT` on a schema and still gets a permission error — it lacks `USE CATALOG` on the catalog (`PRO-S8-O2`)
- `REVOKE SELECT ON TABLE` succeeds and the user still reads the table — the grant was inherited from the schema; revoke it there (`PRO-S8-O2`)
- A catalog must be invisible from the dev workspace, whatever the grants say — set it `ISOLATED` and bind it to prod only (`PRO-S8-O2`)

## Defaults and limits

| Setting | Default or limit | Note |
|---|---|---|
| Tags per securable | 50 | Measured: the 51st fails with "exceeds maximum of 50" |
| Tag key length | 255 characters | Measured; the docs say 256 |
| Tag value length | 256 characters | Measured and in the docs; the value is optional |
| Column tags per table | 1,000 | Docs only |
| Governed tags per account | 1,000, with up to 500 allowed values each | Docs only |
| `SET TAG ON` / `UNSET TAG ON` | Databricks SQL and DBR 16.1+ | `ALTER ... SET TAGS` works from DBR 13.3 LTS |
| `COMMENT ON COLUMN` | Databricks SQL and DBR 16.1+ | Older runtimes: `ALTER TABLE ... ALTER COLUMN c COMMENT '...'` |
| Lineage system tables | rolling 1 year | Catalog Explorer keeps lineage indefinitely; nothing before 1 Sept 2024 |
| Catalog isolation mode | `OPEN` | The workspace catalog is the exception: bound to its own workspace |
| Workspace binding type | `BINDING_TYPE_READ_WRITE` | `BINDING_TYPE_READ_ONLY` is for catalogs only |
| Owner of a new object | its creator | Ownership does not inherit downward |
| `BROWSE` | catalog level only | Metadata without data, and no `USE CATALOG` needed |
| `ALL PRIVILEGES` | evaluated at check time | Excludes `MANAGE`, `EXTERNAL USE SCHEMA`, `EXTERNAL USE LOCATION`, `READ METADATA` |

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
conversation. `COMMENT ON` takes a catalog, schema, table, column, volume,
connection, share, provider or recipient; a function takes its comment in the
`CREATE`. Tags go on catalogs, schemas, tables, views, columns, volumes,
functions and registered models, but not on external locations or connections.

```sql
-- comments: two spellings for a column
COMMENT ON TABLE  sales.orders       IS 'One row per order line. Loaded hourly.';
COMMENT ON COLUMN sales.orders.email IS 'Customer email, PII';          -- DBR 16.1+
ALTER TABLE sales.orders ALTER COLUMN email COMMENT 'Customer email, PII';

-- tags: the older multi-tag form, and the newer one-tag statement
ALTER TABLE  sales.orders SET TAGS ('domain' = 'sales', 'certified' = '');
ALTER TABLE  sales.orders ALTER COLUMN email SET TAGS ('pii' = 'email');
ALTER SCHEMA sales        SET TAGS ('owner_team' = 'finance');
SET TAG   ON COLUMN sales.orders.email pii = email;     -- value optional: SET TAG ON SCHEMA sales owner_team
UNSET TAG ON TABLE  sales.orders certified;
ALTER TABLE sales.orders UNSET TAGS ('domain');

-- read back: one view per securable type
SELECT schema_name, table_name, column_name, tag_value
FROM   system.information_schema.column_tags          -- every catalog you can see
WHERE  tag_name = 'pii';
-- also: catalog_tags, schema_tags, table_tags, volume_tags, routine_tags
```

To apply a tag you own the object or hold `APPLY TAG` on it, plus `USE CATALOG`
and `USE SCHEMA` to reach it. **Tags do not cascade into `information_schema`**:
a tag on a schema appears in `schema_tags` and nowhere in `table_tags`, so "every
table tagged finance" misses the tables whose schema carries the tag.

> **Measured on Free Edition:** a key-only tag (`SET TAG ON SCHEMA s owner_team`)
> is stored with `tag_value = ''`, and `SET TAGS ('certified')` without `= ''` is
> a parse error. A schema tag, governed or not, did not appear in `table_tags` for
> the tables inside it. A hyphenated key (`'bad-key'`) was accepted, although
> the tags page lists `-` among the characters keys cannot contain.

Two properties of `information_schema` to internalise before building on it:

1. **It lives inside each catalog.** `my_catalog.information_schema.tables`
   describes that catalog only; `system.information_schema` spans the metastore
   (and excludes `hive_metastore`).
2. **It is filtered by the caller's privileges.** An inventory built by an admin
   and the same inventory built by an analyst are different inventories. A
   feature, and a trap if you forget it.

"Documented" is a **definition, not a column**. An inventory built on
`tables.comment` alone reports as undocumented every table whose purpose lives in
a tag or in its column comments, confidently and wrongly. Decide what documented
means for your organisation, write it down, then query for *that*.

**AI-generated comments** fill the gap at scale: Catalog Explorer's **AI
generate** button drafts a comment for a table, view, column, schema, catalog,
function, model or volume, and a human accepts or edits it. Saving one needs
ownership or `MODIFY` (ownership for views). It drafts prose; it does not tag.

## Governed tags — `PRO-S8-O1`

A free-form tag is only as good as its spelling: `pii`, `PII` and `contains_pii`
are three tags (keys are case sensitive), and a report on one misses the other
two. **Governed tags** are account-level tag definitions with a fixed list of
allowed values, so the catalog rejects a value outside the list.

| Permission on a governed tag | Lets you | Held by default |
|---|---|---|
| `CREATE` (account level) | define new governed tags | account admins, workspace admins |
| `MANAGE` | edit or delete the tag, grant `MANAGE` / `ASSIGN` | account admins, the tag's creator |
| `ASSIGN` | apply the tag to an object (still needs `APPLY TAG` on the object) | account admins |

```sql
-- applying a governed tag looks like any other tag; the key needs backquotes
-- in SET TAG ON because it contains a dot
SET TAG ON TABLE sales.orders `system.certification_status` = `certified`;
ALTER TABLE sales.orders SET TAGS ('system.certification_status' = 'deprecated');
UNSET TAG ON TABLE sales.orders `system.certification_status`;
```

```bash
# governed tags are defined at account level: UI (Catalog > Governed tags) or API
databricks tag-policies list-tag-policies --profile <PROFILE>
```

Governed tags applied to a catalog or schema are inherited by the objects inside
it (not columns) **for ABAC policy evaluation**, which is what makes "mask every
column tagged `pii` in this catalog" one policy instead of hundreds. That
inheritance is evaluated, not written: `information_schema` still shows the tag
only where it was set. `system.certification_status` is a **system governed
tag**, predefined and not editable, with allowed values `certified` and
`deprecated`; Catalog Explorer shows them as badges.

> **Measured on Free Edition:** `SET TAGS ('system.certification_status' =
> 'gold')` fails with `UC_TAG_POLICY_VALUE_NOT_ALLOWED` and lists the allowed
> values `[certified, deprecated]`. Without backquotes, `SET TAG ON ...
> system.certification_status = certified` is misparsed as a session `SET` and
> fails with `INVALID_SET_SYNTAX`.

## Lineage: where it came from, what reads it — `PRO-S8-O1`

Lineage is metadata Unity Catalog writes for you: every read and write of a UC
table, view or path by a notebook, job, pipeline, dashboard or query is recorded
at run time, down to the column. It answers the two discovery questions a
comment cannot: *where does this come from* and *what breaks if I change it*.

```sql
-- downstream: everything written from orders in the last 90 days
SELECT DISTINCT target_table_full_name, target_type, entity_type, entity_id
FROM   system.access.table_lineage
WHERE  source_table_full_name = 'main.sales.orders'
  AND  event_date >= current_date() - 90;            -- always filter on event_date

-- column level: which target columns derive from orders.email
SELECT target_table_full_name, target_column_name
FROM   system.access.column_lineage
WHERE  source_table_full_name = 'main.sales.orders'
  AND  source_column_name = 'email';
```

| Column | What it holds |
|---|---|
| `source_table_full_name`, `target_table_full_name` | three-part names; NULL for a path |
| `source_path`, `target_path` | storage path when the source or target is not a table |
| `source_type`, `target_type` | `TABLE`, `VIEW`, `MATERIALIZED_VIEW`, `STREAMING_TABLE`, `METRIC_VIEW`, `PATH` |
| `entity_type`, `entity_id`, `entity_run_id` | what ran it: `NOTEBOOK`, `JOB`, `PIPELINE`, `DASHBOARD_V3`, `DBSQL_QUERY`, or NULL |
| `created_by`, `event_time`, `event_date` | who and when |

A row with a source and no target is a read; with both, a write. The system
tables keep a rolling year; the Catalog Explorer lineage graph keeps it
indefinitely. To explore a node in the graph you need at least `BROWSE` on its
catalog; nodes you cannot see appear masked, so lineage is filtered by privilege
just like `information_schema`.

> **Measured on Free Edition:** `table_lineage` and `column_lineage` have the
> columns above plus `statement_id`, `entity_metadata` and `direct_access`. The
> tables are not real time: a `CREATE TABLE ... AS SELECT` run during this check
> had no lineage row minutes later, and the newest row was from the previous
> day. Lineage is for impact analysis, not for a test that runs straight after
> the write.

## The permission inheritance model — `PRO-S8-O2`

Two rules explain almost every access question:

1. **A privilege granted on a container applies to everything inside it**, now
   and in the future: metastore → catalog → schema → table, view, volume,
   function, model.
2. **You must be able to reach the object.** `SELECT` on a table is inert without
   `USE CATALOG` on its catalog *and* `USE SCHEMA` on its schema.

Rule 1 is the one people know. Rule 2 generates the support tickets.

```sql
GRANT USE CATALOG ON CATALOG main            TO `analysts`;
GRANT USE SCHEMA  ON SCHEMA  main.sales      TO `analysts`;
GRANT SELECT      ON SCHEMA  main.sales      TO `analysts`;  -- every table, now and future
GRANT BROWSE      ON CATALOG main            TO `account users`;  -- see metadata, read nothing
GRANT ALL PRIVILEGES ON SCHEMA main.sandbox  TO `engineers`;  -- expanded at check time

SHOW GRANTS ON TABLE main.sales.orders;          -- Principal, ActionType, ObjectType, ObjectKey
SHOW GRANTS `analysts` ON SCHEMA main.sales;

REVOKE SELECT ON SCHEMA main.sales FROM `analysts`;   -- revoke where it lives
ALTER TABLE main.sales.orders OWNER TO `sales_owners`;
```

There is no `DENY` statement in Unity Catalog. Privileges only add; the way to
take access away is to revoke it where it was granted, or to filter it with a row
filter, a column mask or an ABAC policy.

**A privilege applies where it inherits; it lives where it was granted.** `SHOW
GRANTS ON TABLE t` lists an inherited grant with `ObjectType = SCHEMA` and the
schema as `ObjectKey`. Revoking it on the table (`REVOKE ... ON TABLE`) reports
success and removes nothing, because there was no table-level grant. Revoke it
where it lives. `information_schema.table_privileges` carries the same fact in
`inherited_from` (`NONE`, `SCHEMA` or `CATALOG`), and the obvious three-column
query simply does not select it.

> **Measured on Free Edition:** on a table with grants at three levels, `SHOW
> GRANTS ON TABLE` returned five rows with `ObjectType` `CATALOG`, `SCHEMA` and
> `TABLE`, and `table_privileges.inherited_from` returned `CATALOG`, `SCHEMA` and
> `NONE` for the same five. Service principals appear in both by application id
> (a UUID), not by display name.

![Grant where it lives and watch where it applies: traversal, inheritance into a later table, a table-level REVOKE that changes nothing, and a row filter and column mask per principal](visual:privilege-inheritance?h=900)

**Traversal is the privilege you can hold and not use.** A principal can be
granted `SELECT` on every table in a catalog and read none of them, because it
lacks `USE SCHEMA`. `table_privileges` shows the `SELECT`; nothing in that view
says it is ineffective. Effective access is a conjunction across three levels,
and no single view computes it. One spelling trap on the way: you *grant* `USE
CATALOG` with a space and `information_schema` *records* it as `USE_CATALOG` with
an underscore, so a filter on the form you typed matches zero rows and looks like
nobody has access.

**Ownership beats every grant.** An owner holds every privilege implicitly and
nothing in `SHOW GRANTS` says so. An access review that only reads grants makes
owners invisible. Ownership does not inherit: owning a schema does not make you
the owner of the tables in it. The owner of the containing schema or catalog
can still grant on them and transfer their ownership, as can a holder of
`MANAGE` or a metastore admin.

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

## Admin roles, `MANAGE` and `BROWSE` — `PRO-S8-O2`

Three admin roles sit above the grant model, and the exam tests which one can do
what.

| Role | Scope | In Unity Catalog it can |
|---|---|---|
| Account admin | the account | create metastores, attach them to workspaces, assign the metastore admin; holds `CREATE`/`MANAGE`/`ASSIGN` on governed tags |
| Metastore admin | one metastore (optional role) | manage privileges and transfer ownership of **any** object in the metastore |
| Workspace admin | one workspace | owns the workspace catalog by default; cannot grant on, or take ownership of, objects it does not own |

Two privileges change who can act without being owner or admin:

- **`MANAGE`** lets a principal grant and revoke privileges on an object,
  transfer its ownership and drop it, without owning it. It does not grant read
  access, and `ALL PRIVILEGES` does not include it.
- **`BROWSE`** lets a principal see an object's metadata (and request access)
  without `USE CATALOG` and without reading data. It is granted on catalogs
  only, which makes `GRANT BROWSE ON CATALOG c TO \`account users\`` the
  discoverability grant: everyone can find the table and ask for it.

```sql
GRANT MANAGE ON SCHEMA main.sales TO `sales_stewards`;  -- stewards grant, without owning
ALTER CATALOG main OWNER TO `platform_admins`;          -- owner, metastore admin or MANAGE
```

## Workspace bindings — `PRO-S8-O2`

Grants say *who* can use a catalog. Bindings say *from which workspace*. A
catalog is `OPEN` by default, reachable from every workspace attached to the
metastore. Set it `ISOLATED` and only the bound workspaces can use it, whatever
the grants say; a user with `SELECT` working in an unbound workspace does not see
the catalog. Bindings apply to catalogs, external locations, storage credentials
and service credentials, and only a catalog can be bound `READ_ONLY`.

```bash
# isolate the catalog, then bind it to prod read-write and to analytics read-only
databricks catalogs update prod_sales --isolation-mode ISOLATED --profile <PROFILE>
databricks workspace-bindings update-bindings catalog prod_sales --json '{
  "add": [
    {"workspace_id": 1111111111111111, "binding_type": "BINDING_TYPE_READ_WRITE"},
    {"workspace_id": 2222222222222222, "binding_type": "BINDING_TYPE_READ_ONLY"}
  ]}' --profile <PROFILE>
databricks workspace-bindings get-bindings catalog prod_sales --profile <PROFILE>
```

There is no SQL for bindings: they are set in Catalog Explorer, the CLI or the
API, by a metastore admin, the catalog owner or a holder of `MANAGE`.

> **Measured on Free Edition:** the `workspace` catalog reports `isolation_mode:
> ISOLATED`, is owned by the workspace-admins group, and `get-bindings` returns
> one `BINDING_TYPE_READ_WRITE` binding to its own workspace. A catalog created
> by a user reports `isolation_mode: OPEN`.

## Can they read it, in five steps — `PRO-S8-O2`

Answer "why can't they read the table?" (or "why can they?") by walking these in
order. The first failure is the answer.

1. **Binding.** Is the catalog `OPEN`, or `ISOLATED` and bound to the workspace
   the user is working in? If not, nothing else matters.
2. **Catalog.** `USE CATALOG` on the catalog, held directly, through a group, or
   implied by ownership of the catalog.
3. **Schema.** `USE SCHEMA` on the schema, held on the schema or inherited from
   the catalog.
4. **Object.** `SELECT` on the table, held on the table or inherited from the
   schema or catalog, or implied by owning the table. `ALL PRIVILEGES` counts;
   `MANAGE` and `BROWSE` do not.
5. **Rows and columns.** Does a row filter, column mask or ABAC policy apply to
   this user? These are not grants, so no privilege switches them off: a filter
   applies to every reader its function does not exempt (typically with
   `is_account_group_member`), and a table owner cannot override an ABAC
   policy. "Can read the table" and "sees every row" are different answers.

```sql
-- steps 2 to 4 for one principal, from the views the auditor can query
SELECT 'catalog' lvl, privilege_type, inherited_from
FROM   main.information_schema.catalog_privileges
WHERE  grantee = 'analysts' AND privilege_type = 'USE_CATALOG'
UNION ALL
SELECT 'schema', privilege_type, inherited_from
FROM   main.information_schema.schema_privileges
WHERE  grantee = 'analysts' AND schema_name = 'sales'
  AND  privilege_type = 'USE_SCHEMA'
UNION ALL
SELECT 'table', privilege_type, inherited_from
FROM   main.information_schema.table_privileges
WHERE  grantee = 'analysts' AND table_schema = 'sales' AND table_name = 'orders'
  AND  privilege_type = 'SELECT';
-- then: the *_owner columns (step 2 to 4 by ownership), DESCRIBE TABLE EXTENDED
-- for a row filter or mask (step 5), and get-bindings (step 1)
```

The query only sees direct grants to `analysts`; a grant to a group the user
belongs to is a different `grantee`, which is why steps 2 to 4 say "directly or
through a group".

## Further reading

Official documentation for what this section tests, one link per topic:

- [What is Unity Catalog?](https://docs.databricks.com/aws/en/data-governance/unity-catalog/) — the object model.
- [Tags](https://docs.databricks.com/aws/en/database-objects/tags) — applying and querying tags on securables, and the limits.
- [SET TAG](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-set-tag) — the one-tag statement and its securables.
- [COMMENT ON](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-comment) — which objects take a comment.
- [AI-generated comments](https://docs.databricks.com/aws/en/comments/ai-comments) — drafting comments in Catalog Explorer.
- [Governed tags](https://docs.databricks.com/aws/en/admin/governed-tags/) — allowed values and inheritance for ABAC.
- [Governed tag permissions](https://docs.databricks.com/aws/en/admin/governed-tags/manage-permissions) — `CREATE`, `MANAGE`, `ASSIGN`.
- [Certify and deprecate data](https://docs.databricks.com/aws/en/data-governance/unity-catalog/certify-deprecate-data) — the `system.certification_status` tag.
- [Information schema](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-information-schema) — `column_tags`, `table_privileges`, `inherited_from`.
- [Data lineage](https://docs.databricks.com/aws/en/data-governance/unity-catalog/data-lineage) — what is captured and where.
- [Lineage system tables](https://docs.databricks.com/aws/en/admin/system-tables/lineage) — `table_lineage` and `column_lineage` columns and retention.
- [Permissions concepts](https://docs.databricks.com/aws/en/data-governance/unity-catalog/access-control/permissions-concepts) — inheritance, ownership, `ALL PRIVILEGES`.
- [Privileges reference](https://docs.databricks.com/aws/en/data-governance/unity-catalog/access-control/privileges-reference) — every privilege by securable, `MANAGE` and `BROWSE`.
- [Admin privileges](https://docs.databricks.com/aws/en/data-governance/unity-catalog/manage-privileges/admin-privileges) — account, metastore and workspace admins.
- [Ownership](https://docs.databricks.com/aws/en/data-governance/unity-catalog/manage-privileges/ownership) — who can grant.
- [Workspace bindings](https://docs.databricks.com/aws/en/data-governance/unity-catalog/access-control/workspace-catalog-binding) — `OPEN` vs `ISOLATED`, read-only bindings.
- [Unity Catalog best practices](https://docs.databricks.com/aws/en/data-governance/unity-catalog/best-practices) — how to structure catalogs and grants.

Videos for another angle on the hard parts (channel, length):

- [Lineage System Table in Unity Catalog](https://www.youtube.com/watch?v=bZXswjZ0avA) — Databricks, 32 min. Lineage as a governance query.
- [Unity Catalog, Delta Sharing and Data Mesh on Databricks Lakehouse](https://www.youtube.com/watch?v=75QGOtqBj2k) — Databricks, 36 min. The governance model end to end.
