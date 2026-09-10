# Databricks Free Edition: what this repo can and can't do on it

Free Edition is the baseline target, so every limit it imposes shapes the content.
This page records those limits, which ones were **measured** against a live
workspace, and exactly which exam objectives they affect.

Verified 2026-09-09 against an AWS-backed Free Edition workspace.

---

## Platform limits

| Capability | Limit | Verified? |
| --- | --- | --- |
| Databricks Apps | **3 per account.** Each **auto-stops 24 hours** after being started, updated or redeployed | Measured — deployed and ran one |
| App builds | Remote `npm install` and remote build **work** — npm/PyPI are reachable | **Measured** (see below) |
| Compute | **Serverless only.** No custom compute configuration | Documented |
| SQL warehouse | **One**, fixed at **2X-Small** | Measured — `Serverless Starter Warehouse`, 2X-Small |
| Lakeflow Jobs | **5 concurrent job tasks** | Documented |
| Lakeflow Pipelines | **1 active pipeline per type** | Documented |
| Lakebase | **1 project per account**, scale-to-zero | Documented |
| Languages | **No R, no Scala** | Documented — irrelevant, both exams are Python + SQL |
| Egress | Docs say "a limited set of trusted domains", not customisable. **Measured looser than that** — see below | Partly measured |
| DABs | Work. Deploy from a local machine, use serverless, avoid job clusters | **Measured** — validate + deploy + destroy all succeeded |
| Catalogs present | `system`, `samples`, `workspace`, `dbacademy` | Measured |

### The egress question, settled

Free Edition's docs say only that outbound access is limited to "a limited set of
trusted domains" without naming them, and the list can't be extended. Since
Databricks Apps install dependencies from `registry.npmjs.org` at build time, this
was a genuine go/no-go risk for the whole app plan.

