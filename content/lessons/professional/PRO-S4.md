# Data Sharing and Federation — 5%

Two features that move data across a boundary **without copying it**. Delta
Sharing sends your tables out; Lakehouse Federation brings someone else's in.
Both are governed by Unity Catalog like anything else, and both have the same
failure mode: the DDL succeeds and tells you nothing about whether it works.

> **Names:** OpenSharing (Delta Sharing), Databricks-to-Open sharing (D2O, open sharing), query federation (Lakehouse Federation), catalog federation (Hive metastore federation). The exam guide and the SQL still say Delta Sharing: `SHARE`, `RECIPIENT`, `deltaSharing`, `DELTA_SHARING_*` errors. The open-source wire protocol is still the Delta Sharing protocol.

## What the exam asks

- A partner on another Databricks account needs live sales data with no copy and no credential to manage — a D2D recipient created `USING ID` from their sharing identifier, and `CREATE CATALOG ... USING SHARE` on their side (`PRO-S4-O1`)
- A vendor reads your data from pandas, Spark outside Databricks or Power BI — an open (`TOKEN`) recipient, a one-time activation link and a credential file (`PRO-S4-O3`)
- One share serves many partners and each may see only its own region's rows — a partition filter on `CURRENT_RECIPIENT().<key>` or a view using `CURRENT_RECIPIENT('<key>')`, driven by recipient properties (`PRO-S4-O1`)
- An open recipient's credential was sent to the wrong person — `rotate-token` with an expiry of `0`, then send the new activation link over a secure channel (`PRO-S4-O3`)
- Analysts join a live PostgreSQL CRM to lakehouse tables, and the password must not be in any notebook — a connection holding a `secret()`, a foreign catalog, and UC grants (`PRO-S4-O2`)
- A federated query is slow and the source team complains about load — check what was pushed down with `EXPLAIN FORMATTED`; if the scan is big or repeated, ingest a copy (`PRO-S4-O2`)

## Defaults and limits

| Setting | Default or limit | Note |
|---|---|---|
| `ADD TABLE` history | `WITH HISTORY` | Databricks Runtime 16.2+ and SQL warehouses; `WITHOUT HISTORY` on older runtimes |
| `ADD SCHEMA` history | always full history | no `PARTITION`, no alias at schema level |
| Privilege a share takes | `SELECT` only | `GRANT SELECT ON SHARE s TO RECIPIENT r` |
| Deletion vectors or column mapping | must be shared `WITH HISTORY` | for `WITHOUT HISTORY`, turn them off and run `REORG ... APPLY (PURGE)` |
| `START VERSION` on `ADD TABLE` | no longer supported | refused with "'START VERSION' is not supported any more" |
| `delta_sharing_scope` | `INTERNAL` or `INTERNAL_AND_EXTERNAL` | open recipients need `INTERNAL_AND_EXTERNAL`, a metastore-admin setting |
| Recipient token lifetime | the metastore's `delta_sharing_recipient_token_lifetime_in_seconds` | at most one year; existing recipients pick up a change only when their token is rotated |
| Tokens per open recipient | at most two | one active, one rotated; rotating again fails until the rotated one expires |
| Credential file download | once | the activation link stops being shown after the download |
| `rotate-token` expiry | seconds left on the old token | `0` expires it at once; it can shorten an expiry, never extend it |
| `CURRENT_RECIPIENT` | Databricks Runtime 14.2+ | only inside a view definition, or as `CURRENT_RECIPIENT().<key>` in `PARTITION` |
| Sharing views | SQL warehouse or Databricks Runtime 13.3 LTS+ | a view may not reference shared tables or shared views |
| Volumes, Python UDFs, metric views | D2D only | open recipients cannot receive them |
| Federation compute | Databricks Runtime 13.3 LTS+, Standard or Dedicated access; Pro or Serverless SQL warehouse | Classic SQL warehouses cannot federate |
| `remote_query` compute | Databricks Runtime 18.3+, or Pro or Serverless SQL warehouse 2025.35+ | `SELECT` only |
| `fetchsize` / `fetchSize` | `0` (driver default, often one fetch for everything) | docs suggest a large value such as `100000` |
| `pushdown.*.enabled` (`remote_query`) | `true` | `limit`, `offset`, `filters`, `aggregates`, `sortLimit` |
| Snowflake `partition_size_in_mb` | `100` | a target uncompressed size, not exact |
| Federated writes | none: read-only | `INSERT`, `MERGE` and DDL through a foreign catalog are refused |

