# The optional classic-compute track

Free Edition is serverless-only. A handful of exam objectives are *about* classic
compute — cluster sizing and cost models, startup failures, library conflicts,
out-of-memory diagnosis, cluster log delivery — and no amount of serverless
practice covers them.

Rather than quietly demote those to reading material, this track provides
**optional** hands-on labs for them, run on a Premium-tier workspace.

> **Nothing on the required path depends on this track.** You can pass both exams'
> content in this repo without ever opening a paid workspace. This is here so the
> gap is closable, not so it's compulsory.

---

## Read this before you start a trial

The Azure option is a workspace created with the pricing tier
**"Trial (Premium — 14-Days Free DBUs)"**. The name is precise, and the precision
matters:

- **The DBUs are free. The infrastructure is not.** The VMs, managed disks,
  storage and networking behind a classic cluster are billed to your cloud
  subscription for the entire trial. **These labs cost real money** — modest, but
  not zero.
- It requires a **pay-as-you-go** subscription. An **Azure Free Trial subscription
  will not work**; you must convert to pay-as-you-go and remove the spending limit.
- You may need to **request a vCPU quota increase** for your region before a
  cluster will start.
- Equivalent 14-day trials exist on AWS and GCP. This track is written against
  *capability* (Premium tier + classic clusters), not against a specific cloud.
- Any operational workspace you already have access to works just as well, and
  costs you nothing extra.

**The clock starts when you create the workspace.** Don't open a trial until
you're ready to work through the labs — otherwise you'll spend the window waiting.

---

## The one way this gets expensive

A forgotten running cluster. Everything else here is pocket change.

Every lab in this track:

- opens with a **cost banner** stating what it starts and roughly what it costs
- uses the **smallest viable node type**, single-node wherever the lesson allows
- sets **auto-termination to 10–15 minutes**
- ends with a **teardown cell** that deletes the cluster and verifies it's gone

Before you close the laptop:

```bash
databricks clusters list --profile TRIAL     # expect nothing RUNNING
```

Keep the trial on its own CLI profile (`TRIAL`) so it can never be confused with
your Free Edition workspace:

```bash
databricks auth login --host <trial-workspace-url> --profile TRIAL
```

---

## What the labs cover

Each maps to objectives tagged `optional_classic_lab: true` in
`content/objectives/*.yaml`.

| Objective | Free Edition | What the classic lab adds |
| --- | --- | --- |
| `ASSOC-S1-O2` compute services, limits, cost models | theory only | Compare all-purpose vs job vs SQL warehouse; autoscaling, spot instances, Photon; read the cost model off real configurations |
| `ASSOC-S6-O5` startup failures, library conflicts, OOM | theory only | Deliberately break things — a bad init script, conflicting pinned library versions, a forced driver OOM — then read the real errors |
| `ASSOC-S6-O3` Spark UI stage metrics | partial | Full Spark UI: induce skew and disk spill, diagnose from stage-level metrics |
| `PRO-S1-O2` third-party libraries | partial | Cluster-scoped libraries and init scripts; resolve a genuine dependency conflict |
| `PRO-S1-O10` env configs, high-memory notebook tasks | partial | Memory-optimised job compute, and verifying the config actually took effect |
| `PRO-S5-O2` Spark UI monitoring | partial | Spark UI against a long-running classic job |
| `PRO-S9-O1` diagnostics from cluster logs | partial | Cluster log delivery to storage, then root-causing a failure from the logs |

For the `partial` rows, do the Free Edition lab first. Serverless teaches the
concept; classic compute exposes the diagnostic surface.

**The deliberate-failure labs are the most valuable ones here.** Reading about an
OOM teaches you the words; watching a driver die because you called `collect()` on
something too big teaches you the shape of the problem.

---

## Deploying to the trial workspace

The bundle carries a separate `classic` target so nothing can be accidentally
deployed to the wrong place:

```bash
databricks bundle validate -t classic --profile TRIAL
databricks bundle deploy   -t classic --profile TRIAL
```

## Ending the trial

1. Run every teardown cell, or delete clusters from the UI.
2. `databricks clusters list --profile TRIAL` — confirm nothing is running.
3. Delete the workspace in your cloud portal. **Deleting the workspace is what
   stops the infrastructure billing** — letting the trial lapse does not.
4. `rm` the `TRIAL` profile from `~/.databrickscfg`.
