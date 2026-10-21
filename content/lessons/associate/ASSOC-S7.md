# Governance and Security — 15%

Unity Catalog: who can reach what, and how restrictions travel with the data.

> **Names:** Catalog Explorer (Data Explorer), standard access mode (shared), dedicated access mode (single user), External Iceberg reads (UniForm), Lakeflow Jobs (Workflows). `DENY` and `is_member()` belong to the legacy Hive metastore table ACLs, and old names still appear in distractors.

## What the exam asks

- An analyst has `SELECT` on a table and still cannot query it — the missing `USE CATALOG` / `USE SCHEMA` traversal grants (`ASSOC-S7-O2`)
- A `REVOKE SELECT` on a table leaves the user able to read it — the privilege is inherited from the schema; revoke where it was granted (`ASSOC-S7-O2`)
- Dropping a table must not delete files another system still reads — an external table over an external location (`ASSOC-S7-O1`)
- An external table should become managed without copying data by hand — `ALTER TABLE ... SET MANAGED` (`ASSOC-S7-O1`)
- Support sees a masked email, the compliance group sees it in full, on every path to the table — a column mask using `is_account_group_member()` (`ASSOC-S7-O3`)
- Every column tagged as PII, including in tables created next month, must be masked without per-table work — an ABAC policy on the catalog or schema matching a governed tag (`ASSOC-S7-O4`)

## Defaults and limits

| Setting | Default or limit | Note |
|---|---|---|
| `DENY` | does not exist | Unity Catalog rejects it: `UC_COMMAND_NOT_SUPPORTED` |
| `UNDROP` window | 7 days | catalog or schema owners can change it; managed and external tables |
| `SET MANAGED` rollback (`UNSET MANAGED`) | 14 days | the old external files are kept that long |
| `SET MANAGED` compute | Databricks Runtime 17.3 LTS or serverless | readers and writers on 15.4 LTS or above |
| `ALL PRIVILEGES` | excludes `MANAGE`, `READ METADATA`, `EXTERNAL USE SCHEMA`, `EXTERNAL USE LOCATION` | grant those separately |
| Catalog isolation mode | `OPEN` | `ISOLATED` limits it to bound workspaces; the workspace catalog starts bound to its own workspace |
| Workspace binding type | `BINDING_TYPE_READ_WRITE` | `BINDING_TYPE_READ_ONLY` blocks writes from that workspace |
| Column masks per column | 1 | setting another replaces it |
| Row filters per table | 1 | only one distinct filter resolves per user and table |
| ABAC `MATCH COLUMNS` | 3 per column mask policy, 6 per row filter policy | `WHEN` defaults to `TRUE` |
| ABAC compute | Databricks Runtime 16.4 or serverless | metastore-level policies are Beta |
| Governed tags | 1,000 per account, 500 allowed values each | keys and values up to 256 characters |
| Dynamic views and masks on dedicated compute | Databricks Runtime 15.4 LTS or above | filtering runs on serverless |

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

A dropped table can be recovered with `UNDROP` within seven days of the drop — a safety
net, not a licence to be casual. It covers external tables too, but only the
registration was dropped there; the files were never touched.

```sql
-- Managed: no LOCATION; Unity Catalog picks the path
CREATE TABLE main.sales.orders (id INT, amount DECIMAL(10,2));

-- External: LOCATION must sit under an external location you can use
CREATE TABLE main.sales.orders_ext (id INT, amount DECIMAL(10,2))
LOCATION 's3://acme-lake/sales/orders';

DESCRIBE TABLE EXTENDED main.sales.orders;   -- Type: MANAGED or EXTERNAL
SELECT table_name, table_type, table_owner
FROM main.information_schema.tables WHERE table_schema = 'sales';

DROP TABLE main.sales.orders;
SHOW TABLES DROPPED IN main.sales;           -- tableId, deletedAt
UNDROP TABLE main.sales.orders;              -- or UNDROP TABLE WITH ID '<tableId>'
```

