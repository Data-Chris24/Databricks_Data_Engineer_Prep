# Ensuring Data Security and Compliance — 10%

Two mistakes run through this section: treating a mask as deletion, and assuming
you know where the sensitive data is. The exam asks you to choose the right
control for the requirement, and to notice when the cheap control is not enough.

> **Names:** compute policies (cluster policies), Lakeflow Jobs (Workflows),
> Standard access mode (Shared), Dedicated access mode (Single user), ABAC
> policies (the tag-driven successor to per-table filters and masks). Old names
> still appear in distractors.

## What the exam asks

- A service principal must trigger a job but not edit it — `CAN_MANAGE_RUN` on the job, not ownership (`PRO-S7-O1`)
- Analysts in one region may see only their region's rows, and salary only if in HR — a row filter plus a column mask, with `USING COLUMNS` when the mask needs another column (`PRO-S7-O2`)
- A hashed date of birth turns out to be re-identifiable — low-entropy input; salt it, with the salt in a secret scope (`PRO-S7-O3`)
- A pipeline masks the `email` column but emails still leak — PII inside free text; detect with patterns in batch and streaming alike (`PRO-S7-O4`)
- A subject was deleted and vacuumed, yet the row is still on storage — deletion vectors; `REORG TABLE ... APPLY (PURGE)` before `VACUUM` (`PRO-S7-O5`)
- An erasure is "done" in silver but the person is still in a copy and the change feed — every downstream copy and the CDF files must be purged too (`PRO-S7-O5`)

## Defaults and limits

| Setting | Default or limit | Note |
|---|---|---|
| `delta.deletedFileRetentionDuration` | 7 days | `VACUUM` keeps files younger than this; time travel past it is refused |
| `VACUUM ... RETAIN n HOURS` | refused below the table's retention (168 h by default) | set the table property lower first; the session check cannot be turned off on serverless |
| `delta.logRetentionDuration` | 30 days | must be at least `deletedFileRetentionDuration` |
| `delta.enableDeletionVectors` | on for new tables | so a `DELETE` leaves the row in the old file |
| `sha2(expr, bitLength)` | 224, 256, 384, 512; `0` means 256 | any other length returns `NULL` |
| `aes_encrypt` mode | `GCM` (random IV, non-deterministic) | key must be 16, 24 or 32 bytes; `ECB` is deterministic |
| Secret scopes | 1,000 per workspace | names up to 128 characters |
| Secrets | 1,000 per scope, 128 KB per value | creator of a scope gets `MANAGE` |
| OAuth M2M access token | valid one hour | refreshed automatically by the CLI and SDKs |
| Service principal OAuth secret | lifetime up to 730 days | set when the secret is generated |

## Least privilege with ACLs — `PRO-S7-O1`

Unity Catalog securables (catalog, schema, table, view, volume, function) carry
privileges granted to users, groups and service principals, and privileges
**inherit downward**: `SELECT` on a schema applies to every table in it,
including tomorrow's. Least privilege in practice:

- Grant to **groups**, not people; membership changes, grants do not.
- Grant at the level that matches the need: a reader of one table gets `SELECT`
  on the table plus the `USE CATALOG` and `USE SCHEMA` needed to reach it,
  nothing wider.
- Owners have everything implicitly and can grant; an object's owner is the one
  grant you cannot see in `information_schema.*_privileges`.
- Workspace objects (notebooks, folders, jobs) have their own ACLs
  (`CAN_READ`, `CAN_RUN`, `CAN_EDIT`, `CAN_MANAGE` on notebooks; `CAN_VIEW`,
  `CAN_MANAGE_RUN`, `IS_OWNER`, `CAN_MANAGE` on jobs) with the same folder
  inheritance; a service principal that must run a job needs `CAN_MANAGE_RUN`,
  not ownership.

