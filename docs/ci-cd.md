# CI/CD

Three workflows. A pull request must pass checks and carry an approving review;
once it does GitHub merges it, and the merge deploys to Databricks after you
approve the deployment.

```
 PR opened ──▶ pr-checks.yml          auto-merge.yml
              ├─ content validation   └─ enables native auto-merge
              ├─ tests (+ "PR must ship tests" gate)
              ├─ bundle validation                │
              └─ approving review present         ▼
                          │            ruleset satisfied → GitHub merges
                          ▼                                    │
                    all green ───────────────────────────────┘
                                                              ▼
                                                 main ──▶ deploy.yml
                                                              │
                                              ⏸  pauses for your approval
                                                 (databricks-free environment)
                                                              ▼
                                                         Databricks
```

---

## How the approval gate handles a single maintainer

GitHub does not let you approve your own pull request. With one contributor, a
naive "require 1 approval" would mean nothing you open can ever merge.

So the **Approved by a reviewer** check asks whether a second reviewer actually
exists before demanding one:

| Situation | Result |
| --- | --- |
| Someone approved it | Passes |
| Anyone requested changes | **Fails** — always, solo or not |
| No approval, but other people have write access | **Fails**, naming who can approve |
| No approval, and you are the only account with write access | **Waived**, with a loud warning and a note in the run summary explaining why |

The waiver is deliberately noisy rather than silent: it says on every run that the
gate is not currently protecting anything. **Add a collaborator and it becomes a
hard requirement automatically** — no changes to the workflow.

This is honest about what a solo repo can enforce, instead of either pretending to
have peer review or leaving a permanent red X that trains you to merge past
failures.

> **On the ruleset:** while you are the only contributor, put yourself in its
> **Bypass list**. The ruleset requires an approval that cannot exist for your own
> PRs; the bypass is what lets you merge them. A second account of your own would
> technically satisfy the rule while buying nothing real.

---

## One-time setup

**Do these in order — there is a chicken-and-egg in the middle.**

A branch ruleset requires status checks *by name*, and GitHub only offers names it
has already seen. Until a pull request has actually run the workflows, the four
checks do not exist as far as the ruleset UI is concerned, and you would be typing
them from memory — where one typo produces a required check that never reports and
blocks every PR forever.

So the ruleset comes *after* the first pull request, not before:

| # | Step | When |
| --- | --- | --- |
| 1 | Deployment environment | Any time |
| 2 | Databricks credentials | After the environment exists (the secrets live on it) |
| 3 | Allow auto-merge | Any time — but it does nothing until step 6 |
| 4 | Merge style | Before your first merge, or you will merge the wrong way |
| — | **Open your first PR and let the checks run** | Registers the four check names |
| 5 | Create the `no-tests-needed` label | Any time — before your first docs-only PR |
| 6 | Branch ruleset for `main` | Now the checks are selectable |
| — | Merge that first PR | |

Two consequences worth expecting rather than discovering:

- **Your first PR merges without the full gate**, because the ruleset does not
  exist yet. That is unavoidable — and harmless, since all four checks still run
  and you can read them. The gate protects everything after it.
- **The second PR is the first real test of the gate.** Open one deliberately if
  you have nothing pending; it is how you find out whether the ruleset does what
  you think.

### 1. Deployment environment

`Settings → Environments → New environment` → name it **`databricks-free`**,
which is what `deploy.yml` references. Three settings on that page matter.

**Required reviewers — tick it, add yourself.** Every deploy then pauses until you
approve it in the Actions tab.

> **This one works solo, unlike PR approval.** GitHub *does* let you approve a
> deployment you triggered yourself. Ticking "Required reviewers" reveals a
> **"Prevent self-review"** checkbox — leave it **unticked**. Turning it on would
> recreate the same deadlock the PR approval gate has, and for the same reason.

**Allow administrators to bypass configured protection rules — untick it.** It
defaults to ticked. Since you are already a required reviewer with self-review
allowed, you can approve your own deploys in one click; bypass is a second route to
something you can do anyway. That redundancy is the problem: the day you add a
collaborator or tick "Prevent self-review", admin bypass would silently reopen the
gate you just closed. Leave it ticked only if you specifically want a break-glass
path — and on a personal project, no deploy is that urgent.

**Deployment branches and tags — pick "Selected branches and tags" and add the
pattern `main`.** This is the only setting on the page that closes a real path to
your Databricks credentials: `deploy.yml` has a `workflow_dispatch` trigger, so
while this says "No restriction", the environment and its secrets can be reached
from *any* branch by manually dispatching the workflow.