### Storage credential and external location

An external table needs two securables above it. A **storage credential** wraps a cloud
identity (an IAM role, a managed identity, a service account). An **external location**
pairs a storage credential with a path. Users are granted the location, never the
credential's role, and every external table or volume path must fall under one.

```bash
# Storage credentials are created in Catalog Explorer, the CLI or the API
databricks storage-credentials create --json '{
  "name": "lake_cred",
  "aws_iam_role": {"role_arn": "arn:aws:iam::123456789012:role/uc-lake"}}'
```

```sql
CREATE EXTERNAL LOCATION lake_sales
  URL 's3://acme-lake/sales'
  WITH (STORAGE CREDENTIAL lake_cred)
  COMMENT 'sales landing zone';

GRANT READ FILES, CREATE EXTERNAL TABLE ON EXTERNAL LOCATION lake_sales TO `data_engineers`;
SHOW EXTERNAL LOCATIONS;
```

> **Measured on Free Edition:** `CREATE STORAGE CREDENTIAL` does not parse in SQL; the
> CLI command above did create one. `CREATE EXTERNAL LOCATION` parsed and then failed
> validation (`AWS IAM role does not have READ permissions`), so without your own
> bucket and role there are no external locations, and `CREATE TABLE ... LOCATION`
> fails with `NO_PARENT_EXTERNAL_LOCATION_FOR_PATH`.

### Managed to external lifecycle

Moving between the two is one statement each way, and only for Delta tables you own:

```sql
-- External -> managed: Unity Catalog copies the data into managed storage
ALTER TABLE main.sales.orders_ext SET MANAGED;
-- if External Iceberg reads (UniForm) are on:
ALTER TABLE main.sales.orders_ext SET MANAGED TRUNCATE UNIFORM HISTORY;

-- Changed your mind: within 14 days
ALTER TABLE main.sales.orders_ext UNSET MANAGED;
```

The table keeps its name, history and grants, so readers do not change. The old
external files stay for 14 days so `UNSET MANAGED` can roll back; after that predictive
optimization deletes them, or you `VACUUM`. There is no managed-to-external command:
to get files you own, write a new external table from the managed one (`CREATE TABLE
... LOCATION ... AS SELECT`), and drop the managed one when nothing reads it.

> **Measured on Free Edition:** `SET MANAGED` on a managed table fails with
> `MIGRATION_NOT_SUPPORTED ... because it is not a external table`. Without an external
> location the conversion itself cannot be run here; its syntax, the 14-day window and
> the compute floor are from the docs.

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

**There is no `DENY` in Unity Catalog.** The objective lists GRANT, REVOKE and DENY,
and the trap is that DENY belongs to the legacy Hive metastore table ACLs. In Unity
Catalog you narrow access by granting less, by revoking, or with a row filter or
column mask. And a `REVOKE` on a table does nothing against a privilege inherited
from the schema: revoke where it was granted.

```sql
GRANT USE CATALOG ON CATALOG main TO `analysts`;
GRANT USE SCHEMA, SELECT ON SCHEMA main.sales TO `analysts`;
REVOKE SELECT ON SCHEMA main.sales FROM `analysts`;

SHOW GRANTS ON TABLE main.sales.orders;               -- every principal
SHOW GRANTS `analysts` ON SCHEMA main.sales;          -- one principal
```

> **Measured on Free Edition:** `DENY SELECT ON TABLE ...` fails with
> `UC_COMMAND_NOT_SUPPORTED ... DENY are not supported in Unity Catalog`. A
> `REVOKE SELECT ON TABLE` against a `SELECT` granted on the schema **succeeded with no
> error** and `SHOW GRANTS` still listed the schema's `SELECT` afterwards.

![Grant at catalog, schema or table level for three principals, revoke on a table, create a table later, and turn on a row filter and a column mask](visual:privilege-inheritance?h=900)

### The privilege list