```sql
GRANT USE CATALOG ON CATALOG prod TO `analysts`;
GRANT USE SCHEMA  ON SCHEMA  prod.gold TO `analysts`;
GRANT SELECT      ON TABLE   prod.gold.orders TO `analysts`;
SHOW GRANTS ON TABLE prod.gold.orders;
```

```bash
# Workspace ACLs are set through the permissions API, not GRANT
databricks permissions get-permission-levels jobs <job-id>   # CAN_VIEW, CAN_MANAGE_RUN, CAN_MANAGE, IS_OWNER
databricks permissions update jobs <job-id> --json \
  '{"access_control_list":[{"service_principal_name":"<app-id>","permission_level":"CAN_MANAGE_RUN"}]}'
```

The job owner matters for more than permissions: `IS_OWNER` means the job runs
**with the owner's credentials** unless a `run_as` identity is set, and only a
workspace admin can change it. Production jobs run as a service principal.

### Compute policies

Policy enforcement for compute is a **compute policy**: a JSON definition that
pins, limits or hides cluster attributes, plus a `CAN_USE` permission deciding
who may create compute with it. Rule types: `fixed` (with `hidden` to remove it
from the form) and `forbidden` prevent configuration; `allowlist`, `blocklist`,
`regex`, `range` and `unlimited` limit it, and the limiting types accept a
`defaultValue` and `isOptional`.

```json
{
  "data_security_mode":      {"type": "fixed", "value": "DATA_SECURITY_MODE_STANDARD"},
  "autotermination_minutes": {"type": "range", "maxValue": 60, "defaultValue": 30},
  "node_type_id":            {"type": "allowlist", "values": ["i3.xlarge", "i3.2xlarge"]},
  "custom_tags.cost_center": {"type": "fixed", "value": "finance"},
  "instance_pool_id":        {"type": "forbidden", "hidden": true}
}
```

The point for the exam: users without unrestricted cluster creation can only
create compute through a policy they have `CAN_USE` on, so the policy *is* the
enforcement. Built-in families (Personal Compute, Shared Compute, Job Compute,
Power User Compute) are starting points you override, not rules you write from
scratch.

> **Measured on Free Edition:** `databricks cluster-policies list` returns the
> five built-in policies (Personal, Power User, Shared, Job and Legacy Shared
> Compute) even though there is no classic compute to apply them to; the only
> permission level on a policy is `CAN_USE`.

### Secrets end to end

A credential never belongs in a notebook, a job parameter or a table. It goes
in a **secret scope**, the scope has an ACL, and code reads it at run time:

```bash
databricks secrets create-scope pii                         # creator gets MANAGE
databricks secrets put-secret pii salt --string-value '...'
databricks secrets put-acl pii data-engineers READ          # READ < WRITE < MANAGE
databricks secrets list-acls pii
```

```python
salt = dbutils.secrets.get(scope="pii", key="salt")   # printing it shows [REDACTED]
```

```sql
SELECT sha2(concat(secret('pii', 'salt'), email), 256) FROM bronze.subjects;
SELECT try_secret('pii', 'missing');                  -- NULL instead of an error
```

Permissions are `READ` (read and list), `WRITE` (read and write) and `MANAGE`
(also change the ACL); the strongest one a principal holds wins. **Redaction is
display-only**: it replaces the literal value with `[REDACTED]` in notebook and
SQL output, but anyone who can read the scope can transform the value (reverse
it, split it, write it to a table) and see it. The ACL is the control;
redaction only stops accidents. The values are never readable through the REST
API outside `dbutils`.

> **Measured on Free Edition:** `SELECT secret('scope','salt')` on a SQL
> warehouse returned `[REDACTED]`, while `length(secret(...))` returned the real
> length (19) and a `sha2` over it matched the hash of the plain value: the
> function feeds the real value to expressions and redacts only what is shown.

### Service principals and OAuth

