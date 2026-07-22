"""
Secret-scan gate — a fail-closed guardrail on every egress path.

Illustrative, simplified extract from budget-skynet (production code is private).

Before any deliverable is published (npm / PyPI / GitHub / Gist), it is scanned for
secrets deterministically — regex, no LLM. Two strategies:

  1. Verbatim values of our own secret env vars (zero false positives).
  2. High-specificity token formats (provider key prefixes, private-key blocks).

The gate is FAIL-CLOSED and biased to catch, on purpose:
  - false positive  = one blocked publish + an alert to the owner   (recoverable)
  - false negative  = an irreversible secret leak to a public registry (catastrophic)

So it is wired into every publish function; nothing goes out unscanned.
"""
from __future__ import annotations

import os
import re

# High-specificity token shapes — chosen to almost never match normal code.
_TOKEN_PATTERNS = [
    re.compile(r"\bghp_[A-Za-z0-9]{36}\b"),          # GitHub PAT
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{22,}\b"),
    re.compile(r"\bsk-ant-[A-Za-z0-9\-]{20,}\b"),    # Anthropic
    re.compile(r"\bnpm_[A-Za-z0-9]{36}\b"),
    re.compile(r"\bpypi-[A-Za-z0-9\-_]{16,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),             # AWS
    re.compile(r"\bAIza[0-9A-Za-z\-_]{35}\b"),       # Google
    re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]{10,}\b"),# Slack
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
]

# Env-var names whose *values* must never appear in a deliverable.
_SECRET_ENV_VARS = (
    "MARKET_API_KEY", "CLAUDE_API_KEY", "GIST_TOKEN", "AGENT_GITHUB_TOKEN",
    "E2B_API_KEY", "NPM_TOKEN", "PYPI_TOKEN", "HF_TOKEN",
)


def scan_files_for_secrets(files: dict[str, str]) -> list[str]:
    """Return a list of findings (empty == clean). Metadata keys are skipped."""
    live_values = [v for name in _SECRET_ENV_VARS if (v := os.environ.get(name))]
    findings: list[str] = []

    for path, content in files.items():
        if path.startswith("_") or path.endswith(".npmrc"):
            continue  # internal metadata / sandbox auth, written separately
        for val in live_values:
            if val and val in content:
                findings.append(f"{path}: verbatim secret env value")
        for pat in _TOKEN_PATTERNS:
            if pat.search(content):
                findings.append(f"{path}: token-shaped string ({pat.pattern[:24]}...)")
    return findings


def secret_scan_gate(files: dict[str, str], *, alert) -> None:
    """Fail-closed gate. Raises before the network call if anything is found."""
    findings = scan_files_for_secrets(files)
    if findings:
        alert(f"BLOCKED publish — possible secret leak:\n" + "\n".join(findings))
        raise PermissionError("secret-scan gate: refusing to publish")
    # clean -> caller proceeds to publish