## Delta Sharing — `PRO-S4-O1`

Three nouns carry the whole model:

| Noun | Is | Analogy |
|---|---|---|
| **Share** | a named collection of tables, views and volumes | a playlist |
| **Recipient** | who you are sharing with | the person you sent it to |
| **Grant** | `GRANT SELECT ON SHARE ... TO RECIPIENT ...` | pressing send |

Until the grant runs, the share exists and reaches nobody. `SELECT` is the only
privilege a share takes.

| Want | Statement |
|---|---|
| A container | `CREATE SHARE s` |
| Add a table | `ALTER SHARE s ADD TABLE c.s.t` |
| Current state only | `... WITHOUT HISTORY` |
| Rename for the recipient | `... AS alias.name` |
| Only some rows | `... PARTITION (region = 'EU')` |
| A whole schema, present and future | `ALTER SHARE s ADD SCHEMA c.s` |
| Share files | `ALTER SHARE s ADD VOLUME c.s.v` |
| Send it | `GRANT SELECT ON SHARE s TO RECIPIENT r` |
| Check it | `SHOW ALL IN SHARE s` **and** `SHOW GRANTS ON SHARE s` |

```sql
CREATE SHARE sales_share COMMENT 'Live orders for partners';

ALTER SHARE sales_share ADD TABLE main.sales.orders
  COMMENT 'EU orders only'
  PARTITION (region = 'EU')        -- a partition column, or DS_INVALID_PARTITION_SPEC
  AS partner.orders_eu             -- the name the recipient sees: <schema>.<table>
  WITH HISTORY;                    -- the default; WITHOUT HISTORY = current state only

ALTER SHARE sales_share ADD VOLUME main.sales.contracts AS partner.contracts;
ALTER SHARE sales_share REMOVE TABLE partner.orders_eu;   -- takes the shared name

SHOW ALL IN SHARE sales_share;     -- name, shared_object, history_sharing, cdf_shared, partitions
```

The things that go wrong silently:

- **History is shared by default.** The shortest `ADD TABLE` gives the recipient
  time travel over your table, including versions you may not have meant to
  publish. `WITHOUT HISTORY` shares only current state.
- **`WITHOUT HISTORY` needs deletion vectors off.** With deletion vectors the
  current state is not reconstructable from data files alone, so sharing refuses.
  Turning the property off stops *new* vectors; `REORG TABLE t APPLY (PURGE)`
  removes the existing ones, and that is the step people miss.
- **The recipient sees your names** unless you alias: `AS partner.customers`
  hides your catalog and schema, and lets you reorganise your side without
  breaking theirs. Set it when you add the object: `REMOVE TABLE` takes the
  *shared* name, so it cannot be fixed later from the source path.
- **Change data feed follows the table.** `cdf_shared` reflects the table's own
  `delta.enableChangeDataFeed`; turn it on at the table and share it with
  history. The recipient then reads it with `table_changes()` or
  `readChangeFeed`. `WITHOUT HISTORY` turns `cdf_shared` off.
- **Adding to a share checks traversal.** `ALTER SHARE ... ADD TABLE` needs
  share ownership, `USE CATALOG`, `USE SCHEMA` and `SELECT` on the table (and
  `READ VOLUME` for a volume). A `PERMISSION_DENIED` there is almost never about
  the share. If the share owner later loses `SELECT`, recipients lose access.
- **A share is a dependency.** An object in a share cannot be dropped
  (`DELTA_SHARING_SECURABLE_DELETE_BLOCKED.BY_SHARES`), because dropping it would
  break a recipient you may not be in contact with.

> **Measured on Free Edition:** on the workspace this repository was built
> against, the explicit `WITH CHANGE DATA FEED` clause was refused with a message
> about Databricks-managed keys, while `PARTITION` on a partitioned table, `LIKE`
> patterns and several partition specs on one `ADD TABLE` were all accepted
> (2026-10-20). Treat the CDF refusal as a workspace quirk, not exam material.

### One share, many recipients: partitions and recipient properties

A recipient can carry **properties**: key-value pairs you set and the share
reads. `databricks.accountId`, `databricks.metastoreId` and `databricks.name` are
predefined; you add your own. Two mechanisms use them.