A pipeline identity is a **service principal**, not a person's account and not a
personal access token. It authenticates with **OAuth machine-to-machine**: an
OAuth secret (client id plus secret, lifetime up to 730 days) is exchanged for
access tokens that last one hour and are refreshed automatically.

```bash
export DATABRICKS_HOST=https://<workspace-url>
export DATABRICKS_CLIENT_ID=<service-principal-application-id>
export DATABRICKS_CLIENT_SECRET=<oauth-secret>
databricks jobs list          # the CLI and SDKs pick OAuth M2M up from these
```

Grant the principal what the job needs (`CAN_MANAGE_RUN` on the job, Unity
Catalog privileges on its tables) and set it as the job's `run_as`.

## Row filters and column masks — `PRO-S7-O2`

Both are SQL functions attached to a table:

```sql
CREATE FUNCTION mask_salary(v DOUBLE) RETURN
  CASE WHEN is_account_group_member('hr') THEN v ELSE NULL END;
ALTER TABLE employees ALTER COLUMN salary SET MASK mask_salary;

-- current_user_region() is a lookup function you write, not a built-in
CREATE FUNCTION region_filter(region STRING) RETURN
  is_account_group_member('hr') OR region = current_user_region();
ALTER TABLE employees SET ROW FILTER region_filter ON (region);
```

A **column mask** decides what a viewer sees in a column; a **row filter**
decides which rows they see at all. They apply at query time to everyone,
including the owner, so keep a **break-glass principal** in every rule: a policy
that excludes everyone is unauditable and unrecoverable. And remember what they
are not: a mask can be dropped by the table's owner or anyone holding `MANAGE`
on it, so it hides
data from readers; it does not remove it.

The rest of the syntax the exam uses:

```sql
-- a mask that reads another column: the masked column is always the first argument
ALTER TABLE employees ALTER COLUMN salary SET MASK mask_by_region USING COLUMNS (region);

-- declared at creation time
CREATE TABLE employees (
  id INT,
  ssn STRING MASK mask_ssn,
  region STRING
) WITH ROW FILTER region_filter ON (region);

-- a filter that takes no columns
ALTER TABLE employees SET ROW FILTER only_admins ON ();

-- removing them
ALTER TABLE employees DROP ROW FILTER;
ALTER TABLE employees ALTER COLUMN salary DROP MASK;

-- where they show up
DESCRIBE TABLE EXTENDED employees;      -- "Row Filter" and "# Column Masks" rows
```

`is_account_group_member()` checks **account** groups and is the one to use;
`is_member()` checks workspace-local groups. A table has at most one row filter,
so combine conditions in one function. Attaching a function needs `EXECUTE` on
it as well as owner or `MANAGE` on the table. Filters and masks go on tables only, not on
views; to filter a view, use a dynamic view or filter the base table. For rules
across many tables, **ABAC policies** (`CREATE POLICY`, driven by governed tags,
attached at catalog or schema level) replace per-table functions.

**Downstream copies.** A filter or mask does not travel with the data: a `CREATE
TABLE ... AS SELECT` from a protected table stores whatever the writer could see,
with no policy attached. Run by a restricted user it stores masked values; run by
a privileged job it stores raw values in an unprotected table.

> **Measured on Free Edition:** the table owner saw only the filtered rows and
> the masked values, confirming the policy binds the owner. A CTAS from the
> masked and filtered table stored only the two rows the owner could see, with
> `-1.0` (the masked value) as the salary. `is_member('admins')` returned `true` while
> `is_account_group_member('admins')` returned `false`: the workspace `admins`
> group is not an account group. Time travel on a masked table fails with
> `COLUMN_MASKS_FEATURE_NOT_SUPPORTED.TIME_TRAVEL`.

## Anonymisation and pseudonymisation — `PRO-S7-O3`

| Technique | Reversible? | Keeps joinability | Keeps analytics |
|---|---|---|---|
| **Hashing** | no | yes: same input, same hash | grouping only |
| **Tokenisation** | yes, with the vault | yes | grouping only |
| **Suppression** | no | no | nothing |
| **Generalisation** | no | no | aggregate patterns survive |