| Privilege | On | What it allows |
|---|---|---|
| `USE CATALOG`, `USE SCHEMA` | catalog, schema | traversal only; no data |
| `BROWSE` | catalog (and external locations) | see names, comments and tags, and request access, without `USE CATALOG`; no data |
| `SELECT` | table, view (or a parent) | read |
| `MODIFY` | table | `INSERT`, `UPDATE`, `DELETE`, `MERGE` |
| `CREATE SCHEMA`, `CREATE TABLE`, `CREATE VOLUME`, `CREATE FUNCTION` | catalog, schema | create children |
| `READ VOLUME`, `WRITE VOLUME` | volume | files in a volume |
| `EXECUTE` | function | call a UDF, including a mask or filter function |
| `APPLY TAG` | most securables | add or remove tags |
| `READ METADATA` | most securables | see metadata, not data |
| `READ FILES`, `WRITE FILES`, `CREATE EXTERNAL TABLE`, `CREATE MANAGED STORAGE` | external location, storage credential | path access and what may be built on it |
| `MANAGE` | most securables | grant and revoke, transfer ownership, rename, drop — without being the owner |
| `ALL PRIVILEGES` | any | every applicable privilege **except** `MANAGE`, `READ METADATA`, `EXTERNAL USE SCHEMA`, `EXTERNAL USE LOCATION` |

`MANAGE` is not ownership: a holder does not get `SELECT` with it, though it can grant
`SELECT` to itself.

### Ownership

Every securable has exactly one owner, a user, service principal or group. The owner
holds every privilege on it and can grant them. The owner or a `MANAGE` holder can
transfer it. Making a **group** the owner
stops a table being orphaned when its creator leaves.

```sql
ALTER TABLE main.sales.orders OWNER TO `data_engineers`;
ALTER SCHEMA main.sales OWNER TO `data_engineers`;
ALTER CATALOG main OWNER TO `platform_admins`;
```

### Views read with the owner's rights

A reader needs `SELECT` on the view plus `USE CATALOG` and `USE SCHEMA` above it,
and **nothing on the underlying tables**: Unity Catalog checks the **view owner's**
access to them. That is what makes a view a governance boundary, and it is also its
failure mode — if the owner loses `SELECT` on a base table, every reader of the view
loses it too. (Dedicated compute on Runtime 15.3 or below is the exception: there the
reader needs `SELECT` on the base tables as well.)

### Catalog-workspace binding

Grants decide **who**; binding decides **from where**. A catalog is `OPEN` to every
workspace on the metastore by default. Set it `ISOLATED` and only bound workspaces can
reach it — a user with every grant is still refused from any other workspace.

```bash
databricks catalogs update prod --isolation-mode ISOLATED
databricks workspace-bindings update-bindings catalog prod --json '{
  "add": [{"workspace_id": 1234567890, "binding_type": "BINDING_TYPE_READ_ONLY"}]}'
databricks workspace-bindings get-bindings catalog prod
```

Metastore admins, the catalog owner or a `MANAGE` holder can change bindings. A common
pattern is the prod catalog bound read-write to the prod workspace and read-only to dev.

> **Measured on Free Edition:** the `workspace` catalog is `ISOLATED` and bound
> `BINDING_TYPE_READ_WRITE` to its own workspace. Setting a scratch catalog `ISOLATED`
> from the CLI added **no** binding, and its owner then got `Catalog '...' is not
> accessible in current workspace` until it was set back to `OPEN`.

### The traversal puzzle three ways

The same requirement — `analysts` reads `main.sales.orders` — granted at three levels:

| Granted | `SHOW GRANTS ON TABLE main.sales.orders` shows | Query result |
|---|---|---|
| `SELECT ON TABLE main.sales.orders` only | `SELECT`, ObjectType `TABLE` | fails: `[INSUFFICIENT_PERMISSIONS] ... User does not have USE CATALOG on Catalog 'main'` |
| `USE CATALOG` on `main`; `USE SCHEMA, SELECT ON SCHEMA main.sales` | `SELECT`, ObjectType `SCHEMA` | works, and covers every table added to `sales` later |
| `USE CATALOG, USE SCHEMA, SELECT ON CATALOG main` | `SELECT`, ObjectType `CATALOG` | works, for every schema and table in `main`, now and later |

