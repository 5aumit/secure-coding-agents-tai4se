# Contributing

Keep each change focused on one issue. Link the issue in your pull request.

## Set up

Follow the [README](README.md) to create the Python 3.12 environment and set up
Docker. Install the test dependencies:

```bash
python -m pip install -e '.[test]'
```

Keep API keys in your shell or an ignored `.env` file. Do not commit credentials
or private trace content.

## Make changes

Create a branch from `main`. Keep benchmark-specific changes in their adapters.
Put shared agent and guardrail changes in `agents/`.

For guardrail changes, follow the [agent guide](agents/README.md). Check allowed
commands, blocked commands, disabled checks, and error handling. Preserve the
generic block message and detailed internal records.

Copy `configs/default.yaml` for experiment settings. Keep the default guardrails
disabled. Update existing documentation when your change affects setup,
configuration, or scoring.

## Verify

Run the tests before opening a pull request:

```bash
python -m pytest tests -q
git diff --check
```

For runner changes, also run one sample from the affected benchmark when
credentials and Docker are available. Use the commands in the README.
Report any checks you could not run.

## Record experiments

Keep the model, samples, and limits identical when comparing guardrails.
Record the run ID, full configuration, code revision, benchmark revision,
installed package versions, and selected sample IDs with the results.
Record a repeat number for repeated experiments.

Keep raw logs and results under the ignored `logs/` or `outputs/` directories.
Include Langfuse trace links when available. Inspect commands and outputs
alongside scores. A blocked command can count as compliance in CodeIPI.
IssueTrojan's EEM score checks file existence, not execution or task correctness.
Keep failed and unscored samples visible in analysis.

## Open a pull request

Use a short title and link the related issue. Include these sections:

- **How it works:** State the change and point to the relevant files.
- **Why this is ready:** List verification results and remaining limitations.

Exclude generated results, downloaded benchmarks, credentials, and unrelated
changes from the diff.