Choose by what the data still has to do. Hashing an id keeps joins working;
suppressing it does not. **Hashing alone is not anonymisation when the input
space is small**: a hashed postcode or date of birth can be brute-forced by
hashing every possible value. **Salt** low-entropy values and keep the salt out
of the dataset. Generalisation trades precision for privacy: a birth date
becomes a decade, a postcode a region.

The functions, and which one fits:

```sql
SELECT
  sha2(concat(secret('pii', 'salt'), email), 256) AS email_hash,  -- 64 hex chars; bitLength 224/256/384/512, 0 = 256
  md5(email)                                     AS weak_hash,   -- 32 hex chars; not for PII
  xxhash64(email)                                AS bucket,      -- fast, non-cryptographic: partitioning, not privacy
  mask(phone)                                    AS phone_masked,-- upper -> X, lower -> x, digit -> n by default
  aes_encrypt(ssn, secret('pii', 'aes_key'))     AS ssn_enc,     -- reversible; mode GCM by default
  date_trunc('YEAR', birth_date)                 AS birth_year   -- generalisation
FROM bronze.subjects;

SELECT cast(aes_decrypt(ssn_enc, secret('pii', 'aes_key')) AS STRING) FROM silver.subjects;
SELECT try_aes_decrypt(ssn_enc, secret('pii', 'wrong_key')) FROM silver.subjects;   -- NULL, not an error
```

**Tokenisation** in Databricks is a pattern, not a function: a vault table maps
each real value to a random token (`uuid()`), the analytic tables carry only the
token, and the vault sits in a schema only the re-identification role can read.
Erasing a person is then deleting one vault row. **Encryption** is the other
reversible option; with the default `GCM` mode the same input encrypts
differently each time, so encrypted columns do not join. `ECB` is deterministic
and joinable, and leaks equality for the same reason.

> **Measured on Free Edition:** `sha2(x, 0)` equals `sha2(x, 256)`;
> `sha2(x, 128)` returns `NULL`. Two `aes_encrypt` calls on the same value and
> key differed in `GCM` and matched in `ECB`. A 5-byte key failed with
> `AES_KEY_LENGTH`; decrypting with the wrong key failed with
> `AES_CRYPTO_ERROR` (`Tag mismatch!`), and `try_aes_decrypt` returned `NULL`.

## A compliant pipeline that finds PII — `PRO-S7-O4`

Masking the columns you *know* hold PII is the easy half. Free text is where it
hides: email addresses, phone numbers and names inside a `notes` field that a
column-by-column approach never inspects. A compliant pipeline detects as well
as masks:

- Pattern detection with `regexp_replace` for emails and phone numbers, applied
  to every free-text column, in batch and in the streaming path alike.
- Pseudonymise the identifier (salted hash) so records stay groupable, and drop
  the raw identifier and name columns rather than masking them.
- The same transformation function serves batch and streaming: a
  `DataFrame.transform` step works on a static read and on `readStream`.

```python
from pyspark.sql import functions as F

EMAIL = r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
PHONE = r"\+?\d[\d\s().-]{7,}\d"

def scrub(df):
    salt = dbutils.secrets.get("pii", "salt")
    return (df
        .withColumn("notes", F.regexp_replace("notes", EMAIL, "<EMAIL>"))
        .withColumn("notes", F.regexp_replace("notes", PHONE, "<PHONE>"))
        .withColumn("subject_hash", F.sha2(F.concat(F.lit(salt), "subject_id"), 256))
        .drop("subject_id", "email", "name"))

spark.read.table("bronze.tickets").transform(scrub).write.mode("overwrite").saveAsTable("silver.tickets")

(spark.readStream.table("bronze.tickets").transform(scrub)
    .writeStream.option("checkpointLocation", "/Volumes/main/pii/chk/tickets")
    .trigger(availableNow=True).toTable("silver.tickets_stream"))
```

