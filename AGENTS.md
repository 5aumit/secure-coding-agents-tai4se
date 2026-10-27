# Agent Instructions

## Project context

This repository evaluates prompt-injection security guardrails for coding agents using CodeIPI and IssueTrojanBench. Both benchmarks share a mini-swe-agent implementation.

Read the relevant documentation before making changes:

- [CONTRIBUTING.md](CONTRIBUTING.md) for development, verification, and PR guidelines.
- [README.md](README.md) for setup, configuration, and benchmark execution.
- [agents/README.md](agents/README.md) when modifying agent behavior or guardrails.
- [benchmarks/README.md](benchmarks/README.md) when modifying benchmark integrations.

## Development

- Create feature branches from `origin/dev`, not `main`.
- Keep changes minimal, focused, and consistent with existing code.
- Prefer simple solutions. Avoid unnecessary abstractions, dependencies, files, and scaffolding.
- Do not refactor unrelated code or introduce speculative functionality.
- Keep shared agent and guardrail logic in `agents/` and benchmark-specific logic in their adapters.
- Preserve existing behavior unless the task explicitly requires changing it.
- Do not silently modify benchmark scoring, experimental defaults, or evaluation methodology.
- Keep guardrails disabled in the default configuration unless explicitly requested otherwise.
- Never commit credentials, private traces, downloaded benchmarks, or generated experiment outputs.

## Verification

Follow the verification guidelines in `CONTRIBUTING.md`.

- Run relevant tests for changed behavior.
- For guardrails, test both blocking and legitimate command execution, including disabled checks and failures.
- Run a benchmark sample for integration changes when feasible.
- Report verification results accurately. Never claim a test or benchmark passed unless it was actually run.
- Do not add tests solely to increase coverage or duplicate existing tests.

## Pull requests

Follow the PR guidelines in `CONTRIBUTING.md`.

- **Always target the remote `dev` branch (`origin/dev`) when creating pull requests. Never target `main`.**
- Explain what changed and why, including important design decisions.
- Report actual verification results and remaining limitations.
- Link relevant code when it helps reviewers understand the implementation.
- Focus on reasoning and evidence rather than narrating the diff.
- Keep descriptions concise and proportional to the change.
- Do not claim that code was independently reviewed unless it was.

Treat documentation and experimental reproducibility as part of the implementation, not as optional follow-up work.