It was tested rather than assumed. A minimal AppKit app deployed cleanly —
`Installing packages` → `Building app` → `App started successfully`, reaching
`RUNNING`. **npm egress works.** Details in
[architecture.md](architecture.md#decision-3-appkit-on-free-edition--verified-not-assumed).

### Egress is less restricted than the docs imply — but don't rely on it

The limitations page says outbound access is limited to "a limited set of trusted
domains". Two measurements complicate that:

- **npm and PyPI are reachable** — a Databricks App built and started successfully,
  which requires `registry.npmjs.org`.
- **An outbound JDBC connection to a public Postgres on port 5432 succeeded** from
  serverless compute (2026-09-09).

The second is the surprising one. It may depend on account-level verified internet
access, which there is no API to check for, so **it is not something to build a
required lab on.** Treat reachable egress as a bonus that some learners have and
others may not: every lab on the required path must work with no external network
at all. Where a lesson wants to show an external source, make it an optional
variant and say plainly that it may not work for everyone.

### The 24-hour auto-stop

The single most surprising limit. An app stops ~24h after its last start/update/
redeploy, so this is a study tool you bring up when you need it, not a site to
hand to other people.

```bash
databricks apps start de-prep-study --profile FREE                  # restart without redeploying
databricks apps get de-prep-study --profile FREE -o json | jq .app_status.state
```

Or merge anything to `main`: the deploy workflow redeploys, which also restarts it.
Progress lives in Lakebase, so a stopped app loses nothing.

### The study app

`app/` deploys as the `de-prep-study` app through the bundle, **from CI only**.
Two rules that come from how Lakebase and Databricks Apps hand out ownership:

- **Deploy before running locally.** The app's service principal creates the
  `study` schema on its first start and thereby owns it. If `npm run dev` runs
  against the database first, *your* role owns the schema and the deployed app
  gets `permission denied` forever (recovery is drop-and-redeploy, which loses
  data). `app/README.md` has the check to run first.
- **Never `bundle deploy` from a laptop.** Development mode prefixes resource
  names, so it would create a second app and use one of the three slots.

Confirmed on the first deploys (2026-09-10):

- The bundle interpolates `${workspace.file_path}` into the app's environment
  (`DE_PREP_FILES_ROOT`), and `bundle validate --strict -t free` accepts the app.
- The CI service principal needs **CAN_MANAGE on the Lakebase project** to attach
  it to the app; without it `bundle deploy` fails with `403 PERMISSION_DENIED`
  (`docs/ci-cd.md`, step 2b).
- `bundle deploy` alone creates the app with no compute: it sat `STOPPED` with no
  deployment. `deploy.yml` therefore runs `bundle run study_app` afterwards, which
  deploys the uploaded source and starts the app.

Still to confirm from inside the running app: that a user can open notebooks under
the service principal's bundle folder from the app's links, and that the relative
links in the notebooks' closing cell resolve.

---

## Objective coverage

Most objectives are fully practisable here. The exceptions are tagged in
`content/objectives/*.yaml` and rendered into the objective maps, so nothing is
silently downgraded.

An **absent** tag is a positive claim that the objective needs no special
treatment. Only exceptions carry tags.

### Theory only on Free Edition

Not practisable here at all. Both have an optional classic-compute lab.

| Objective | Why |
| --- | --- |
| `ASSOC-S1-O2` — compute services, limits, cost models | Serverless-only, no custom compute config: there is nothing to compare |
| `ASSOC-S6-O5` — cluster startup failures, library conflicts, OOM | There are no clusters to fail to start |

### Settled by measurement, 2026-09-09

| Objective | Finding |
| --- | --- |
| `ASSOC-S2-O4` — Lakeflow Connect | **partial.** Standard connectors (Auto Loader / `read_files` over a UC volume) are fully hands-on. Managed connectors cannot be created: the database ones need an ingestion gateway on classic compute, which does not exist here. Cover them as a dry-run spec walkthrough. |
| `ASSOC-S2-O5` — JDBC ingestion | **full** — better than expected. `spark.read.format("jdbc")` works on serverless, and the workspace's own SQL warehouse serves as the JDBC source, so no external database and no Lakebase project is needed. Secret scopes work too, so `dbutils.secrets.get` is available. |
| `PRO-S2-O1` — file formats | **full.** Every format the objective names round-trips on serverless: Parquet, ORC, Avro, JSON, CSV, XML (`format("xml")` with `rowTag`), `text` and Delta all write **and** read; `binaryFile` reads, returning `path`, `modificationTime`, `length`, `content`. No library installs needed. |
| `PRO-S2-O2` — append-only batch + streaming | **full.** Auto Loader (`cloudFiles`) over a UC volume writing to a table with `trigger(availableNow=True)` works, checkpoints resume correctly, and a Delta table can be read as a stream. An `UPDATE` on the source makes the downstream stream fail with `DELTA_SOURCE_TABLE_IGNORE_CHANGES`; `skipChangeCommits` clears it. |
| `PRO-S4-O1` — Delta Sharing | **partial.** The whole provider side works: `CREATE SHARE`, `ALTER SHARE ADD TABLE/VOLUME` with aliases and history options, `CREATE RECIPIENT` (DATABRICKS auth), `GRANT SELECT ON SHARE`, `SHOW ALL IN SHARE`, `SHOW GRANTS ON SHARE`. Open-protocol (`TOKEN`) recipients are refused — *External Delta Sharing is not enabled on the metastore*, `delta_sharing_scope = INTERNAL`. The consumer side needs a second metastore: sharing to your own produces no provider. |
| `PRO-S4-O2` — Lakehouse Federation | **partial.** All DDL and governance works — `CREATE CONNECTION`, `CREATE FOREIGN CATALOG`, `GRANT USE CONNECTION`, `system.information_schema.connections`, and the rule that a connection cannot be dropped while a foreign catalog uses it. **None of it validates anything**: a connection to a nonexistent host is accepted. The query path fails with `FAILED_JDBC.CONNECTION`, including a `databricks`-type connection to this workspace's own SQL warehouse. A Lakebase Postgres target is untested — one project per account, reserved for the study app. |
| `PRO-S4-O3` — share to any platform | **theory only.** Needs the open sharing protocol, which needs a `TOKEN` recipient. Refused here. |
| `PRO-S5-O1` — system tables | **full.** Thirteen schemas readable: access, ai, ai_gateway, alert, billing, compute, information_schema, lakeflow, mlflow, query, serving, storage, tags. `system.billing.usage` and `system.access.audit` both return rows. |

### Delta Sharing constraints worth knowing before you plan a lab

Measured 2026-09-09, all of them silent or surprising:

- **Sharing checks traversal explicitly.** `ALTER SHARE ... ADD TABLE` fails with
  `PERMISSION_DENIED` unless you hold `USE CATALOG` and `USE SCHEMA` — owning the
  table is not enough.
- **A plain `ADD TABLE` shares the history.** `history_sharing` defaults to `ENABLED`.
  Nothing warns you; `SHOW ALL IN SHARE` tells you only if you read the column.
- **Deletion vectors block history-free sharing.** `WITHOUT HISTORY` is refused with
  `DS_UNSUPPORTED_DELTA_TABLE_FEATURES`. The remedy is
  `delta.enableDeletionVectors = false` **then** `REORG TABLE ... APPLY (PURGE)` —
  turning the property off alone does not remove the vectors already written.
- **`WITH CHANGE DATA FEED` is refused entirely**, because tables here are encrypted
  with Databricks-managed keys. `cdf_shared` follows the table's own
  `delta.enableChangeDataFeed` property instead, so CDF sharing *is* achievable —
  just not through the documented clause.
- **An alias is permanent.** `ALTER SHARE ... REMOVE TABLE` takes the *shared* name,
  so an object added `AS partner.x` cannot be removed by its source path.
- **A shared table cannot be dropped** — `DELTA_SHARING_SECURABLE_DELETE_BLOCKED.BY_SHARES`.
- **`SHOW SHARES` names its first column `share`, not `name`.**

### Governed tags: a footgun

`CREATE GOVERNED TAG <key>` works, and creates the key with an **empty allowed-value
list**. No SQL form was found to populate it (`ALTER GOVERNED TAG ... ALLOWED VALUES`
does not parse). While it exists, ordinary `SET TAGS` on that key is rejected
**everywhere in the metastore** — so creating one casually breaks unrelated tagging
until you `DROP GOVERNED TAG` it.

### A cast that fails may never run

ANSI mode is on (`spark.sql.ansi.enabled = true`), so an invalid cast raises
`CAST_INVALID_INPUT` — **when it executes.** Measured on serverless: `count()` over a
projection nothing consumes returns a number with no error, because the projection is
pruned before evaluation, and `filter(col.isNull())` over such a cast folds to a null
check on the source column and returns 0. The same expression `collect()`ed raises.

A small literal DataFrame behaves differently again: the cast is folded at plan time
and raises immediately. So a file-backed read is what reproduces the pruning.

**Consequence for content:** never treat "the query returned a number" as evidence a
cast is valid. Validate by materialising values, or with `try_cast` and an explicit
null count.

### Partly hands-on

| Objective | What's reachable | What isn't |
| --- | --- | --- |
| `ASSOC-S6-O3` — Spark UI stage metrics | Skew and spill can be induced | Spark UI depth on serverless |
| `PRO-S1-O2` — third-party libraries | Notebook-scoped `%pip`, serverless environments | Cluster-scoped libraries, init scripts |
| `PRO-S1-O10` — env/dependency configs | Retry and environment config | High-memory compute selection |
| `PRO-S4-O1` / `O3` — Delta Sharing | Creating shares and recipients | Completing a cross-account handshake — needs a second party |
| `PRO-S4-O2` — Lakehouse Federation | Possibly against own Lakebase Postgres | Arbitrary foreign sources |
| `PRO-S5-O2` — Query Profiler and Spark UI | Query Profiler on the warehouse | Spark UI depth |
| `PRO-S9-O1` — diagnostics | Query profiles | Cluster log delivery — no clusters |

### Feasibility not yet verified

Flagged `verify_in_workspace: true`. These need checking against the live
workspace before content is written — **the failure mode here is guessing**.

| Objective | Open question |
| --- | --- |
| `ASSOC-S6-O3` — Spark UI | How much stage-level detail is actually visible on serverless? |
| `ASSOC-S7-O4` — Unity Catalog ABAC | Is ABAC available on Free Edition? The feature has been moving quickly |
| `PRO-S4-O1..O3` — Sharing / Federation | How far can these go single-handed? |
| `PRO-S5-O1` — system tables | Which `system.*` schemas are enabled? Billing and audit especially |

---

## Working within the quotas

- **Pipelines:** one active per type. Declarative-pipeline labs run one at a time
  and each ends with a teardown step.
- **Jobs:** 5 concurrent tasks. Orchestration labs stay narrow — no wide fan-out
  DAGs; demonstrate branching and looping with a handful of tasks.
- **Apps:** 3 total. Delete throwaways immediately; the study app is one of them.
- **Warehouse:** a single 2X-Small, and it auto-stops. Expect a cold-start pause
  on the first query of a session.
- **Quota exhaustion is punitive:** exceeding compute quota shuts the workspace's
  compute down for the rest of the day, and in extreme cases the month. Keep lab
  datasets small — they're for learning mechanics, not for scale.