The first row is the trap, and `SHOW GRANTS` on the table does not reveal it: the
listing never shows the traversal privileges, only what applies to the table itself.
Check the parents with ``SHOW GRANTS `analysts` ON CATALOG main`` and ``ON SCHEMA``.

> **Measured on Free Edition:** with `USE CATALOG` and `BROWSE` on a catalog, `USE
> SCHEMA` and `SELECT` on the schema, and `MANAGE` on the catalog and the table,
> `SHOW GRANTS ON TABLE` listed `SELECT` (ObjectType `SCHEMA`), `MANAGE` (ObjectType
> `CATALOG`) and `MANAGE` (ObjectType `TABLE`) — no `USE CATALOG`, `USE SCHEMA` or
> `BROWSE`. The error text in the first row is from the docs: on Free Edition the only
> user is an admin and owner, so the refusal cannot be reproduced.

**Use service principals for pipelines.** The pipeline survives the person leaving,
its access is scoped to what the job needs rather than everything its author had, and
audit logs attribute the work to the pipeline. Service principals are subject to
exactly the same permission checks — they are not a bypass.

```sql
-- a service principal is named by its application ID
GRANT USE CATALOG ON CATALOG main TO `6f1c0e2a-1b2c-4d5e-9f00-123456789abc`;
```

## Masking and row filters — `ASSOC-S7-O3`

| Need | Mechanism |
|---|---|
| Hide or transform a **value** | column mask |
| Remove **rows** | row filter |

Both attach to the **table** and are evaluated per querying user, typically with
`is_account_group_member()`. Because they attach to the table, every path to the data
inherits them — notebook, SQL editor, dashboard, someone else's view built on top.
That is what makes them governance rather than convention.

The lesson notebook applies and removes one of each. What it does not show:

```sql
-- A mask can read other columns of the same row
CREATE FUNCTION main.sec.mask_email(email STRING, region STRING)
RETURN CASE WHEN is_account_group_member('compliance') OR region = 'US'
            THEN email ELSE '***' END;
ALTER TABLE main.sales.customers
  ALTER COLUMN email SET MASK main.sec.mask_email USING COLUMNS (region);

-- Both can be declared when the table is created
CREATE TABLE main.sales.customers (
  id INT, email STRING MASK main.sec.mask_email USING COLUMNS (region), region STRING)
WITH ROW FILTER main.sec.f_region ON (region);

-- Where they are recorded
SELECT * FROM main.information_schema.column_masks;  -- mask_name, using_columns
SELECT * FROM main.information_schema.row_filters;   -- filter_name, target_columns
```

Applying one needs ownership of the table or `MANAGE` on it, plus `EXECUTE` on the
function. Each column takes one mask and each table one row filter; a second `SET MASK`
replaces the first. Use `is_account_group_member()`, which checks account groups;
`is_member()` checks workspace-local groups and is there for Hive metastore
compatibility.

> **Measured on Free Edition:** the table's **owner** saw `***` from its own mask — owning
> the table is no exemption, only the function's logic is. A second `SET MASK` on an
> already-masked column replaced the first without a `DROP MASK`, and
> `information_schema.column_masks` showed the new function with `using_columns =
> region`. The inline `MASK ... USING COLUMNS` and `WITH ROW FILTER` form of `CREATE
> TABLE` also ran, and `information_schema.row_filters` listed the filter.

A view can also expose a permitted subset, and is the simplest answer when a whole
group should see a fixed slice. It stops being enough when different users need
different slices *of the same rows*.

### View vs dynamic view vs mask vs ABAC

