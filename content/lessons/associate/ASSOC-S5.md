# Implementing CI/CD — 10%

Getting the same code into dev, test and prod without editing it on the way.

> **Names:** Git folders (Repos), Declarative Automation Bundles (Databricks Asset Bundles, DABs), Lakeflow Jobs (Workflows), Lakeflow Spark Declarative Pipelines (Delta Live Tables, DLT). The CLI still says `repos` and `bundle`, and old names still appear in distractors.

## What the exam asks

- A colleague's notebook changes are not in your Git folder after they merged — Pull, because a Git folder never updates itself (`ASSOC-S5-O1`)
- One bundle must write to `dev_catalog`, `test_catalog` and `prod_catalog` — a variable with a `default`, overridden under `targets.<name>.variables` (`ASSOC-S5-O2`)
- The same variable is set by `--var`, `BUNDLE_VAR_`, the target and the default — `--var` wins; the precedence order (`ASSOC-S5-O2`)
- A developer's deployed job should not fire on its schedule or collide with prod — `mode: development` prefixes names and pauses schedules (`ASSOC-S5-O3`)
- A production deploy must run under a non-human identity — `run_as` with `service_principal_name` (`ASSOC-S5-O3`)
- A CI step must fail on a misspelled key before anything is uploaded — `databricks bundle validate --strict` (`ASSOC-S5-O4`)

## Defaults and limits

| Setting | Default or limit | Note |
|---|---|---|
| Target used when `-t` is omitted | the one with `default: true` | with several targets and none marked, the CLI stops: `please specify target` |
| Variable type | string | `type: complex` is the only other value, for maps and lists |
| Variable with no `default` and no override | error at validate | `no value assigned to required variable` |
| Variable precedence | `--var` > `BUNDLE_VAR_<name>` > `variable-overrides.json` > target `variables` > `default` | first match wins |
| `mode: development` name prefix | `[dev <short_name>] ` | plus a `dev: <short_name>` tag on jobs and pipelines |
| `mode: development` schedules and triggers | `PAUSED` | set `pause_status: UNPAUSED` on one job to override |
| `mode: development` deployment lock | disabled | `bundle.deployment.lock.enabled: true` turns it back on |
| `mode: development` job concurrency | concurrent runs enabled (`max_concurrent_runs: 4` measured) | a job's own `max_concurrent_runs` overrides it |
| `mode: production` | requires `workspace.root_path`; checks `git.branch` | `--force` skips the branch check |
| `validate` unknown key | warning, exit 0 | `--strict` turns warnings into errors (exit 1) |
| Default bundle root | `/Workspace/Users/<deployer>/.bundle/<bundle>/<target>` | so two deployers never share a copy |
| New notebook format | IPYNB | source format (`.py`, `.sql`, `.scala`, `.r`) drops outputs |
| Git operation | 2 GB memory, 4 GB disk writes | working branch limited to 1 GB |
| Workspace assets in one Git folder | 20,000 recommended | not enforced |
| Files viewable in the UI | up to 10 MB | larger files exist but do not open |
| Auth method order | PAT, then OAuth M2M, then OAuth U2M | first that succeeds is used |

## Git folders — `ASSOC-S5-O1`

Databricks Git folders put notebooks under normal version control: branch, commit,
push, open a pull request, all from the workspace.

Work on a **branch per change** and integrate through pull requests. Beyond avoiding
collisions, that gives every change a review point and a revert path — the things you
want on the day something breaks in production.

Everything happens in the **Git dialog**, opened from the branch name at the top of a
notebook or from the folder:

| Operation | What it does | Trap |
|---|---|---|
| **Create Branch** | new branch from a base you choose | the base is not always `main`; check it |
| switch branch | the branch dropdown | non-conflicting uncommitted changes carry over; assets missing on the new branch are deleted, and come back with new IDs and URLs |
| **Commit & Push** | one step; a commit message is required | there is no local-only commit |
| **Pull** | brings remote changes in | nothing updates on its own |
| **Merge** (kebab menu) | merges a branch in and pushes | recommended over rebase |
| **Rebase** (kebab menu) | rewrites history, then commits and **force-pushes** | affects everyone on that branch |
| **Reset** | hard reset plus force push to another branch's state | discards local *and* remote changes |