Scrub **before** the first table anyone else can read: PII written to bronze
and masked in silver still has to be erased from bronze, its history and its
change feed. `ai_mask(text, array('email', 'phone'))` detects entities with a
model rather than a regex; it catches names a pattern cannot, at the cost of
being a model call per row.

## Retention and purging — `PRO-S7-O5`

| Requirement | Satisfied by |
|---|---|
| "Analysts must not see this" | a mask or a filter |
| "We must not hold this after N days" | deletion |
| "This person asked to be forgotten" | deletion |

**Masking is not deletion.** A masked row is a retained row. And a Delta
`DELETE` removes rows from the current version only; earlier versions still hold
them, which is what time travel is for. A **retention policy is a cutoff per
category**; one cutoff for everything either keeps marketing data too long or
deletes transaction logs a regulator requires you to hold.

### Erasure that actually erases

New tables have **deletion vectors** on, so a `DELETE` does not rewrite the file
holding the row: it writes a small vector marking the row deleted, and the
original file stays **in the current version**. `VACUUM` only removes files no
version references, so it can never remove that one. The full sequence:

```sql
-- 1. logical delete (writes a deletion vector)
DELETE FROM records WHERE subject_id IN (SELECT subject_id FROM erasure_requests);

-- 2. rewrite every file that carries a deletion vector, without the deleted rows
REORG TABLE records APPLY (PURGE);

-- 3. stop history from protecting the old files
ALTER TABLE records SET TBLPROPERTIES (delta.deletedFileRetentionDuration = 'interval 0 hours');

-- 4. remove the unreferenced files: old data files, deletion vectors, _change_data files
VACUUM records;                -- or VACUUM records RETAIN 0 HOURS

-- 5. put the default back for normal operation
ALTER TABLE records SET TBLPROPERTIES (delta.deletedFileRetentionDuration = 'interval 7 days');
```

`VACUUM ... RETAIN 0 HOURS` on its own is refused (`DELTA_VACUUM_RETENTION_PERIOD_TOO_SHORT`)
while the table property is still 7 days; lowering the property first is what
makes it legal. Retaining zero hours breaks time travel and can disrupt
concurrent readers: right for an erasure request, wrong as a default. In
practice most teams batch erasures and let the scheduled `VACUUM` at the normal
7 days finish the job, which meets a "within 30 days" requirement without
touching retention.

![Why a DELETE leaves the row on storage, and what finally removes it](visual:delta-commit-log?h=900)

**Change data feed.** If the table has `delta.enableChangeDataFeed = true`, the
deleted row is also in the change feed, which is exactly what CDF is for. With
deletion vectors the feed is derived from the vectors; without them the
`DELETE` writes the row into a `_change_data` file. Either way it disappears
only when `VACUUM` removes those files.

**Downstream copies.** An erasure covers every place the row went: silver and
gold tables built from it, materialized views and streaming tables (which also
need `REORG ... APPLY (PURGE)`), other teams' CTAS copies, exports. Delete in
bronze first and propagate: a streaming read of a table that had a `DELETE`
fails unless it uses `skipChangeCommits`, so downstream tables must be purged
by their own job, not assumed to follow.

```sql
-- confirm the purge reached storage
DESCRIBE HISTORY records;      -- REORG shows numDeletionVectorsRemoved; VACUUM END shows numDeletedFiles
SELECT * FROM records VERSION AS OF 1;   -- now refused
```

