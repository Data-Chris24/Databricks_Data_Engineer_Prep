"""Tests for tools/check_sensitive.py.

Every sample that must be caught is made up and assembled from pieces, so this
file holds no literal match: tools/check_sensitive.py scans it like any other
file, and GitHub push protection rejects a token-shaped string, fake or not.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import check_sensitive as cs  # noqa: E402


@pytest.mark.parametrize(
    "line, kind",
    [
        ("host: https://" + "dbc-" + "0a0b0c0d-0e0f" + ".cloud.databricks.com", "workspace URL"),
        ("https://" + "adb-" + "98765432" + "10987654" + ".7.azuredatabricks.net", "workspace URL"),
        ("open https://my-app-" + "98765432" + "10987654" + ".aws.databricksapps.com", "app URL"),
        ('{"workspace_id": ' + "98765432" + "10987654" + "}", "workspace ID"),
        ("GRANT USE CATALOG ON CATALOG main TO `" + "0a1b2c3d-4e5f-4a6b-8c7d-" + "9e0f1a2b3c4d" + "`", "UUID"),
        ("contact jane.doe" + "@" + "gmail.com", "email address"),
        ("token = " + "da" + "pi" + "0123456789abcdef" * 2, "Databricks token"),
        ("GH_TOKEN=" + "gh" + "p_" + "abcdefghijklmnopqrstuvwxyz0123", "GitHub token"),
        ("AK" + "IA" + "ABCDEFGHIJKLMNOP", "AWS key"),
        ("-----BEGIN OPENSSH " + "PRIVATE KEY-----", "private key"),
    ],
)
def test_real_values_are_caught(line, kind):
    assert kind in {k for _, k, _ in cs.findings_in(line)}


@pytest.mark.parametrize(
    "line",
    [
        "databricks auth login --host <your-workspace-url> --profile FREE",
        '{"workspace_id": 1111111111111111}',
        "TO `6f1c0e2a-1b2c-4d5e-9f00-123456789abc`",
        "Co-Authored-By: Claude <noreply@anthropic.com>",
        "git config user.email 12345+someone@users.noreply.github.com",
        "send to analyst@example.com",
        "reachable at a `*.aws.databricksapps.com` URL",
        '"@databricks/appkit": "0.57.0"',
    ],
)
def test_placeholders_pass(line):
    assert cs.findings_in(line) == []


def test_the_repository_is_clean():
    # The same check CI runs: no tracked file may identify a workspace, person or credential.
    assert cs.main() == 0
