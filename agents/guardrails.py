"""Implement configured command guardrails."""

from __future__ import annotations

import re


def check_regex(command: str, check: dict):
    """Return the first matching pattern's block decision, or allow."""
    for pattern in check["patterns"]:
        if re.search(pattern, command):
            return {"decision": "block", "pattern": pattern}
    return {"decision": "allow"}