> **Do not pick "Protected branches only" here.** It recognises only *classic*
> branch protection rules, and step 6 below has you creating a **ruleset** — which
> it does not count. GitHub even warns you at the time: *"No repository branch
> protection rules set: all branches are still allowed."* The setting would look
> configured while doing nothing. "Selected branches and tags" is explicit,
> self-contained, and unaffected by that incompatibility.

### 2. Databricks credentials

CI authenticates to Databricks as a **service principal** using OAuth
machine-to-machine, never as you. A service principal holds only the access it
needs, deploys are attributable to CI rather than to a person, and revoking it
does not disturb your own login.

> **This is a public repository.** Nothing below — no workspace URL, no client ID,
> no secret — belongs in a committed file. All three live in GitHub secrets, and
> every value in this document is a placeholder.
>
> If you are the maintainer, your own filled-in values live in
> `docs/local/workspace-values.md`, which is gitignored and never pushed. Keep it
> that way: placeholders here, real values there.

#### a. Create the service principal

Run this against your own workspace, with a CLI profile you have already
authenticated (`databricks auth login --host <your-workspace-url> --profile FREE`):

```bash
databricks service-principals create --display-name "github-actions-ci" --profile FREE
```

Two fields from the response matter — note both:

| Response field | Used for | Looks like |
| --- | --- | --- |
| `applicationId` | the `DATABRICKS_CLIENT_ID` secret | a UUID |
| `id` | the numeric ID the secrets commands take | a long integer |

The service principal is created with `workspace-access` and
`databricks-sql-access` entitlements, which is enough to deploy a bundle.

#### b. Create its OAuth secret

```bash
databricks service-principal-secrets-proxy create <NUMERIC_ID> --profile FREE
```

The `secret` field is **shown once and never again**.

> **Handle it like the credential it is.** Copy it straight into the GitHub secret
> below. Do not paste it into a chat, an AI conversation, a terminal you are
> screen-sharing, or a file — including a `.env` you intend to gitignore. If it is
> ever exposed, revoke it (step d) and issue a new one; the exposure is only as bad
> as the time it stays valid.

#### c. Store all three as environment secrets

`Settings → Environments → databricks-free → Add environment secret`.

Environment secrets, **not repository secrets**: only `deploy.yml` needs these and
it is the sole workflow declaring the environment, so environment scope prevents
any other workflow — including ones added later — from reading them.

| Secret | Value |
| --- | --- |
| `DATABRICKS_HOST` | Your workspace URL, e.g. `https://dbc-XXXXXXXX-XXXX.cloud.databricks.com` |
| `DATABRICKS_CLIENT_ID` | The `applicationId` from step (a) |
| `DATABRICKS_CLIENT_SECRET` | The `secret` from step (b) |

Find your workspace URL in the browser address bar when signed in to Databricks, or
with `databricks auth profiles`.

#### d. Rotating and revoking

Secrets are valid for up to two years, and a service principal can hold up to five
at once — so rotation is create-then-delete, with no downtime:

```bash
databricks service-principal-secrets-proxy list <NUMERIC_ID> --profile FREE
databricks service-principal-secrets-proxy create <NUMERIC_ID> --profile FREE   # update the GitHub secret
databricks service-principal-secrets-proxy delete <NUMERIC_ID> <OLD_SECRET_ID> --profile FREE
```

To find the numeric ID again later:

```bash
databricks service-principals list --profile FREE
```

### 2b. Lakebase access for the service principal

The study app attaches the Lakebase project as an app resource, and the Apps API
requires whoever creates the app to hold **CAN_MANAGE on that project**. The
project is owned by you, so the CI service principal has nothing on it until you
grant it. Without this, `bundle deploy` fails with
`User does not have permission to add resource postgres to app de-prep-study.
User needs MANAGE permission on the resource. (403 PERMISSION_DENIED)` — the first
deploy after PR #21 did exactly that.

One-time, as the project owner (the permissions object type for a Lakebase
project is `database-projects`; `update` adds to the list, `set` would replace it):

```bash
databricks permissions update database-projects de-prep --profile FREE \
  --json '{"access_control_list":[{"service_principal_name":"<DATABRICKS_CLIENT_ID>","permission_level":"CAN_MANAGE"}]}'
databricks permissions get database-projects de-prep --profile FREE      # confirm CAN_MANAGE is listed
```

Then re-run the deploy: `gh workflow run deploy.yml --ref main`.

### 3. Allow auto-merge

`Settings → General → Pull Requests` → tick **Allow auto-merge**.

Without this, `auto-merge.yml` logs a warning and does nothing; PRs simply wait to
be merged by hand.

