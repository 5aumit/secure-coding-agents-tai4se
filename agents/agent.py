"""Minimal ReAct coding agent; Inspect selects the model at runtime."""

from inspect_ai.agent import as_solver, react
from inspect_ai.solver import Solver, solver

from agents.tools import get_tools


@solver
def coding_agent(enabled_tools: list[str] | None = None) -> Solver:
    """Use Inspect's default ReAct prompt and the configured execution tools."""
    return as_solver(react(tools=get_tools(enabled_tools)))
