# Data Sharing and Federation — 5%

Two features that move data across a boundary **without copying it**. Delta
Sharing sends your tables out; Lakehouse Federation brings someone else's in.
Both are governed by Unity Catalog like anything else, and both have the same
failure mode: the DDL succeeds and tells you nothing about whether it works.

## Delta Sharing — `PRO-S4-O1`, `PRO-S4-O3`

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
| Share files | `ALTER SHARE s ADD VOLUME c.s.v` |
| Send it | `GRANT SELECT ON SHARE s TO RECIPIENT r` |
| Check it | `SHOW ALL IN SHARE s` **and** `SHOW GRANTS ON SHARE s` |

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
  `delta.enableChangeDataFeed`; turn it on at the table and share normally. On the
  Free Edition workspace this repository was built against, the explicit
  `WITH CHANGE DATA FEED` clause was refused with a message about
  Databricks-managed keys; treat that as a measured quirk, not exam material.
- **Adding to a share checks traversal.** `ALTER SHARE ... ADD TABLE` needs
  `USE CATALOG` and `USE SCHEMA`; a `PERMISSION_DENIED` there is almost never
  about the share.
- **A share is a dependency.** An object in a share cannot be dropped
  (`DELTA_SHARING_SECURABLE_DELETE_BLOCKED.BY_SHARES`), because dropping it would
  break a recipient you may not be in contact with.

**Two kinds of recipient**, and the difference decides the setup:

| | Databricks-to-Databricks (D2D) | Open protocol (D2O) |
|---|---|---|
| Recipient is | another Databricks metastore | anyone with a Delta Sharing client |
| Identified by | their sharing identifier (`cloud:region:metastore-id`) | a credential file you send them |
| Auth | `DATABRICKS` | `TOKEN` |
| They read with | a catalog mounted from the share | pandas, Spark, Power BI, anything speaking the protocol |

On the consumer side a D2D share arrives as a **provider**: `SHOW PROVIDERS`,
`CREATE CATALOG partner_data USING SHARE provider.share`, and from there it is an
ordinary catalog with live data and no copy step. Open sharing must be enabled on
the metastore (`INTERNAL_AND_EXTERNAL`), a metastore-admin setting.

**Audit both halves.** "What is in the share" and "who has been granted the
share" are two questions; a sharing review needs `SHOW ALL IN SHARE` *and*
`SHOW GRANTS ON SHARE`. And the requirement that is easiest to miss is the one
with nothing to write: the table that must *not* be shared.

## Lakehouse Federation — `PRO-S4-O2`

| Noun | Is |
|---|---|
| **Connection** | credentials plus an address for a foreign system, stored once in Unity Catalog |
| **Foreign catalog** | one database on that system, mounted into UC |

```sql
CREATE CONNECTION pg TYPE postgresql OPTIONS (host '...', port '5432', user '...', password '...');
CREATE FOREIGN CATALOG crm USING CONNECTION pg OPTIONS (database 'crm');
GRANT USE CONNECTION ON CONNECTION pg TO `analysts`;      -- may build a foreign catalog over it
GRANT USE CATALOG, SELECT ON CATALOG crm TO `analysts`;    -- may read through it
```

Supported sources include PostgreSQL, MySQL, SQL Server, Redshift, Snowflake,
BigQuery, Oracle, Teradata, Hive Metastore and another Databricks workspace.

The governance point: **the credential lives once, inside UC**, owned by whoever
created the connection. Nobody who queries through it sees it, and error messages
redact it. Foreign schemas and tables are discovered on demand and follow the
source as it changes; grants on the foreign catalog inherit to every foreign
table under it, exactly as in the `PRO-S8` model. A connection cannot be dropped
while a foreign catalog is built on it.

**Federation DDL is lazy.** A connection to a host that does not exist is
accepted; so is a foreign catalog over it. The first statement to touch the
source is the first to fail, with `FAILED_JDBC.CONNECTION`. A green deployment
proves nothing; only a query does.

| | Federation | Ingest a copy |
|---|---|---|
| Freshness | live, always | as fresh as the last run |
| Load on the source | every query hits it | one read per run |
| Performance | bounded by the source and the network | Delta-native |
| Good for | exploration, small dimensions, joins against something you do not own | anything hot, big, or repeatedly scanned |

Federate to discover; ingest to serve. A foreign catalog is a live connection to
somebody's production database, and a careless join can put your job in their
incident review.

> Free Edition runs the provider side of sharing and all federation DDL, but has
> no second metastore, no open-protocol sharing and no outbound JDBC path, so the
> consumer side and the federated query path are theory here.

## Further reading

Official documentation for what this section tests, one link per topic:

- [Delta Sharing](https://docs.databricks.com/aws/en/delta-sharing/) — the sharing documentation home.
- [Create and manage shares](https://docs.databricks.com/aws/en/delta-sharing/create-share) — `ADD TABLE`, `WITHOUT HISTORY`, partitions.
- [Create and manage recipients](https://docs.databricks.com/aws/en/delta-sharing/create-recipient) — Databricks-to-Databricks vs open sharing.
- [Share data with Databricks recipients](https://docs.databricks.com/aws/en/delta-sharing/share-data-databricks) — what D2D adds.
- [Read shared data as a recipient](https://docs.databricks.com/aws/en/delta-sharing/recipient) — the recipient's side of the flow.
- [ALTER SHARE](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-alter-share) — every clause.
- [Lakehouse Federation](https://docs.databricks.com/aws/en/query-federation/) — connections, foreign catalogs and pushdown.
- [Foreign catalogs](https://docs.databricks.com/aws/en/query-federation/foreign-catalogs) — creating and querying them.
- [Deletion vectors](https://docs.databricks.com/aws/en/delta/deletion-vectors) — why `WITHOUT HISTORY` needs them off.

Videos for another angle on the hard parts (channel, length):

- [Databricks Lakehouse Federation explained](https://www.youtube.com/watch?v=wr3jXDBRwRY) — Praveen Reddy Learnings, 7 min. A foreign catalog set up and queried.
- [Unity Catalog, Delta Sharing and Data Mesh on Databricks Lakehouse](https://www.youtube.com/watch?v=75QGOtqBj2k) — Databricks, 36 min. Sharing in context.