> **Auto-merge does nothing until the ruleset exists.** It exists to merge a PR
> once its *pending requirements* are met — so if no ruleset makes any check
> required, the PR is immediately mergeable and GitHub refuses to enable
> auto-merge on it ("Pull request is in clean status"). Step 4 is what gives it
> something to wait for. This is a warning in the workflow log, not a failure.

### 4. Merge style

`Settings → General → Pull Requests`:

- ✅ **Allow squash merging** — the project's merge style: one commit per PR, so
  `main` reads as a list of changes rather than a tangle of merge bubbles. The
  content PRs ahead are naturally cohesive (a section's lessons, labs and
  questions), so they squash well.
- ❌ Untick **merge commits** and **rebase merging**. `auto-merge.yml` is set to
  `SQUASH`; leaving the others enabled means a PR merged by hand lands differently
  from one merged automatically, which is a difference nobody will remember.
- ✅ **Automatically delete head branches** — saves a manual cleanup per PR.
  Deleting a merged branch never blocks a rollback: the change is a commit on
  `main`, so `git revert <sha>` is all a rollback needs, and GitHub keeps the
  deleted ref restorable from the PR anyway.

> Reasoning that would otherwise live in a series of commit messages belongs in
> `docs/` instead, where it is far more discoverable than `git log`.

### 5. Create the `no-tests-needed` label

The test-presence gate refuses a PR that adds or changes no tests, and names this
label as the way out. **The label does not exist by default** — without it the
escape hatch is unusable, and a docs-only PR can never merge.

```bash
gh label create "no-tests-needed" \
  --description "Change genuinely cannot carry a test (docs, comments). Waives the test-presence gate." \
  --color "0E8A16"
```

Or `Issues → Labels → New label`. The name must match exactly — the workflow
checks for it literally.

### 6. Branch ruleset for `main`

**This is the actual enforcement.** The `approval` job in `pr-checks.yml` makes the
requirement *visible*, but a workflow cannot stop someone with write access from
merging — a ruleset can.

> **Do this after your first PR has run its checks** (see the ordering table
> above), so the four check names appear in the picker instead of being typed.

`Settings → Rules → Rulesets → New branch ruleset`:

- **Target**: default branch (`main`)
- ✅ Restrict deletions
- ✅ Block force pushes
- ✅ **Require a pull request before merging**
  - Required approvals: **1**
  - ✅ Dismiss stale approvals when new commits are pushed
- ✅ **Require status checks to pass**, and select:
  - `Content validation`
  - `Tests`
  - `Bundle validation`
  - `Approved by a reviewer`

While you're the only contributor, add yourself under **Bypass list** — see the
section at the top for why.

---

## What each workflow does

### `pr-checks.yml`

Runs on PR events **and on review submission** — a plain `pull_request` workflow
doesn't re-run when someone approves, which would leave the approval check stale.

| Job | Checks |
| --- | --- |
| **Content validation** | `validate_content.py`, the generated objective docs match their YAML, and the app's content JSON matches `content/` (`build_app_content.py --check`) |
| **Tests** | The test-presence gate, then `pytest tools/tests` |
| **Bundle validation** | `tools/validate_bundle.py` — schema + repo invariants, offline |
| **Study app** | In `app/`: `npm ci`, typecheck, lint, vitest, `npm run build` — no credentials |
| **Approved by a reviewer** | An approval, or a waiver if no second reviewer exists — see above |

**Why the PR does not run `databricks bundle validate`.** That command always
resolves the current user over SCIM, so it needs working credentials — it is not an
offline check, despite looking like one. On a public repo, pull requests from forks
receive no secrets, so requiring credentials would fail every outside contribution;
and giving a PR-triggered workflow real credentials is a bad idea in its own right.

So the PR check validates `databricks.yml` against the schema the CLI emits
(`databricks bundle schema` needs no credentials) plus this repo's own invariants —
notably that no target hardcodes `workspace.host`. The authoritative
`bundle validate --strict` runs in `deploy.yml` against the real workspace before
anything is deployed. Early warning on the PR; the real gate before deploy.

### The "every PR must ship tests" gate

You asked for this explicitly, so it fails a PR that adds or changes no tests. A
file counts if it matches:

- `tests/` or `test/` anywhere in its path
- `test_*.py` or `*_test.py`
- `*.spec.ts` / `*.test.tsx` (and the js variants)

**The escape hatch:** apply the **`no-tests-needed`** label. Without one, a README
typo fix could never merge, and a rule people route around by inventing junk tests
is worse than no rule. The label leaves a visible record of the decision on each PR
where it's used.