```sql
CREATE RECIPIENT acme USING ID 'aws:eu-west-1:<metastore-uuid>'
  PROPERTIES ('region' = 'EU', 'tier' = 'gold');
ALTER RECIPIENT acme SET PROPERTIES ('region' = 'US');
ALTER RECIPIENT acme UNSET PROPERTIES ('tier');
DESCRIBE RECIPIENT acme;           -- auth type, properties, IP access list, tokens

-- 1. Partition filter: the key is read with dot syntax, no quotes
ALTER SHARE sales_share ADD TABLE main.sales.orders
  PARTITION (region = CURRENT_RECIPIENT().region) AS partner.my_orders;

-- 2. Dynamic view: any column, a function call with the key quoted
CREATE VIEW main.sales.orders_for_recipient AS
  SELECT order_id, amount, region FROM main.sales.orders
  WHERE region = CURRENT_RECIPIENT('region');
ALTER SHARE sales_share ADD VIEW main.sales.orders_for_recipient AS partner.orders;
```

The two spellings differ and the exam can use the difference:
`CURRENT_RECIPIENT().region` in a `PARTITION` clause, `CURRENT_RECIPIENT('region')`
in a view. A partition filter needs a real partition column. A dynamic view
filters on anything and can hide columns too. `CURRENT_RECIPIENT` is the sharing
counterpart of `current_user()` in a dynamic view: it is resolved on the
recipient's side, at query time.

> **Measured on Free Edition:** `PARTITION (region = 'EU')` on a table with no
> partition columns was refused with `DS_INVALID_PARTITION_SPEC`. The view above
> was created and added to a share (with a warning that shared views support only
> a subset of built-in functions), but querying it as the provider failed with
> `DELTA_SHARING_CURRENT_RECIPIENT_PROPERTY_UNDEFINED.PROVIDER`, and a bare
> `SELECT current_recipient('region')` failed with `INVALID_CURRENT_RECIPIENT_USAGE`:
> the function only exists inside a share-only view. The docs' answer for testing
> one is to share it with yourself and query it as a recipient.

### D2D, step by step

**Two kinds of recipient**, and the difference decides the setup:

| | Databricks-to-Databricks (D2D) | Open protocol (D2O) |
|---|---|---|
| Recipient is | another Databricks metastore | anyone with a Delta Sharing client |
| Identified by | their sharing identifier (`cloud:region:metastore-id`) | a credential file you send them |
| Auth | `DATABRICKS` | `TOKEN` (or OIDC federation) |
| Secret to manage | none | a bearer token that expires and is rotated |
| Can receive | tables, views, volumes, models, notebooks, metric views | tables, views; streaming tables and materialized views as current snapshot only |
| They read with | a catalog mounted from the share | pandas, Spark, Power BI, anything speaking the protocol |

```sql
-- Recipient, in their workspace: find the identifier to send you
SELECT CURRENT_METASTORE();                 -- aws:us-east-2:<uuid>

-- Provider, in yours
CREATE RECIPIENT acme USING ID 'aws:us-east-2:<uuid>' COMMENT 'Acme analytics';
GRANT SELECT ON SHARE sales_share TO RECIPIENT acme;

-- Recipient again: the share arrives as a provider
SHOW PROVIDERS;
SHOW SHARES IN PROVIDER `our_company`;
CREATE CATALOG partner_sales USING SHARE `our_company`.sales_share;
GRANT USE CATALOG, USE SCHEMA, SELECT ON CATALOG partner_sales TO `acme_analysts`;
SELECT * FROM partner_sales.partner.orders_eu;   -- live, no copy step
```

No token appears anywhere: Databricks authenticates the two metastores to each
other. The recipient's catalog is read-only, and from there it is governed like
any other catalog on *their* side; you control what is in the share, they control
who in their organisation reads it. Revoking is one statement,
`REVOKE SELECT ON SHARE sales_share FROM RECIPIENT acme`, and there is no
credential to chase afterwards.

**Audit both halves.** "What is in the share" and "who has been granted the
share" are two questions; a sharing review needs `SHOW ALL IN SHARE` *and*
`SHOW GRANTS ON SHARE`. And the requirement that is easiest to miss is the one
with nothing to write: the table that must *not* be shared.

