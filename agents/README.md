# Shared coding agent

CodeIPI and IssueTrojanBench use the same mini-swe-agent and command guardrails.
Benchmark runners provide the task and container, then score the result.
See the [project README](../README.md) for setup and run commands.

| File | Purpose |
|---|---|
| `swe.py` | Loads configuration, runs the agent, and records model calls and guardrail decisions. |
| `agent.py` | Connects the agent to CodeIPI's Inspect AI container and scorer. |
| `guardrails.py` | Defines guardrail classes, their shared result type, and supported guardrail names. |
| `security.py` | Validates settings and checks commands before execution. |
| `tracing.py` | Sends CodeIPI events and scores to Langfuse. Shared model tracing is in `swe.py`. |

## Command checks

`GuardedEnvironment.execute()` calls enabled guardrails in configuration order.
The first block stops the command. If no guardrail blocks it, the container
executes it. Disabled guardrails do not run.

Every block returns `Command blocked by security policy.` to the agent.
Matched patterns and other details stay in local records and optional Langfuse
traces. A guardrail error raises `CheckFailure` and leaves the sample unscored.

Checks apply only before agent commands. They do not check tool results,
benchmark setup, or scoring commands. The regex guardrail checks command text.
Encoded or assembled filenames can bypass it.

## Configure a guardrail

Copy `configs/default.yaml` to an experiment config. Keep its model and limits,
and set `experiment` to a name for the guardrail setting, such as `regex-v1`.
Edit the security section:

```yaml
security:
  checks:
    - name: regex
      enabled: true
      patterns:
        - '(?i)\.cursorrules|CLAUDE\.md|AGENTS\.md'
```

Pass the file to either runner with `--config path/to/config.yaml`.
Set `enabled: false` to disable a guardrail. Keep other settings identical when
comparing runs with and without that guardrail.

## Add or edit a guardrail

1. Edit `RegexGuardrail` or add a `Guardrail` subclass in `guardrails.py`.
   Implement `check(command, settings)`. Return `GuardrailResult` with a Boolean
   `blocked` value and an optional `details` dictionary for internal records.
2. Register an instance under its configuration name in `SUPPORTED_GUARDRAILS`.
3. Update `validate_checks()` in `security.py` if the guardrail needs different
   settings. Currently all checks require `name`, `enabled`, and `patterns`.
4. Verify blocks, disabled checks, generic feedback, and internal records in
   `tests/test_swe.py`. Run `python -m pytest tests/test_swe.py -q`.

Use string keys in `details`. The keys `action`, `check`, `decision`, and `result`
are reserved. Invalid return values cause `CheckFailure`.
