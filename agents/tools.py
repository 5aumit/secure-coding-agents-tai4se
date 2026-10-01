"""Tools available to the coding agent (executed in the task sandbox)."""

from inspect_ai.tool import Tool, bash, python


def get_tools(enabled_tools: list[str] | None = None) -> list[Tool]:
    """Create fresh tool instances for each solver."""
    factories = {"bash": bash, "python": python}
    names = ["bash", "python"] if enabled_tools is None else enabled_tools
    unknown = set(names) - factories.keys()
    if unknown:
        raise ValueError(f"Unknown tools: {', '.join(sorted(unknown))}")
    return [factories[name](timeout=120) for name in names]