> **Measured on Free Edition:** the whole provider side runs: shares, `ADD TABLE`,
> `ADD VIEW`, `ADD VOLUME`, a D2D recipient and the grant. The consumer side does
> not: the only metastore is your own, sharing to it produces no provider, and
> only one D2D recipient can point at a given metastore id (the workspace already
> has one), so `CREATE CATALOG ... USING SHARE` cannot be run.

## Sharing with any platform: the open protocol — `PRO-S4-O3`

"Any computing platform" means a recipient who is not on Databricks, or not on
your account. They get a **bearer token** wrapped in a credential file, and they
read with any Delta Sharing client. Open sharing has to be switched on for the
metastore first.

```bash
# Metastore admin: allow open recipients, and set the default token lifetime (seconds)
databricks metastores update <metastore-uuid> \
  --delta-sharing-scope INTERNAL_AND_EXTERNAL \
  --delta-sharing-recipient-token-lifetime-in-seconds 7776000   # 90 days

databricks recipients create vendor TOKEN     # prints activation_url
databricks recipients get vendor              # activation_url again, until it is used
databricks recipients rotate-token vendor 3600   # new token; the old one dies in an hour (0 = now)
```

```sql
CREATE RECIPIENT vendor COMMENT 'External vendor';   -- no USING ID: open recipient, TOKEN auth
DESCRIBE RECIPIENT vendor;                           -- activation_link, tokens, ip_access_list
GRANT SELECT ON SHARE sales_share TO RECIPIENT vendor;
```

The flow, and where it breaks:

1. **Create** the recipient without `USING ID`. Unity Catalog issues a token and an
   **activation link**.
2. **Send the link** over a secure channel. The recipient downloads the credential
   file (`config.share`: endpoint URL plus bearer token) **once**; after that the
   link is no longer shown.
3. **They read** with the path `<profile-file>#<share>.<schema>.<table>`:

   ```python
   import delta_sharing
   df = delta_sharing.load_as_pandas("/secure/config.share#sales_share.partner.orders_eu")

   spark.read.format("deltaSharing").load("/secure/config.share#sales_share.partner.orders_eu")
   (spark.read.format("deltaSharing")
       .option("readChangeFeed", "true").option("startingVersion", 3)   # needs history + CDF on the table
       .load("/secure/config.share#sales_share.partner.orders_eu"))
   ```

4. **The token expires** after the metastore's lifetime (at most a year). Changing
   the metastore default does not touch existing recipients; rotate them.
5. **Rotate** with `rotate-token <name> <seconds>`: a new token, and the old one
   lives for the overlap you choose. A recipient holds at most two tokens, so you
   cannot rotate twice in a row. For a leaked credential: revoke the share, rotate
   with `0`, send the new link securely, re-grant once it has been used, or drop
   and recreate the recipient.
6. **Restrict where from** with an IP access list on the recipient
   (`ip_access_list.allowed_ip_addresses`, set with `databricks recipients update`).
   Open recipients only.

What the open protocol cannot carry: volumes, Python UDFs and models, metric views,
and history or streaming reads of streaming tables and materialized views (open
recipients get their current snapshot only). If the partner is on Databricks, D2D
is the better answer to almost every question: no token to leak, expire or rotate.

> **Measured on Free Edition:** `delta_sharing_scope` is `INTERNAL` and cannot be
> changed, so both `CREATE RECIPIENT` without `USING ID` and
> `databricks recipients rotate-token` fail with "External Delta Sharing is not
> enabled on the metastore". Everything in this section past that point was
> checked against the documentation, not run.

## Lakehouse Federation — `PRO-S4-O2`

| Noun | Is |
|---|---|
| **Connection** | credentials plus an address for a foreign system, stored once in Unity Catalog |
| **Foreign catalog** | one database on that system, mounted into UC |

```sql
CREATE CONNECTION pg TYPE postgresql OPTIONS (
  host 'crm.internal.example.com', port '5432',
  user secret('crm', 'user'), password secret('crm', 'password'));   -- secret(scope, key)
CREATE FOREIGN CATALOG crm USING CONNECTION pg OPTIONS (database 'crm');

GRANT CREATE FOREIGN CATALOG ON CONNECTION pg TO `platform_team`;   -- may build a catalog on it (+ CREATE CATALOG on the metastore)
GRANT USE CONNECTION ON CONNECTION pg TO `power_users`;             -- may see it and run remote_query
GRANT USE CATALOG, USE SCHEMA, SELECT ON CATALOG crm TO `analysts`; -- may read through the foreign catalog
REFRESH FOREIGN CATALOG crm;                                        -- re-read the source's metadata now
```

