# Working in this repository

This repo is **public and meant to be forked**: a stranger clones it and deploys
it to their own Databricks Free Edition workspace. Nothing in it may depend on,
or reveal, the maintainer's workspace, account or identity.

## Never commit or put in a PR, issue or PR description

- **Workspace URLs**: `dbc-….cloud.databricks.com`, `adb-….azuredatabricks.net`,
  a deployed app's `….databricksapps.com` address.
- **IDs**: workspace IDs, service principal application IDs, user or group IDs,
  job and run IDs, warehouse IDs, Lakebase endpoint IDs from a real workspace.
- **People**: email addresses, real names or usernames, other than the public
  GitHub owner in the repo's own URL.
- **Credentials**: tokens, client secrets, keys, passwords, `.databrickscfg`
  contents, anything from a secret scope.
- **Anything from `docs/local/`** (gitignored on purpose) or from command output
  that echoes the above (`databricks auth describe`, `apps get`, `current-user me`).

Use instead: `<your-workspace-url>`, `--profile <PROFILE>` (or `FREE` in
examples), repository secrets in workflows, `1111111111111111` for a workspace
ID, a UUID ending `123456789abc` for a principal, `user@example.com`.

The same rule covers screenshots and pasted output in PR descriptions: crop or
redact URLs, IDs and names before attaching them.

## Before every commit

1. `python3 tools/check_sensitive.py`: must print "No sensitive data found".
   CI runs it too, but catch it before it is in git history: history is public
   and effectively permanent.
2. `git diff --cached`: read what is actually staged.
3. Commits are authored with the GitHub noreply address, never a personal email.

If something sensitive does get committed, stop and tell the maintainer before
pushing anything else. Do not try to hide it with a follow-up commit; the value
stays in history.

## Other conventions

- `docs/authoring-guide.md`: how notes, questions, diagrams and assignments are
  written and verified ("run it, don't assume it").
- `docs/ci-cd.md`: the PR checks and the deploy.
- The generated app content (`app/shared/content/*.json`) is not committed;
  `tools/build_app_content.py` builds it.