**Conflicts** stop a pull, merge or rebase. For each file you edit it by hand and click
**Mark As Resolved**, or pick **Keep all current changes** / **Take all incoming
changes**; then **Continue Merge** (or **Continue Rebase**), or **Abort** to back out.

**Pull requests are opened in the Git provider**, not in Databricks: you push the branch
from the dialog, then create, review and merge the PR in GitHub, GitLab or Azure DevOps.
If you cannot push to the default branch, that is the only route.

**What gets committed** depends on the notebook format. New notebooks are **IPYNB** by
default. A **source-format** notebook (`.py`, `.sql`, `.scala`, `.r`) is plain code with a
`# Databricks notebook source` first line and never carries outputs; every notebook in
this repository is one, which is why its diffs read as code. IPYNB outputs are committed
only when an admin allows it and the repository's `.databricks/commit_outputs` file says
so.

The same operations exist outside the UI, which is how automation keeps a production Git
folder on a release branch:

```bash
databricks repos create https://github.com/org/project.git gitHub \
  --path /Workspace/Users/<you>/project       # provider names are case-insensitive
databricks repos update <repo-id> --branch release   # check out a branch (or --tag)
```

Prefer bundles for deploying jobs; a Git folder is for *developing* the code.

## Variables and overrides — `ASSOC-S5-O2`

Declarative Automation Bundles (formerly Databricks Asset Bundles) package jobs,
pipelines and their configuration as version-controlled code.

```yaml
bundle:
  name: my-project

variables:
  catalog:
    description: where the job writes
    default: dev_catalog              # used when nothing overrides it
  warehouse_id:
    lookup:
      warehouse: "Serverless Starter Warehouse"   # resolved to the ID at deploy time
  cluster_conf:
    type: complex                     # the only non-string type
    default:
      spark_version: 15.4.x-scala2.12
      num_workers: 1

targets:
  dev:
    default: true
    mode: development
  test:
    variables:
      catalog: test_catalog
  prod:
    mode: production
    variables:
      catalog: prod_catalog          # same definition, different value
```

**One definition, promoted across environments, with only configuration differing.**
That is the whole point — and it is what makes a dev deployment genuinely predict
prod. Two copies of a bundle diverge, and the moment they do, dev stops telling you
anything.

Reference a variable as `${var.catalog}`. Built-in substitutions sit beside it:
`${bundle.name}`, `${bundle.target}` (the old `${bundle.environment}` still appears in
distractors), `${workspace.current_user.userName}` and `${resources.jobs.<key>.id}`.
A `lookup` turns a name into an ID for an `alert`, `cluster`, `cluster_policy`,
`dashboard`, `instance_pool`, `job`, `metastore`, `notification_destination`,
`pipeline`, `query`, `service_principal` or `warehouse`, and fails if the name is not
found. Variables are resolved **at deploy time**, not when the job runs.

**Override precedence**, first match wins:

```bash
databricks bundle deploy -t prod --var="catalog=hotfix_catalog"   # 1. --var
export BUNDLE_VAR_catalog=ci_catalog                               # 2. environment
# 3. .databricks/bundle/prod/variable-overrides.json  {"catalog": "file_catalog"}
# 4. targets.prod.variables.catalog                    (prod_catalog)
# 5. variables.catalog.default                         (dev_catalog)
```

> **Measured on Free Edition:** with each pair set at once, `--var` beat
> `BUNDLE_VAR_catalog`, `BUNDLE_VAR_catalog` beat `variable-overrides.json`, and the
> file beat the target value (CLI v1.6.0, read from `bundle validate -o json`).

### Promotion walkthrough

The bundle above, validated against each target with nothing else set. The code is
identical in all three columns; only what the CLI resolves changes:

| Resolved value | `-t dev` | `-t test` | `-t prod` |
|---|---|---|---|
| `${var.catalog}` | `dev_catalog` (default) | `test_catalog` | `prod_catalog` |
| job name | `[dev <you>] my job` | `my job` | `my job` |
| schedule | `PAUSED` | as written | as written |
| `max_concurrent_runs` | 4 | 1 | 1 |
| deployment lock | off | on | on |
| bundle root | `.../.bundle/my-project/dev` | `.../.bundle/my-project/test` | `workspace.root_path` (required) |