Query federation sources include PostgreSQL, MySQL, SQL Server, Azure Synapse,
Oracle, Teradata, Redshift, Snowflake, BigQuery, Salesforce Data 360 and another
Databricks workspace. Catalog federation instead reads a foreign catalog's files
straight from object storage: Hive metastore (legacy or external), AWS Glue,
Snowflake and others.

**Who may do what.** Creating a connection takes `CREATE CONNECTION` on the
metastore. Building a foreign catalog on it takes `CREATE CATALOG` on the
metastore *and* ownership of the connection or `CREATE FOREIGN CATALOG` on it.
`USE CONNECTION` is not that privilege: it lets someone see the connection and
query it with `remote_query`. Readers of the foreign catalog need nothing on the
connection at all, only `USE CATALOG`, `USE SCHEMA` and `SELECT`, exactly as for
a Delta table (the `PRO-S8` model).

The governance point: **the credential lives once, inside UC**, owned by whoever
created the connection. Nobody who queries through it sees it, and error messages
redact it. Foreign schemas and tables are discovered on demand and follow the
source as it changes; grants on the foreign catalog inherit to every foreign
table under it. A connection cannot be dropped while a foreign catalog is built
on it. Everything is **read-only**: no `INSERT`, `MERGE` or DDL goes back to the
source.

**Federation DDL is lazy.** A connection to a host that does not exist is
accepted; so is a foreign catalog over it. The first statement to touch the
source is the first to fail, with `FAILED_JDBC.CONNECTION`. A green deployment
proves nothing; only a query does.