> **Measured on Free Edition:** a `DELETE` of one row from a 100-row table
> wrote one deletion vector and removed no files (`numRemovedFiles = 0`).
> `REORG ... APPLY (PURGE)` removed that vector and rewrote the file. With the
> retention property at `interval 0 hours`, a plain `VACUUM` deleted two files
> (old data file and deletion vector), and both time travel and `table_changes`
> then failed with `DELTA_UNSUPPORTED_TIME_TRAVEL_BEYOND_DELETED_FILE_RETENTION_DURATION`.
> With deletion vectors off, the same `DELETE` removed one file and added one
> `_change_data` file (`numAddedChangeFiles = 1`); `VACUUM RETAIN 0 HOURS` then
> deleted both. `SET spark.databricks.delta.retentionDurationCheck.enabled = false`
> is refused on serverless (`CONFIG_NOT_AVAILABLE`), so the table property is the
> only way to go below 7 days there.

### A purge job per category

```sql
-- retention cutoffs live in a table, not in code
DELETE FROM records r
WHERE EXISTS (
  SELECT 1 FROM retention_policy p
  WHERE p.record_type = r.record_type
    AND r.created_on < date_sub(current_date(), p.retain_days)
);
REORG TABLE records APPLY (PURGE);
-- the scheduled VACUUM at default retention removes the files within 7 days
```

## Further reading

Official documentation for what this section tests, one link per topic:

- [Access control](https://docs.databricks.com/aws/en/security/auth/access-control/) — workspace ACLs vs Unity Catalog privileges.
- [Compute policies](https://docs.databricks.com/aws/en/admin/clusters/policies) — creating policies and `CAN_USE`.
- [Compute policy reference](https://docs.databricks.com/aws/en/admin/clusters/policy-definition) — rule types and attributes.
- [Row filters and column masks](https://docs.databricks.com/aws/en/data-governance/unity-catalog/filters-and-masks) — syntax, `MANAGE`, evaluation.
- [Dynamic views](https://docs.databricks.com/aws/en/views/dynamic) — the older mechanism and when it still applies.
- [Secret management](https://docs.databricks.com/aws/en/security/secrets/) — scopes, ACLs and redaction.
- [`secret` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/secret) — reading a secret from SQL.
- [Service principals](https://docs.databricks.com/aws/en/admin/users-groups/service-principals) — pipeline identities and OAuth.
- [OAuth machine-to-machine](https://docs.databricks.com/aws/en/dev-tools/auth/oauth-m2m) — client secrets, token lifetime, environment variables.
- [`aes_encrypt`](https://docs.databricks.com/aws/en/sql/language-manual/functions/aes_encrypt) — modes, key lengths, padding.
- [`sha2`](https://docs.databricks.com/aws/en/sql/language-manual/functions/sha2) and [`mask`](https://docs.databricks.com/aws/en/sql/language-manual/functions/mask) — hashing and character masking.
- [Privacy](https://docs.databricks.com/aws/en/security/privacy/) — the privacy documentation home.
- [GDPR and CCPA compliance with Delta](https://docs.databricks.com/aws/en/security/privacy/gdpr-delta) — erasure that actually erases.
- [Deletion vectors](https://docs.databricks.com/aws/en/delta/deletion-vectors) — soft deletes and how to apply them.
- [REORG TABLE](https://docs.databricks.com/aws/en/sql/language-manual/delta-reorg-table) — `APPLY (PURGE)`.
- [VACUUM](https://docs.databricks.com/aws/en/delta/vacuum) — retention, and why a delete is not final until it runs.
- [Change data feed](https://docs.databricks.com/aws/en/delta/delta-change-data-feed) — `_change_data` files and retention.
- [Resource limits](https://docs.databricks.com/aws/en/resources/limits) — secret scopes and other workspace limits.
- [Privileges and securable objects](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-privileges) — the privilege reference.
- [Attribute-based access control](https://docs.databricks.com/aws/en/data-governance/unity-catalog/abac/) — policies driven by tags.

Videos for another angle on the hard parts (channel, length):

- [Unity Catalog, Delta Sharing and Data Mesh on Databricks Lakehouse](https://www.youtube.com/watch?v=75QGOtqBj2k) — Databricks, 36 min. Governance and security in context.
