#!/usr/bin/env python3
"""Check that this repo's GitHub CI/CD configuration matches what the docs say.

Everything here is configured through the GitHub web UI rather than committed to
the repo, so nothing else can catch it drifting. This reads the live settings via
`gh api` and reports what is wrong and how to fix it.

    python3 tools/verify_ci_setup.py

Requires the GitHub CLI, authenticated:  gh auth login
"""

from __future__ import annotations

import json
import subprocess
import sys

ENVIRONMENT = "databricks-free"
DEFAULT_BRANCH = "main"
REQUIRED_SECRETS = {"DATABRICKS_HOST", "DATABRICKS_CLIENT_ID", "DATABRICKS_CLIENT_SECRET"}
REQUIRED_CHECKS = {"Content validation", "Tests", "Bundle validation", "Approved by a reviewer"}

OK, WARN, FAIL = "PASS", "WARN", "FAIL"
results: list[tuple[str, str, str, str]] = []  # status, area, finding, remedy


def record(status, area, finding, remedy=""):
    results.append((status, area, finding, remedy))


def gh(path, *, method="GET"):
    """Call the GitHub API. Returns (ok, parsed_json_or_error_string)."""
    proc = subprocess.run(
        ["gh", "api", "-X", method, path],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        return False, (proc.stderr or proc.stdout).strip()
    try:
        return True, json.loads(proc.stdout or "null")
    except json.JSONDecodeError:
        return True, proc.stdout


def repo_slug() -> str | None:
    proc = subprocess.run(
        ["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"],
        capture_output=True, text=True,
    )
    return proc.stdout.strip() if proc.returncode == 0 else None


# ---------------------------------------------------------------- checks


def check_repo_settings(slug):
    ok, data = gh(f"repos/{slug}")
    if not ok:
        record(FAIL, "repo", f"cannot read repo: {data}")
        return
    if data.get("allow_auto_merge"):
        record(OK, "repo", "auto-merge is allowed")
    else:
        record(FAIL, "repo", "auto-merge is disabled",
               "Settings > General > Pull Requests > tick 'Allow auto-merge'")

    if data.get("visibility") == "public":
        record(OK, "repo", "public repo (no secrets may be committed)")


def check_environment(slug):
    ok, env = gh(f"repos/{slug}/environments/{ENVIRONMENT}")
    if not ok:
        record(FAIL, "environment", f"environment '{ENVIRONMENT}' not found",
               f"Settings > Environments > New environment > '{ENVIRONMENT}'")
        return

    record(OK, "environment", f"'{ENVIRONMENT}' exists")

    rules = {r["type"]: r for r in env.get("protection_rules", [])}

    reviewers = rules.get("required_reviewers")
    if reviewers:
        who = [
            (r.get("reviewer") or {}).get("login") or (r.get("reviewer") or {}).get("slug", "?")
            for r in reviewers.get("reviewers", [])
        ]
        record(OK, "environment", f"required reviewers: {', '.join(who) or '(none listed)'}")
        if reviewers.get("prevent_self_review"):
            record(WARN, "environment",
                   "'Prevent self-review' is ON",
                   "With a single maintainer this deadlocks deploys - untick it")
    else:
        record(WARN, "environment", "no required reviewers - deploys run unattended",
               "Tick 'Required reviewers' and add yourself")

    # The API exposes admin bypass as can_admins_bypass.
    if env.get("can_admins_bypass") is True:
        record(WARN, "environment", "admins can bypass protection rules",
               "Untick 'Allow administrators to bypass configured protection rules'")
    elif env.get("can_admins_bypass") is False:
        record(OK, "environment", "admin bypass is disabled")

    policy = env.get("deployment_branch_policy")
    if not policy:
        record(FAIL, "environment", "any branch may deploy to this environment",
               "Set 'Selected branches and tags' and add the pattern 'main'")
    elif policy.get("protected_branches"):
        record(FAIL, "environment",
               "branch policy is 'Protected branches only', which ignores rulesets",
               "Switch to 'Selected branches and tags' with the pattern 'main'")
    elif policy.get("custom_branch_policies"):
        ok2, pol = gh(f"repos/{slug}/environments/{ENVIRONMENT}/deployment-branch-policies")
        names = [p["name"] for p in pol.get("branch_policies", [])] if ok2 else []
        if names == [DEFAULT_BRANCH]:
            record(OK, "environment", f"only '{DEFAULT_BRANCH}' may deploy")
        else:
            record(WARN, "environment", f"branch patterns allowed: {names or '(none)'}",
                   f"Expected exactly ['{DEFAULT_BRANCH}']")


def check_secrets(slug):
    ok, data = gh(f"repos/{slug}/environments/{ENVIRONMENT}/secrets")
    if ok:
        names = {s["name"] for s in data.get("secrets", [])}
        missing = REQUIRED_SECRETS - names
        if missing:
            record(FAIL, "secrets", f"environment secrets missing: {sorted(missing)}",
                   "Settings > Environments > databricks-free > Add environment secret")
        else:
            record(OK, "secrets", f"all three environment secrets present: {sorted(names)}")
    else:
        record(FAIL, "secrets", f"cannot read environment secrets: {data}")

    # Repository-level copies would be readable by workflows that never declare
    # the environment - the exposure environment scope exists to prevent.
    ok, data = gh(f"repos/{slug}/actions/secrets")
    if ok:
        strays = {s["name"] for s in data.get("secrets", [])} & REQUIRED_SECRETS
        if strays:
            record(FAIL, "secrets", f"Databricks secrets ALSO exist at repo level: {sorted(strays)}",
                   "Delete them: Settings > Secrets and variables > Actions > Repository secrets")
        else:
            record(OK, "secrets", "no Databricks secrets at repository level")


def check_ruleset(slug):
    ok, rulesets = gh(f"repos/{slug}/rulesets")
    if not ok:
        record(FAIL, "ruleset", f"cannot read rulesets: {rulesets}")
        return
    if not rulesets:
        record(FAIL, "ruleset", f"no ruleset protecting '{DEFAULT_BRANCH}'",
               "Settings > Rules > Rulesets > New branch ruleset (see docs/ci-cd.md step 4)")
        return

    for rs in rulesets:
        ok, detail = gh(f"repos/{slug}/rulesets/{rs['id']}")
        if not ok:
            continue
        if detail.get("enforcement") != "active":
            record(WARN, "ruleset", f"ruleset '{detail['name']}' is not active",
                   "Set Enforcement status to Active")
            continue

        record(OK, "ruleset", f"'{detail['name']}' is active")
        rules = {r["type"]: r.get("parameters", {}) for r in detail.get("rules", [])}

        pr = rules.get("pull_request")
        if pr is None:
            record(FAIL, "ruleset", "pull requests are not required",
                   "Tick 'Require a pull request before merging'")
        else:
            n = pr.get("required_approving_review_count", 0)
            if n >= 1:
                record(OK, "ruleset", f"requires {n} approving review(s)")
            else:
                record(WARN, "ruleset", "requires 0 approving reviews",
                       "Set 'Required approvals' to 1")

        checks = rules.get("required_status_checks")
        if checks is None:
            record(FAIL, "ruleset", "no required status checks",
                   f"Require these: {sorted(REQUIRED_CHECKS)}")
        else:
            have = {c["context"] for c in checks.get("required_status_checks", [])}
            missing = REQUIRED_CHECKS - have
            extra = have - REQUIRED_CHECKS
            if missing:
                record(FAIL, "ruleset", f"status checks not required: {sorted(missing)}",
                       "Add them under 'Require status checks to pass'")
            else:
                record(OK, "ruleset", "all four PR checks are required")
            if extra:
                record(WARN, "ruleset", f"unrecognised required checks: {sorted(extra)}",
                       "These will never report and will block every PR")

        if "non_fast_forward" in rules:
            record(OK, "ruleset", "force pushes blocked")
        else:
            record(WARN, "ruleset", "force pushes are allowed", "Tick 'Block force pushes'")

        if "deletion" in rules:
            record(OK, "ruleset", "branch deletion blocked")
        else:
            record(WARN, "ruleset", "branch deletion is allowed", "Tick 'Restrict deletions'")

        if detail.get("bypass_actors"):
            who = [b.get("actor_type", "?") for b in detail["bypass_actors"]]
            record(WARN, "ruleset", f"bypass actors configured: {who}",
                   "Expected while you are the only contributor - see docs/ci-cd.md")


def main() -> int:
    if subprocess.run(["which", "gh"], capture_output=True).returncode != 0:
        print("The GitHub CLI (gh) is not installed or not on PATH.", file=sys.stderr)
        return 2
    if subprocess.run(["gh", "auth", "status"], capture_output=True).returncode != 0:
        print("Not authenticated. Run:  gh auth login", file=sys.stderr)
        return 2

    slug = repo_slug()
    if not slug:
        print("Could not determine the repository. Run this inside the repo.", file=sys.stderr)
        return 2

    print(f"Verifying CI/CD configuration for {slug}\n")

    check_repo_settings(slug)
    check_environment(slug)
    check_secrets(slug)
    check_ruleset(slug)

    width = max(len(a) for _, a, _, _ in results)
    icon = {OK: "PASS", WARN: "WARN", FAIL: "FAIL"}
    for status, area, finding, remedy in results:
        print(f"  [{icon[status]}] {area.ljust(width)}  {finding}")
        if remedy and status != OK:
            print(f"         {' ' * width}  -> {remedy}")

    fails = sum(1 for r in results if r[0] == FAIL)
    warns = sum(1 for r in results if r[0] == WARN)
    print(f"\n{len(results)} checks: {len(results) - fails - warns} passed, {warns} warnings, {fails} failures")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
