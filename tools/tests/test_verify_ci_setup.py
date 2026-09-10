"""Tests for the CI/CD configuration verifier.

The verifier reads live GitHub settings, so the calls themselves cannot be tested
offline - but the logic that turns an API response into PASS/WARN/FAIL is pure,
and that is where a wrong field name or an inverted condition would hide. A
verifier that quietly passes on a broken configuration is worse than no verifier,
because it is trusted.

These stub the `gh` helper with canned payloads and assert the verdicts.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import verify_ci_setup as v  # noqa: E402

SLUG = "owner/repo"
ENV = f"repos/{SLUG}/environments/{v.ENVIRONMENT}"


@pytest.fixture(autouse=True)
def clean_results():
    v.results.clear()
    yield
    v.results.clear()


def stub(monkeypatch, responses):
    """Point the verifier at canned API responses instead of the network."""
    def fake_gh(path, *, method="GET"):
        if path not in responses:
            return False, f"no stub for {path}"
        return True, responses[path]
    monkeypatch.setattr(v, "gh", fake_gh)


def verdicts(area=None):
    return [(r[0], r[2]) for r in v.results if area is None or r[1] == area]


def statuses(area=None):
    return {s for s, _ in verdicts(area)}


# ---------------------------------------------------------------- repo


def test_auto_merge_disabled_fails(monkeypatch):
    stub(monkeypatch, {f"repos/{SLUG}": {"allow_auto_merge": False, "allow_squash_merge": True}})
    v.check_repo_settings(SLUG)
    assert any(s == v.FAIL and "auto-merge" in f for s, f in verdicts())


def test_missing_no_tests_needed_label_fails(monkeypatch):
    """Without the label the test-presence gate has no escape hatch at all."""
    stub(monkeypatch, {
        f"repos/{SLUG}": {"allow_auto_merge": True, "allow_squash_merge": True,
                          "allow_merge_commit": False, "allow_rebase_merge": False,
                          "delete_branch_on_merge": True},
        f"repos/{SLUG}/labels": [{"name": "bug"}],
    })
    v.check_repo_settings(SLUG)
    assert any(s == v.FAIL and "no-tests-needed" in f for s, f in verdicts())


def test_present_no_tests_needed_label_passes(monkeypatch):
    stub(monkeypatch, {
        f"repos/{SLUG}": {"allow_auto_merge": True, "allow_squash_merge": True,
                          "allow_merge_commit": False, "allow_rebase_merge": False,
                          "delete_branch_on_merge": True},
        f"repos/{SLUG}/labels": [{"name": "no-tests-needed"}],
    })
    v.check_repo_settings(SLUG)
    assert v.FAIL not in statuses()


def test_squash_only_passes(monkeypatch):
    stub(monkeypatch, {f"repos/{SLUG}": {
        "allow_auto_merge": True, "allow_squash_merge": True,
        "allow_merge_commit": False, "allow_rebase_merge": False,
        "delete_branch_on_merge": True,
    }})
    v.check_repo_settings(SLUG)
    assert v.FAIL not in statuses()
    assert v.WARN not in statuses()


def test_other_merge_methods_warn(monkeypatch):
    """This is the drift PR #1 hit: merged by hand one way, auto-merge another."""
    stub(monkeypatch, {f"repos/{SLUG}": {
        "allow_auto_merge": True, "allow_squash_merge": True,
        "allow_merge_commit": True, "allow_rebase_merge": False,
        "delete_branch_on_merge": True,
    }})
    v.check_repo_settings(SLUG)
    assert any(s == v.WARN and "merge commits" in f for s, f in verdicts())


# ---------------------------------------------------------------- environment


def _env(**overrides):
    base = {
        "protection_rules": [
            {"type": "required_reviewers",
             "reviewers": [{"reviewer": {"login": "someone"}}],
             "prevent_self_review": False},
        ],
        "can_admins_bypass": False,
        "deployment_branch_policy": {"protected_branches": False, "custom_branch_policies": True},
    }
    base.update(overrides)
    return base


def test_missing_environment_fails(monkeypatch):
    stub(monkeypatch, {})
    v.check_environment(SLUG)
    assert any(s == v.FAIL and "not found" in f for s, f in verdicts())


def test_protected_branches_policy_fails(monkeypatch):
    """The trap: 'Protected branches only' ignores rulesets, so it allows everything."""
    stub(monkeypatch, {ENV: _env(
        deployment_branch_policy={"protected_branches": True, "custom_branch_policies": False})})
    v.check_environment(SLUG)
    assert any(s == v.FAIL and "ignores rulesets" in f for s, f in verdicts())


def test_no_branch_policy_fails(monkeypatch):
    stub(monkeypatch, {ENV: _env(deployment_branch_policy=None)})
    v.check_environment(SLUG)
    assert any(s == v.FAIL and "any branch may deploy" in f for s, f in verdicts())


def test_main_only_branch_policy_passes(monkeypatch):
    stub(monkeypatch, {
        ENV: _env(),
        f"{ENV}/deployment-branch-policies": {"branch_policies": [{"name": "main"}]},
    })
    v.check_environment(SLUG)
    assert any(s == v.OK and "only 'main' may deploy" in f for s, f in verdicts())


