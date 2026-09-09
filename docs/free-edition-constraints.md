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
| Egress | Restricted to trusted domains. **Not customisable** — network policies are Enterprise-tier | Documented |
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

### The 24-hour auto-stop

The single most surprising limit. An app stops ~24h after its last start/update/
redeploy, so this is a study tool you bring up when you need it, not a site to
hand to other people.

```bash
databricks bundle deploy --profile FREE     # redeploys and restarts
databricks apps get <app-name> --profile FREE -o json   # check app_status.state
```

Studying must never be blocked by a stopped app, so the content also builds to a
static export.

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

### Partly hands-on

| Objective | What's reachable | What isn't |
| --- | --- | --- |
| `ASSOC-S2-O5` — JDBC/ODBC ingestion | Possibly via the account's own Lakebase Postgres as the source | Arbitrary external databases — egress is restricted |
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
| `ASSOC-S2-O4` — Lakeflow Connect | Which connectors does Free Edition expose? Managed connectors target SaaS systems a learner won't have |
| `ASSOC-S2-O5` — JDBC | Can a serverless notebook reach the account's own Lakebase over JDBC? |
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