`test` has no `mode`, so it behaves like plain configuration: no prefix and live
schedules. Give a shared test target its own `root_path` and a service principal so it
behaves like prod.

## Deploying across targets — `ASSOC-S5-O3`

A bundle deploys jobs, pipelines and other assets (dashboards, apps, volumes, schemas)
declared under `resources:`. `mode` is the switch between a private sandbox and the
real thing:

| | `mode: development` | `mode: production` |
|---|---|---|
| Resource names | prefixed `[dev <short_name>]` | as written |
| Tags | `dev: <short_name>` added | none added |
| Schedules and triggers | paused | as written |
| Job concurrency | concurrent runs enabled | as written (default 1) |
| Deployment lock | disabled | enabled |
| Pipelines | `development: true` | must be `development: false` |
| `--cluster-id` override | allowed | refused |
| `workspace.root_path` | defaults under the deployer's home | must be set |
| `git.branch` | checked at deploy | checked at deploy; `--force` overrides |
| Identity | the deployer | a service principal via `run_as` recommended |

`mode: development` prefixes deployed resources with your username, so your
experiments cannot collide with anyone else's or with production. It also pauses every
schedule and trigger, enables concurrent runs and disables the deployment lock, so a
development deploy never fires on its own. `mode: production` drops the prefix, keeps
schedules live, refuses to deploy without an explicit `root_path` and expects a
service-principal `run_as`. Both modes are bundles of **presets**, and you can set
those directly instead:

```yaml
targets:
  prod:
    mode: production
    workspace:
      root_path: /Workspace/Users/${workspace.current_user.userName}/.bundle/${bundle.name}/${bundle.target}
    git:
      branch: main                    # deploy refuses from any other branch
    run_as:
      service_principal_name: <application-id>   # or user_name: someone@example.com
    permissions:
      - level: CAN_VIEW
        group_name: data-engineers
  staging:
    presets:
      name_prefix: "[staging] "
      trigger_pause_status: PAUSED
      jobs_max_concurrent_runs: 1
      pipelines_development: false
      tags:
        env: staging
```

A preset beats the mode's default; a resource's own setting beats the preset.
**`run_as` is the identity the jobs and pipelines execute as**, separate from who
deployed them. The deployer needs permission to use that principal; the principal needs
access to the data.

> **Measured on Free Edition:** a `mode: production` target without `root_path` fails
> `validate` (`must set 'workspace.root_path'`); with it, a target that has neither
> `run_as` nor `permissions` still validated. A target with `git.branch: main` deployed
> from another branch failed with `not on the right Git branch` in **both** modes.
> A `root_path` under `/Workspace/Shared` drew a warning (every user could write there),
> so `validate --strict` failed on it.
> A development deploy gave `max_concurrent_runs: 4` and `edit_mode: UI_LOCKED`: the
> job is meant to be changed in the bundle, not in the Jobs UI (CLI v1.6.0).

## The CLI in automation — `ASSOC-S5-O4`

```bash
databricks bundle init default-python              # scaffold from a template
databricks bundle validate --strict -t prod        # config check; warnings fail too
databricks bundle deploy -t prod                   # upload files, create/update resources
databricks bundle run my_job -t prod               # trigger a job (or pipeline update)
databricks bundle summary -t prod                  # what is deployed and its URLs
databricks bundle destroy -t dev --auto-approve    # delete what this bundle deployed
databricks bundle generate job --existing-job-id 123 --key my_job --bind
                                                   # adopt a UI-built job into the bundle
databricks bundle deployment bind my_job 123       # link a key to an existing job (two-step form)
```

**`validate` is a configuration check, not a test run.** It catches malformed YAML,
unresolved variables and bad references before anything is uploaded. It never executes
your code — so a bundle can validate cleanly and still fail at runtime, which is why a
pipeline runs tests as well. An unknown key is only a **warning** (exit 0) unless you
add `--strict`.

`destroy` deletes the jobs, pipelines and the bundle's workspace folder for that target
only; tables the jobs wrote stay, unless the bundle itself declares their schema or
volume as a resource. `generate` writes YAML for an existing job, pipeline,
dashboard or app; without `--bind` (or a later `deployment bind`) the next deploy
creates a **second** copy instead of taking over the first. `deploy` takes
`--fail-on-active-runs`, `--force-lock` and `--force` (skip the Git branch check).

