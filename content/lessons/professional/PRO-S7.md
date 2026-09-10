# Ensuring Data Security and Compliance — 10%

Two mistakes run through this section: treating a mask as deletion, and assuming
you know where the sensitive data is. The exam asks you to choose the right
control for the requirement, and to notice when the cheap control is not enough.

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

## Retention and purging — `PRO-S7-O5`

| Requirement | Satisfied by |
|---|---|
| "Analysts must not see this" | a mask or a filter |
| "We must not hold this after N days" | deletion |
| "This person asked to be forgotten" | deletion |

**Masking is not deletion.** A masked row is a retained row. And a Delta
`DELETE` removes rows from the current version only; earlier versions still hold
them, which is what time travel is for. To make an erasure final, expire the
history and vacuum:

```sql
DELETE FROM records WHERE subject_id IN (SELECT subject_id FROM erasure_requests);
ALTER TABLE records SET TBLPROPERTIES (delta.deletedFileRetentionDuration = 'interval 0 days');
VACUUM records RETAIN 0 HOURS;
```

Retaining zero hours breaks time travel and can disrupt concurrent readers: right
for an erasure request, wrong as a default. A **retention policy is a cutoff per
category**; one cutoff for everything either keeps marketing data too long or
deletes transaction logs a regulator requires you to hold.

## Further reading

Official documentation for what this section tests, one link per topic:

- [Access control](https://docs.databricks.com/aws/en/security/auth/access-control/) — workspace ACLs vs Unity Catalog privileges.
- [Row filters and column masks](https://docs.databricks.com/aws/en/data-governance/unity-catalog/filters-and-masks) — syntax, `MANAGE`, evaluation.
- [Dynamic views](https://docs.databricks.com/aws/en/views/dynamic) — the older mechanism and when it still applies.
- [Secret management](https://docs.databricks.com/aws/en/security/secrets/) — scopes, ACLs and redaction.
- [Service principals](https://docs.databricks.com/aws/en/admin/users-groups/service-principals) — pipeline identities and OAuth.
- [Privacy](https://docs.databricks.com/aws/en/security/privacy/) — the privacy documentation home.
- [GDPR and CCPA compliance with Delta](https://docs.databricks.com/aws/en/security/privacy/gdpr-delta) — erasure that actually erases.
- [VACUUM](https://docs.databricks.com/aws/en/delta/vacuum) — retention, and why a delete is not final until it runs.
- [Privileges and securable objects](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-privileges) — the privilege reference.
- [Attribute-based access control](https://docs.databricks.com/aws/en/data-governance/unity-catalog/abac/) — policies driven by tags.

Videos for another angle on the hard parts (channel, length):

- [Unity Catalog, Delta Sharing and Data Mesh on Databricks Lakehouse](https://www.youtube.com/watch?v=75QGOtqBj2k) — Databricks, 36 min. Governance and security in context.
