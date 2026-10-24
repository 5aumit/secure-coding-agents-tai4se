"""Implement configured command guardrails."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class GuardrailResult:
    """A block decision and details for internal records only."""

    blocked: bool
    details: dict = field(default_factory=dict)


class Guardrail(ABC):
    @abstractmethod
    def check(self, command: str, settings: dict) -> GuardrailResult:
        """Check a proposed command without executing it."""


class RegexGuardrail(Guardrail):
    def check(self, command: str, settings: dict) -> GuardrailResult:
        """Block on the first matching pattern, or allow."""
        for pattern in settings["patterns"]:
            if re.search(pattern, command):
                return GuardrailResult(blocked=True, details={"pattern": pattern})
        return GuardrailResult(blocked=False)


SUPPORTED_GUARDRAILS = {"regex": RegexGuardrail()}