One requirement four ways: *support sees `***` for email; the `compliance` group sees
it in full.*

```sql
-- 1. View: one fixed answer for everyone who can read the view
CREATE VIEW main.sales.customers_support AS
SELECT id, '***' AS email, region FROM main.sales.customers;

-- 2. Dynamic view: per-user, but only for queries that go through the view
CREATE VIEW main.sales.customers_v AS
SELECT id,
       CASE WHEN is_account_group_member('compliance') THEN email ELSE '***' END AS email,
       region
FROM main.sales.customers;

-- 3. Column mask: per-user, on the table itself
ALTER TABLE main.sales.customers ALTER COLUMN email SET MASK main.sec.mask_email;

-- 4. ABAC: per-user, on every column tagged pii = email under the schema
CREATE POLICY mask_pii_email ON SCHEMA main.sales
COLUMN MASK main.sec.mask_email TO `account users` EXCEPT `compliance`
FOR TABLES MATCH COLUMNS has_tag_value('pii', 'email') AS e ON COLUMN e;
```

| | Per-user | Protects the base table | New tables covered |
|---|---|---|---|
| View | no; grant different views to different groups | only if nobody has `SELECT` on the table | no |
| Dynamic view | yes | only if nobody has `SELECT` on the table | no |
| Column mask | yes | yes | no; one `ALTER` per column |
| ABAC policy | yes | yes | yes, once the column is tagged |

## ABAC — `ASSOC-S7-O4`

Attribute-based policies bind rules to **tags** rather than to named objects. Tag a
column as PII, and every policy targeting that tag applies to it immediately, wherever
it lives.

The failure this removes is the one that actually happens: a new table shipping
unprotected because someone forgot a step. Per-object masks scale linearly with objects
and depend on human diligence every time. The governance question shifts from "did
someone protect this table" to "is the data classified correctly", which is far easier
to audit.

ABAC uses **governed tags**: account-level tag keys with a tag policy that fixes the
allowed values and who may assign them. An ungoverned tag with the same key is just a
label. Policies attach to a catalog, schema or table (metastore in Beta) and apply to
every table below. Creating one needs `MANAGE` or ownership on that securable and
`EXECUTE` on the function. A table owner cannot remove a policy set above it.

```sql
CREATE [OR REPLACE] POLICY name
ON { CATALOG c | SCHEMA c.s | TABLE c.s.t }
[COMMENT '...']
{ ROW FILTER fn | COLUMN MASK fn }
TO principal [, ...] [EXCEPT principal [, ...]]
FOR TABLES
[WHEN has_tag('tag') | has_tag_value('tag', 'value')]          -- default TRUE
[MATCH COLUMNS has_tag_value('tag', 'value') [AS] alias [, ...]]
[ON COLUMN alias]                                              -- column masks only
[USING COLUMNS (alias | literal [, ...])];

SHOW [EFFECTIVE] POLICIES ON TABLE c.s.t;     -- EFFECTIVE adds inherited ones
DESCRIBE POLICY name ON SCHEMA c.s;
DROP POLICY name ON SCHEMA c.s;
```

### ABAC in one policy

```bash
# 1. A governed tag with its allowed values (account level; UI or CLI)
databricks tag-policies create-tag-policy --json '{"tag_key": "pii", "values": [{"name": "email"}, {"name": "phone"}]}'
```

```sql
-- 2. Classify the data
ALTER TABLE main.sales.customers ALTER COLUMN email SET TAGS ('pii' = 'email');

-- 3. One policy for the whole schema
CREATE POLICY mask_pii_email ON SCHEMA main.sales
COMMENT 'Mask every column tagged pii=email'
COLUMN MASK main.sec.mask_email
TO `account users` EXCEPT `compliance`
FOR TABLES
MATCH COLUMNS has_tag_value('pii', 'email') AS e
ON COLUMN e;

-- 4. Next month's table needs only step 2
ALTER TABLE main.sales.leads ALTER COLUMN contact SET TAGS ('pii' = 'email');
```