### `auto-merge.yml`

Turns on GitHub's *native* auto-merge rather than merging from a workflow. GitHub
then merges the PR itself once the ruleset is satisfied. This keeps the ruleset as
the single source of truth for "may this merge" — a workflow that merges directly
would be a second, weaker copy of that logic.

Skips drafts.

### `deploy.yml`

Runs on push to `main` (and manual dispatch). Because it declares
`environment: databricks-free`, it **pauses and waits for your approval** in the
Actions tab before any step runs — including before it can read the environment's
secrets.

**It is hands-off, and here is what makes it so.** A merge performed under the
default `GITHUB_TOKEN` does not trigger other workflows, which is why bot-merged
PRs #5–#20 never deployed. Two settings fix that, both in place and confirmed on
PR #23 (2026-09-10), whose auto-merge produced a `push`-event deploy run with no
manual dispatch:

1. A fine-grained personal access token scoped to this repo with *Contents* and
   *Pull requests* read & write, stored as the repository secret
   **`AUTOMERGE_TOKEN`**. `auto-merge.yml` uses it when present, so the merge is
   attributed to a user and the push to `main` triggers the deploy. When the
   token expires, the symptom is a merged PR with no deploy run - rotate the
   secret.
2. The `databricks-free` environment has no *Required reviewers*; the branch
   ruleset already decides what reaches `main`. *Deployment branches* stays
   restricted to `main`.

A quick check that a merge really deployed:
`gh run list --workflow=deploy.yml --limit 1` should show `event: push`.

Once approved it re-runs validation and tests before deploying, since two
individually-valid PRs can merge into a broken `main`. Then
`databricks bundle deploy -t free`, with a concurrency group so two deploys can't
race.

The bundle now includes the study app (`bundle/resources/de_prep_study_app.app.yml`).
`bundle deploy` only uploads it and creates the app resource, stopped; the
following `bundle run study_app` step is what deploys the source and starts the
app (and redeploys it when it is already running). Databricks runs `npm install`
and `npm run build` remotely, which is why `deploy.yml` sets up no Node toolchain. Check it afterwards with
`databricks apps get de-prep-study --profile FREE -o json`.

---

## Gotchas worth knowing

**`DATABRICKS_CONFIG_PROFILE` overrides M2M env vars.** If that variable is set in
your shell, the CLI resolves a named profile and *ignores* `DATABRICKS_CLIENT_ID` /
`DATABRICKS_CLIENT_SECRET` — so a local attempt to reproduce CI auth will silently
run as *you* instead of as the service principal, and appear to work. Use
`env -u DATABRICKS_CONFIG_PROFILE` to test it honestly. CI runners never set it.

**Deploys land under the service principal's path**, not yours:
`/Workspace/Users/<application-id>/.bundle/databricks-de-prep/free`. That's
correct, and a good way to tell a CI deploy from one you ran by hand. The study
app's notebook links point into that folder (`DE_PREP_FILES_ROOT`), so the app
only links correctly to the deploy that shipped it.

**Never `bundle deploy` the app from a laptop.** Development mode prefixes
resource names, so it would create a second `de-prep-study` and use one of Free
Edition's three app slots. Use `npm run dev` in `app/` instead.

**The bundle hardcodes no workspace URL.** `bundle/databricks.yml` deliberately
omits `workspace.host` on both targets — it does not belong in a public repo, and
it cannot be parameterised anyway (it resolves before variables interpolate). The
host comes from your CLI profile locally (`--profile FREE`) and from
`DATABRICKS_HOST` in CI. That is why every local command below passes `--profile`.

**Free Edition quotas apply to CI too.** Deploying is cheap, but jobs the bundle
runs are not — 5 concurrent tasks, one active pipeline per type, and blowing the
compute quota shuts the workspace down for the rest of the day. Don't add
run-on-every-merge jobs without thinking about that.

**Right now the bundle deploys almost nothing.** It has targets and no resources
yet; they arrive with the Phase 2 content. The pipeline is wired and verified
first, deliberately, so content lands on rails that already work.

---

## Verifying it locally

```bash
# what CI runs on a PR
./.venv/bin/python tools/validate_content.py
./.venv/bin/python tools/render_objectives.py --check
./.venv/bin/python -m pytest tools/tests -v
./.venv/bin/python tools/validate_bundle.py

# check the GitHub side matches this doc (needs: gh auth login)
./.venv/bin/python tools/verify_ci_setup.py

# what CI runs on merge (deploys for real)
cd bundle && databricks bundle deploy -t free --profile FREE
```
