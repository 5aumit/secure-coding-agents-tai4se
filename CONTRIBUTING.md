# Contributing

Keep changes focused and easy to review. Link the relevant issue when one exists.

## Set up

Follow the [README](README.md) to set up Python 3.12 and Docker. Install test dependencies:

```bash
python -m pip install -e '.[test]'
```

Keep API keys in your shell or an ignored `.env` file. Never commit credentials or private trace content.

## Make changes

Create a branch from `origin/dev`. Keep benchmark-specific changes in their adapters and shared agent or guardrail changes in `agents/`.

For guardrail changes, follow the [agent guide](agents/README.md). Test that malicious commands are blocked without unnecessarily blocking legitimate commands. Verify disabled checks, error handling, generic block feedback, and internal records. Check failures must stop the sample rather than silently allowing execution.

Copy `configs/default.yaml` for experiment settings. Keep default guardrails disabled. Update existing documentation when changes affect setup, configuration, behavior, or scoring.

Prefer simple solutions over unnecessary abstractions, dependencies, or scaffolding. Follow existing patterns unless there is a clear reason to change them.

## Verify

Run the tests before opening a pull request:

```bash
python -m pytest tests -q
git diff --check
```

For runner or integration changes, also run a sample from the affected benchmark when credentials and Docker are available. Use the commands in the README.

Report checks actually performed, their results, and anything you could not verify. Distinguish unit tests from live benchmark runs.

## Record experiments

Keep the model, selected samples, limits, and other experimental settings identical when comparing guardrail configurations, unless the changed setting is the variable being studied.

Record the run ID, configuration, code revision, benchmark revision, package versions, selected samples, and repeat number when applicable.

Keep raw logs and results under the ignored `logs/` or `outputs/` directories. Include Langfuse trace links when available.

Inspect commands, outputs, and guardrail decisions alongside scores. Distinguish attempted attacks, successfully executed attacks, and legitimate task completion.

Be aware of benchmark limitations:

- **CodeIPI:** A blocked command may still count as compliance because the scorer examines attempted tool calls.
- **IssueTrojanBench:** EEM checks file existence, not whether a malicious command executed or the legitimate task succeeded.

Keep failed and unscored samples visible in analysis. Do not draw conclusions from scores beyond what the benchmark actually measures.

## Open a pull request

Target `dev` (`origin/dev`), never `main`.

Keep PRs focused, use a descriptive title, and link the relevant issue when one exists.

Include:

- **What and why:** Explain the problem, what changed, and important design decisions.
- **Verification:** Report checks actually run and their results. Include benchmark evidence when relevant.
- **Limitations:** Note known issues, untested behavior, and anything requiring closer review.

Explain decisions rather than narrating the diff. Link to relevant code when useful, and keep descriptions proportional to the change.

Exclude generated results, downloaded benchmarks, credentials, and unrelated changes from the diff.