> **Measured on Free Edition:** connections, foreign catalogs and all three
> grants run; nothing past them does, because there is no outbound JDBC path.
> `SHOW SCHEMAS`, `SELECT`, `REFRESH FOREIGN CATALOG` and `remote_query` all fail
> with `FAILED_JDBC.CONNECTION`, the URL redacted. A `secret()` pointing at a
> scope or key that does not exist is refused with the misleading
> `INVALID_SQL_SYNTAX.OPTION_IS_INVALID` ("only constant expressions are
> supported"); with a real secret the same statement succeeds (2026-10-20).

### `remote_query`: send the source its own SQL

A foreign catalog maps tables. `remote_query` skips the mapping and sends a query
in the source's own dialect through the connection, as a table-valued function.

```sql
SELECT * FROM remote_query('pg',
  database => 'crm',
  query    => 'SELECT id, name FROM public.accounts WHERE active');   -- source dialect

SELECT * FROM remote_query('pg',
  database        => 'crm',
  dbtable         => 'public.orders',      -- dbtable or query, never both
  fetchsize       => '100000',             -- default 0, the driver default
  partitionColumn => 'order_id', lowerBound => '1', upperBound => '1000000',
  numPartitions   => '8');                 -- all four together, dbtable only

-- Delegated access: readers get SELECT on the view, the view's owner holds USE CONNECTION
CREATE VIEW main.crm_live.active_accounts AS
  SELECT * FROM remote_query('pg', database => 'crm', query => 'SELECT * FROM public.accounts');
```

Oracle takes `service_name` instead of `database`; BigQuery needs
`materializationDataset` for a `query`. It is `SELECT` only: a DML statement
raises `DML_OPERATIONS_NOT_SUPPORTED_FOR_REMOTE_QUERY_FUNCTION`, and a missing
`USE CONNECTION` raises `PERMISSION_DENIED`.

### What federation pushes down

A federated query runs in two places: the part the source can do is translated
and sent to it, and Databricks does the rest after pulling the rows over the
network. What gets pushed decides whether the source returns ten rows or ten
million.

| Usually pushed down | Not pushed down, or only sometimes |
|---|---|
| projections (only the columns you select) | functions with no remote translation, such as `ILIKE` |
| filters, part by part: an `AND` pushes the half it can translate | date, string and maths functions: in filters only, depending on the source |
| `LIMIT`, `OFFSET`, `TABLESAMPLE` | arithmetic when ANSI mode is off |
| aggregates | joins across two connections, or a federated table joined to a Delta table |
| inner, left and right outer joins within one source | a join over an aggregate or a `LIMIT` |

Join pushdown is on by default for Redshift, Snowflake and BigQuery. For
PostgreSQL, MySQL, SQL Server, Oracle and Teradata it is a preview with its own
toggle. A join between a foreign table and a Delta table always runs in
Databricks: both sides travel to the cluster first.

```sql
EXPLAIN FORMATTED
SELECT region, count(*) FROM crm.public.orders
WHERE order_date >= '2026-01-01' AND customer ILIKE '%acme%'
GROUP BY region;
-- look for PushedFilters (the date half only; ILIKE stays local),
-- PushedAggregates, and PushedJoins with [L] and [R] for a pushed join
```

`EXPLAIN` shows the plan, not always the query that runs: adaptive execution can
change it. To switch a pushdown off for one `remote_query`, pass
`'pushdown.filters.enabled' => 'false'` (also `limit`, `offset`, `aggregates`,
`sortLimit`; all default `true`).

> **Docs only:** none of the pushdown behaviour can be seen on Free Edition, since
> no federated query reaches a source there. This section is from the federation
> performance and `remote_query` documentation.

| | Federation | Ingest a copy |
|---|---|---|
| Freshness | live, always | as fresh as the last run |
| Load on the source | every query hits it | one read per run |
| Performance | bounded by the source and the network | Delta-native |
| Good for | exploration, small dimensions, joins against something you do not own | anything hot, big, or repeatedly scanned |

Federate to discover; ingest to serve. A foreign catalog is a live connection to
somebody's production database, and a careless join can put your job in their
incident review.

## Further reading

Official documentation for what this section tests, one link per topic:

- [OpenSharing (Delta Sharing)](https://docs.databricks.com/aws/en/opensharing/) — the sharing documentation home.
- [Create and manage shares](https://docs.databricks.com/aws/en/opensharing/create-share) — `ADD TABLE`, `WITHOUT HISTORY`, partitions, views and dynamic views.
- [Create and manage recipients](https://docs.databricks.com/aws/en/opensharing/create-recipient) — Databricks-to-Databricks vs open sharing.
- [Manage recipients](https://docs.databricks.com/aws/en/opensharing/manage-recipients) — recipient properties, `DESCRIBE RECIPIENT`, IP access lists.
- [Open recipients with bearer tokens](https://docs.databricks.com/aws/en/opensharing/create-recipient-token) — activation links, token lifetime and rotation.
- [Share data with Databricks recipients](https://docs.databricks.com/aws/en/opensharing/share-data-databricks) — what D2D adds.
- [Read shared data as a recipient](https://docs.databricks.com/aws/en/opensharing/recipient) — the recipient's side of the flow.
- [Read shared data with open sharing](https://docs.databricks.com/aws/en/opensharing/read-data-open) — pandas, Spark, Power BI and the credential file.
- [ALTER SHARE](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-alter-share) — every clause.
- [`current_recipient`](https://docs.databricks.com/aws/en/sql/language-manual/functions/current_recipient) — the function behind dynamic shared views.
- [Lakehouse Federation](https://docs.databricks.com/aws/en/query-federation/) — query federation vs catalog federation.
- [Query federation](https://docs.databricks.com/aws/en/query-federation/database-federation) — connections, foreign catalogs and supported sources.
- [Foreign catalogs](https://docs.databricks.com/aws/en/query-federation/foreign-catalogs) — creating and querying them.
- [Federation performance](https://docs.databricks.com/aws/en/query-federation/performance-recommendations) — pushdown, join pushdown, `fetchSize`, parallel reads.
- [Remote queries](https://docs.databricks.com/aws/en/query-federation/remote-queries) — `remote_query` options per connector.
- [Deletion vectors](https://docs.databricks.com/aws/en/tables/features/deletion-vectors) — why `WITHOUT HISTORY` needs them off.

Videos for another angle on the hard parts (channel, length):

- [Databricks Lakehouse Federation explained](https://www.youtube.com/watch?v=wr3jXDBRwRY) — Praveen Reddy Learnings, 7 min. A foreign catalog set up and queried.
- [Unity Catalog, Delta Sharing and Data Mesh on Databricks Lakehouse](https://www.youtube.com/watch?v=75QGOtqBj2k) — Databricks, 36 min. Sharing in context.
