# Shared SWE agent

CodeIPI and IssueTrojanBench both use stock mini-swe-agent through `swe.run_swe()`.
The benchmark runners supply the task and sandbox, then score the result.
See the [root README](../README.md) for dependencies and benchmark setup.

- `swe.py`: loads configuration, applies agent limits, and records model calls and guardrail decisions.
- `agent.py`: connects the shared agent to CodeIPI's Inspect sandbox and scorer.
- `guardrails.py`: defines `Guardrail`, `GuardrailResult`, and the explicit `SUPPORTED_GUARDRAILS` mapping, currently with `RegexGuardrail`.
- `security.py`: validates check settings, selects checks by name, and controls command execution.
- `tracing.py`: exports CodeIPI events and scores to Langfuse. Shared agent tracing is in `swe.py`.

## How guardrails work

```text
Agent proposes a shell command
  → security.py calls enabled guardrails in config order
  → first block returns a generic error without executing the command
  → otherwise the sandbox executes the command
```

Every block returns `Command blocked by security policy.` to the agent.
Check names, matched patterns, and other details stay in local records and optional
Langfuse observations. Guardrails do not choose the agent-facing message.
A check failure raises `CheckFailure`; the sample must not receive a benchmark score.

Checks run **before agent commands only**. They do not filter tool results, task text,
benchmark setup, or scoring commands. Regex checks inspect raw command text;
encoded or assembled filenames can bypass them.

## Edit or add a guardrail

1. Edit `RegexGuardrail` or add a `Guardrail` subclass in `guardrails.py`.
   Implement `check(command, settings)` and return `GuardrailResult(blocked=..., details={...})`.
   Details stay internal; regex records `pattern`. Do not use the reserved detail keys
   `action`, `check`, `decision`, or `result`. The executor rejects malformed results as `CheckFailure`.
2. Add an instance under its config name in `SUPPORTED_GUARDRAILS` in `guardrails.py`.
   No implementation import or mapping change is needed in `security.py`.
3. Update `validate_checks()` if the new check needs different settings.
   Currently every check requires `name`, `enabled`, and a list of regex `patterns`.
4. Check behavior in `tests/test_swe.py`, including blocks, disabled checks,
   generic feedback, and retained internal details.

## Configure and test

From the repository root, copy `configs/default.yaml` to an experiment config.
Keep its `model` and `limits` sections. Edit the security section, for example:

```yaml
security:
  checks:
    - name: regex
      enabled: true
      patterns:
        - '(?i)\.cursorrules|CLAUDE\.md|AGENTS\.md'
```

Set `enabled: false` to ablate a check. Keep other settings identical for comparisons.
Both runners default to `configs/default.yaml`; `--config` selects another file.

```bash
python -m pytest tests/test_swe.py -q
python -m scripts.run_codeipi --config configs/experiment.yaml --limit 1
python -m scripts.run_issuetrojan --config configs/experiment.yaml \
  --samples sympy_matrix_det:policy_bypass:mid_en_visible --output outputs/experiment
```

The ITB output directory must not already exist. Live runs require provider credentials
and Docker; enable Langfuse separately if traces are needed.