def test_prevent_self_review_warns(monkeypatch):
    """Enabling it deadlocks a solo maintainer - the verifier must say so."""
    stub(monkeypatch, {
        ENV: _env(protection_rules=[
            {"type": "required_reviewers",
             "reviewers": [{"reviewer": {"login": "solo"}}],
             "prevent_self_review": True}]),
        f"{ENV}/deployment-branch-policies": {"branch_policies": [{"name": "main"}]},
    })
    v.check_environment(SLUG)
    assert any(s == v.WARN and "Prevent self-review" in f for s, f in verdicts())


def test_admin_bypass_enabled_warns(monkeypatch):
    stub(monkeypatch, {
        ENV: _env(can_admins_bypass=True),
        f"{ENV}/deployment-branch-policies": {"branch_policies": [{"name": "main"}]},
    })
    v.check_environment(SLUG)
    assert any(s == v.WARN and "bypass" in f for s, f in verdicts())


# ---------------------------------------------------------------- secrets


def test_all_secrets_present_passes(monkeypatch):
    stub(monkeypatch, {
        f"{ENV}/secrets": {"secrets": [{"name": n} for n in v.REQUIRED_SECRETS]},
        f"repos/{SLUG}/actions/secrets": {"secrets": []},
    })
    v.check_secrets(SLUG)
    assert v.FAIL not in statuses()


def test_missing_secret_fails(monkeypatch):
    stub(monkeypatch, {
        f"{ENV}/secrets": {"secrets": [{"name": "DATABRICKS_HOST"}]},
        f"repos/{SLUG}/actions/secrets": {"secrets": []},
    })
    v.check_secrets(SLUG)
    assert any(s == v.FAIL and "missing" in f for s, f in verdicts())


def test_stray_repository_secrets_fail(monkeypatch):
    """Repo-level copies stay readable by workflows outside the environment."""
    stub(monkeypatch, {
        f"{ENV}/secrets": {"secrets": [{"name": n} for n in v.REQUIRED_SECRETS]},
        f"repos/{SLUG}/actions/secrets": {"secrets": [{"name": "DATABRICKS_CLIENT_SECRET"}]},
    })
    v.check_secrets(SLUG)
    assert any(s == v.FAIL and "repo level" in f for s, f in verdicts())


# ---------------------------------------------------------------- ruleset


def _ruleset(**overrides):
    base = {
        "id": 1, "name": "MainBranchRuleset", "enforcement": "active",
        "rules": [
            {"type": "pull_request", "parameters": {"required_approving_review_count": 1}},
            {"type": "required_status_checks", "parameters": {
                "required_status_checks": [{"context": c} for c in v.REQUIRED_CHECKS]}},
            {"type": "non_fast_forward"},
            {"type": "deletion"},
        ],
        "bypass_actors": [],
    }
    base.update(overrides)
    return base


def test_no_ruleset_fails(monkeypatch):
    stub(monkeypatch, {f"repos/{SLUG}/rulesets": []})
    v.check_ruleset(SLUG)
    assert any(s == v.FAIL and "no ruleset" in f for s, f in verdicts())


def test_complete_ruleset_passes(monkeypatch):
    rs = _ruleset()
    stub(monkeypatch, {f"repos/{SLUG}/rulesets": [rs], f"repos/{SLUG}/rulesets/1": rs})
    v.check_ruleset(SLUG)
    assert v.FAIL not in statuses()


def test_disabled_ruleset_warns(monkeypatch):
    """Rulesets default to Disabled - easy to create one that protects nothing."""
    rs = _ruleset(enforcement="disabled")
    stub(monkeypatch, {f"repos/{SLUG}/rulesets": [rs], f"repos/{SLUG}/rulesets/1": rs})
    v.check_ruleset(SLUG)
    assert any(s == v.WARN and "not active" in f for s, f in verdicts())


def test_missing_status_checks_fail(monkeypatch):
    rs = _ruleset(rules=[
        {"type": "pull_request", "parameters": {"required_approving_review_count": 1}},
        {"type": "required_status_checks", "parameters": {
            "required_status_checks": [{"context": "Tests"}]}},
    ])
    stub(monkeypatch, {f"repos/{SLUG}/rulesets": [rs], f"repos/{SLUG}/rulesets/1": rs})
    v.check_ruleset(SLUG)
    assert any(s == v.FAIL and "not required" in f for s, f in verdicts())


def test_unrecognised_required_check_warns(monkeypatch):
    """A typo'd check name never reports, so it blocks every PR forever."""
    rs = _ruleset(rules=[
        {"type": "pull_request", "parameters": {"required_approving_review_count": 1}},
        {"type": "required_status_checks", "parameters": {
            "required_status_checks": [{"context": c} for c in v.REQUIRED_CHECKS]
            + [{"context": "Contnet validation"}]}},
    ])
    stub(monkeypatch, {f"repos/{SLUG}/rulesets": [rs], f"repos/{SLUG}/rulesets/1": rs})
    v.check_ruleset(SLUG)
    assert any(s == v.WARN and "unrecognised" in f for s, f in verdicts())