> **Measured on Free Edition:** ABAC works end to end. A scratch tag policy created
> with the CLI command above, allowed values included, accepted its listed value; a value outside
> the list failed with `UC_TAG_POLICY_VALUE_NOT_ALLOWED ... Allowed values: [email]`.
> A schema-level `COLUMN MASK` policy masked the tagged column at once, and a table
> created **after** the policy was masked the moment its column was tagged, with no
> change to the policy. `information_schema.column_masks` was **empty** for both
> tables — ABAC masks show in `SHOW EFFECTIVE POLICIES` and `DESCRIBE POLICY`, not
> there. A row filter policy whose `USING COLUMNS` named a column already masked by
> another policy was accepted, then every query failed with
> `UC_USING_REF_OF_MASKED_COLUMNS`.

## Further reading

Official documentation for what this section tests, one link per topic:

- [What is Unity Catalog?](https://docs.databricks.com/aws/en/data-governance/unity-catalog/) — the object model and the metastore.
- [Managed tables](https://docs.databricks.com/aws/en/tables/managed) — lifecycle, `UNDROP`, and why they are the default.
- [External tables](https://docs.databricks.com/aws/en/tables/external) — when the files outlive the table.
- [Convert an external table to managed](https://docs.databricks.com/aws/en/tables/convert-external-managed) — `SET MANAGED`, `UNSET MANAGED` and the 14-day window.
- [UNDROP TABLE](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-undrop-table) — the retention window and `WITH ID`.
- [External locations](https://docs.databricks.com/aws/en/connect/unity-catalog/cloud-storage/external-locations) — paths, validation and their privileges.
- [Storage credentials](https://docs.databricks.com/aws/en/connect/unity-catalog/cloud-storage/storage-credentials) — the cloud identity behind an external location.
- [Manage privileges](https://docs.databricks.com/aws/en/data-governance/unity-catalog/manage-privileges/) — `GRANT`, `REVOKE`, `SHOW GRANTS`.
- [SHOW GRANTS](https://docs.databricks.com/aws/en/sql/language-manual/security-show-grant) — the syntax and what the listing includes.
- [Privilege types and inheritance](https://docs.databricks.com/aws/en/data-governance/unity-catalog/manage-privileges/privileges) — the full privilege list and the traversal rule.
- [Ownership](https://docs.databricks.com/aws/en/data-governance/unity-catalog/manage-privileges/ownership) — what an owner can do that nobody else can.
- [Workspace-catalog binding](https://docs.databricks.com/aws/en/catalogs/binding) — isolation mode and read-only bindings.
- [Dynamic views](https://docs.databricks.com/aws/en/views/dynamic) — per-user views and `is_account_group_member()`.
- [Row filters and column masks](https://docs.databricks.com/aws/en/data-governance/unity-catalog/filters-and-masks) — syntax, evaluation and limits.
- [information_schema.column_masks](https://docs.databricks.com/aws/en/sql/language-manual/information-schema/column_masks) — where table-level masks are recorded.
- [Attribute-based access control](https://docs.databricks.com/aws/en/data-governance/unity-catalog/abac/) — tag-driven policies at catalog and schema level.
- [Create and manage ABAC policies](https://docs.databricks.com/aws/en/data-governance/unity-catalog/abac/policies) — `CREATE POLICY`, `MATCH COLUMNS` and the limits.
- [Governed tags](https://docs.databricks.com/aws/en/admin/governed-tags/) — tag policies, allowed values and account limits.
- [Service principals](https://docs.databricks.com/aws/en/admin/users-groups/service-principals) — identities for pipelines.

Videos for another angle on the hard parts (channel, length):

- [Unity Catalog, Delta Sharing and Data Mesh on Databricks Lakehouse](https://www.youtube.com/watch?v=75QGOtqBj2k) — Databricks, 36 min. Governance at scale from the people who built it.