In CI, authenticate as a **service principal** using OAuth machine-to-machine
(`DATABRICKS_CLIENT_ID` / `DATABRICKS_CLIENT_SECRET`), never as a person. Deploys are
then attributable to the pipeline and scoped to what it needs.

```bash
export DATABRICKS_HOST=https://<workspace>.cloud.databricks.com
export DATABRICKS_CLIENT_ID=<application-id>
export DATABRICKS_CLIENT_SECRET=<oauth-secret>
databricks bundle deploy -t prod     # no --profile: the variables above are used
```

Unified authentication looks for credentials in **environment variables first, then
the `DEFAULT` profile in `.databrickscfg`**, and tries methods in the order personal
access token, OAuth M2M, OAuth U2M, stopping at the first that works. Naming a profile
with `--profile` or `DATABRICKS_CONFIG_PROFILE` changes that: the named profile's
method is used.

> Worth knowing: `DATABRICKS_CONFIG_PROFILE`, if set, overrides those M2M variables and
> the CLI silently authenticates as *you* instead. A local test of CI auth can appear to
> succeed while proving nothing.

> **Measured on Free Edition:** with a deliberately wrong client ID and secret,
> `databricks jobs list` failed when only the M2M variables were set, and succeeded as
> the user when `DATABRICKS_CONFIG_PROFILE` pointed at a U2M profile (CLI v1.6.0).

## Further reading

Official documentation for what this section tests, one link per topic:

- [Git folders](https://docs.databricks.com/aws/en/repos/) — clone, branch, commit and pull inside the workspace.
- [Git operations in Git folders](https://docs.databricks.com/aws/en/repos/git-operations-with-repos) — the dialog step by step, including conflicts.
- [Git folder limits](https://docs.databricks.com/aws/en/repos/limits) — size, asset count and memory limits.
- [Notebook formats](https://docs.databricks.com/aws/en/notebooks/notebook-format) — source vs IPYNB and committing outputs.
- [Declarative Automation Bundles](https://docs.databricks.com/aws/en/dev-tools/bundles/) — the bundles documentation home.
- [Bundle configuration](https://docs.databricks.com/aws/en/dev-tools/bundles/settings) — every top-level key in `databricks.yml`.
- [Bundle variables](https://docs.databricks.com/aws/en/dev-tools/bundles/variables) — defaults, lookups and overrides.
- [Deployment modes](https://docs.databricks.com/aws/en/dev-tools/bundles/deployment-modes) — what development and production modes change.
- [Bundle run identity](https://docs.databricks.com/aws/en/dev-tools/bundles/run-as) — `run_as` and who jobs execute as.
- [Bundle commands](https://docs.databricks.com/aws/en/dev-tools/cli/bundle-commands) — `validate`, `deploy`, `summary`, `destroy`, `generate`, `deployment bind`.
- [Develop a job with bundles](https://docs.databricks.com/aws/en/dev-tools/bundles/jobs-tutorial) — the end-to-end tutorial.
- [Unified authentication](https://docs.databricks.com/aws/en/dev-tools/auth/unified-auth) — where the CLI looks for credentials, and in what order.
- [OAuth M2M](https://docs.databricks.com/aws/en/dev-tools/auth/oauth-m2m) — service-principal authentication for CI.
- [CI/CD on Databricks](https://docs.databricks.com/aws/en/dev-tools/ci-cd/) — the recommended pipeline shape.
- [GitHub Actions](https://docs.databricks.com/aws/en/dev-tools/ci-cd/github) — the `setup-cli` action and a deploy workflow.

Videos for another angle on the hard parts (channel, length):

- [Deploy Faster: Databricks Asset Bundles + Git Explained](https://www.youtube.com/watch?v=FZpgwclX88Q) — Databricks Skill Builder, 23 min. Bundles and Git folders from the source.
- [Databricks CI/CD: Intro to Databricks Asset Bundles](https://www.youtube.com/watch?v=uG0dTF5mmvc) — Dustin Vannoy, 20 min. A practitioner's first bundle, validate to deploy.
