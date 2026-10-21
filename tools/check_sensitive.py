#!/usr/bin/env python3
"""Fail if a tracked file contains something that identifies a real workspace,
person or credential.

This repository is public and meant to be forked, so nothing in it may point at
one person's Databricks workspace or account. Real values belong in a CLI
profile, a secret scope, repository secrets, or the gitignored docs/local/.
CI runs this on every pull request; run it yourself before committing:

    python3 tools/check_sensitive.py

What it rejects, and the placeholder to use instead:

  * workspace URLs (dbc-....cloud.databricks.com, adb-....azuredatabricks.net,
    <id>.<cloud>.databricksapps.com)          -> <your-workspace-url>, --profile
  * numeric workspace IDs (15-16 digits)      -> 1111111111111111 (one digit repeated)
  * UUIDs, e.g. service principal IDs         -> a UUID ending 123456789abc or 000000000000
  * email addresses                           -> user@example.com
  * tokens and keys (dapi, dose, ghp_, github_pat_, AKIA, private keys)
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Generated or vendored. The check and its tests are scanned too: their samples
# are made up and assembled from pieces, so the files hold no literal match.
SKIP = {
    "app/package-lock.json",
}

PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("workspace URL", re.compile(r"\bdbc-[0-9a-f]{8}-[0-9a-f]{4}\.cloud\.databricks\.com\b", re.I)),
    ("workspace URL", re.compile(r"\badb-\d{6,}\.\d+\.azuredatabricks\.net\b", re.I)),
    ("app URL", re.compile(r"\b[\w-]+-\d{10,}\.(?:aws|azure|gcp)\.databricksapps\.com\b", re.I)),
    ("workspace ID", re.compile(r"(?<![\w.-])\d{15,16}(?![\w.-])")),
    ("UUID", re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)),
    ("email address", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}\b")),
    ("Databricks token", re.compile(r"\b(?:dapi|dose)[0-9a-f]{20,}\b")),
    ("GitHub token", re.compile(r"\b(?:ghp|gho|ghs|ghu)_[A-Za-z0-9]{20,}\b|\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("AWS key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
]

ALLOWED_EMAIL_DOMAINS = ("example.com", "example.org", "users.noreply.github.com")
ALLOWED_EMAILS = {"noreply@anthropic.com", "noreply@github.com"}


def allowed(kind: str, value: str) -> bool:
    if kind == "workspace ID":
        return len(set(value)) == 1  # 1111111111111111 and friends
    if kind == "UUID":
        return value.lower().endswith(("123456789abc", "000000000000"))
    if kind == "email address":
        v = value.lower()
        domain = v.split("@", 1)[1]
        return v in ALLOWED_EMAILS or any(domain == d or domain.endswith("." + d) for d in ALLOWED_EMAIL_DOMAINS)
    return False


def findings_in(text: str) -> list[tuple[int, str, str]]:
    found = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for kind, pattern in PATTERNS:
            for m in pattern.finditer(line):
                if not allowed(kind, m.group(0)):
                    found.append((lineno, kind, m.group(0)))
    return found


def tracked_files() -> list[str]:
    out = subprocess.run(["git", "ls-files", "-z"], cwd=REPO_ROOT, capture_output=True, text=True, check=True)
    return [p for p in out.stdout.split("\0") if p and p not in SKIP]


def main() -> int:
    problems = []
    for rel in tracked_files():
        path = REPO_ROOT / rel
        try:
            text = path.read_text()
        except (UnicodeDecodeError, FileNotFoundError, IsADirectoryError):
            continue  # binary, or deleted in the working tree
        for lineno, kind, value in findings_in(text):
            problems.append(f"{rel}:{lineno}: {kind}: {value}")

    if problems:
        print("Possible sensitive data in tracked files:", file=sys.stderr)
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        print(
            "\nReplace each with a placeholder (see the top of tools/check_sensitive.py), "
            "or move it to a CLI profile, a secret, or docs/local/.",
            file=sys.stderr,
        )
        return 1
    print("No sensitive data found in tracked files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
