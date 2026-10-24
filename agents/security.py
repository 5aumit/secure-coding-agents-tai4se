"""Ordered checks for commands proposed by mini-swe-agent."""

from __future__ import annotations

import re

from agents.guardrails import check_regex


class CheckFailure(RuntimeError):
    """A configured check failed; the sample must not be scored."""


_CHECKS = {"regex": check_regex}
_BLOCKED_RESULT = {"returncode": 1, "output": "Command blocked by security policy.", "exception_info": ""}


def validate_checks(checks):
    if not isinstance(checks, list):
        raise ValueError("security.checks must be a list")
    names = set()
    for check in checks:
        if not isinstance(check, dict) or set(check) != {"name", "enabled", "patterns"}:
            raise ValueError("Each check needs name, enabled, and patterns")
        name = check["name"]
        if not isinstance(name, str) or name not in _CHECKS or name in names:
            raise ValueError(f"Unknown or duplicate security check: {name}")
        names.add(name)
        if not isinstance(check["enabled"], bool) or not isinstance(check["patterns"], list):
            raise ValueError("Check enabled must be boolean and patterns must be a list")
        for pattern in check["patterns"]:
            if not isinstance(pattern, str):
                raise ValueError("Regex patterns must be strings")
            re.compile(pattern)
    return checks


class GuardedEnvironment:
    """Check model commands, then delegate allowed commands to mini's environment."""

    def __init__(self, env, checks, record):
        self.env = env
        self.checks = validate_checks(checks)
        self.record = record
        self.error = None

    def __getattr__(self, name):
        return getattr(self.env, name)

    def execute(self, action: dict, **kwargs):
        command = action.get("command", "")
        try:
            for check in self.checks:
                if not check["enabled"]:
                    continue
                decision = _CHECKS[check["name"]](command, check)
                if decision["decision"] == "block":
                    result = _BLOCKED_RESULT.copy()
                    self.record({"action": action, "check": check["name"], **decision, "result": result})
                    return result
                self.record({"action": action, "check": check["name"], **decision})
        except Exception as exc:
            self.error = CheckFailure(f"Security check failed: {type(exc).__name__}")
            self.record({"action": action, "decision": "error", "error_type": type(exc).__name__})
            raise self.error from None
        self.record({"action": action, "decision": "execute"})
        return self.env.execute(action, **kwargs)
