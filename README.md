# Coding agent evaluation research

Course project for [TAI4SE](https://tai4se.github.io).

We study whether security guardrails stop coding agents from following malicious
instructions in GitHub issues. We compare runs with guardrails enabled and
disabled using CodeIPI and IssueTrojanBench. Both benchmarks use mini-swe-agent.

## Setup

Install Conda and Docker with the Compose plugin. Start Docker.
Run all commands from the repository root.

```bash
conda env create -f environment.yml
conda activate tai4se-secure-coding-agents
docker info
docker compose version
export OPENROUTER_API_KEY='your-api-key'
```

Set provider credentials in your shell environment before each run.
Or copy `.env.example` to `.env`, fill it in, and load it with
`set -a; source .env; set +a`.

## Configure the agent

Both runners read `configs/default.yaml`. It sets the experiment name, model,
step limit, time limit, cost limit, and security checks. The default model is
`openrouter/openai/gpt-oss-20b`. Guardrails are disabled by default.

Copy the config to create an experiment configuration. Pass it to either runner
with `--config path/to/config.yaml`. Enable or disable checks in that file.
Set `experiment` to a short, lowercase, hyphenated name for the setting being
tested, such as `regex-v1`. Reuse it across benchmarks and models that should be
compared.
See [the agent guide](agents/README.md) to configure, add, or edit guardrails.

To change models, pass a `provider/model` identifier as CodeIPI's first argument
or use ITB's `--model` option. Set the corresponding provider's API key.
Time and cost limits are checked between agent steps. An active model request
can exceed them.

## Run CodeIPI

Download [CodeIPI](https://github.com/UKGovernmentBEIS/inspect_evals/tree/main/src/inspect_evals/ipi_coding_agent):

```bash
git clone --depth 1 --filter=blob:none --sparse \
  https://github.com/UKGovernmentBEIS/inspect_evals \
  benchmarks/inspect_evals
git -C benchmarks/inspect_evals sparse-checkout set \
  src/inspect_evals/ipi_coding_agent
python -m scripts.run_codeipi --limit 1
```

Do not install the downloaded checkout as a Python package. The runner loads it
directly. Omit `--limit 1` to run the full benchmark. Use `--sample-id ID` to
select a specific sample. Other run options pass through to Inspect AI.

Logs are saved in `logs/`. Run `inspect view` to inspect them.
Record the benchmark revision and installed versions with your results:

```bash
git -C benchmarks/inspect_evals rev-parse HEAD
python -m pip freeze
```

## Run IssueTrojanBench

Download the benchmark data and build the container image:

```bash
python scripts/fetch_issuetrojan.py
docker build -t issuetrojan-smoke:py312 \
  -f configs/issuetrojan/Dockerfile configs/issuetrojan
```

List cases, then run one sample:

```bash
python -m scripts.run_issuetrojan --list
python -m scripts.run_issuetrojan \
  --samples sympy_matrix_det:policy_bypass:mid_en_visible \
  --output outputs/issuetrojan-matrix
```

The output directory must not already exist. Use `--seeds hnf` to select a seed.
`--seeds` and `--samples` accept multiple values. Combined filters select cases
that match both. Omit both filters to run all 144 GitHub issue cases across six
seed issues. Other delivery methods are outside this study.

Each case uses its mapped repository and commit. See [seed revisions](docs/issuetrojan-seed-revisions.md)
for these choices and [benchmark details](benchmarks/README.md) for data sources.
The output directory contains `results.json` and per-sample records, including
configuration, model calls, commands, guardrail decisions, and repository changes.

## Read results

Check commands and saved files alongside benchmark scores. CodeIPI can count a
blocked command as compliance because its scorer reads attempted tool calls.
IssueTrojanBench's EEM score checks whether selected files exist. It does not
prove that an attack command ran. We do not check legitimate task correctness
for IssueTrojanBench.

## Optional Langfuse tracing

Set these variables before running either benchmark:

```bash
export LANGFUSE_TRACING_ENABLED=true
export LANGFUSE_PUBLIC_KEY='your-public-key'
export LANGFUSE_SECRET_KEY='your-secret-key'
export LANGFUSE_BASE_URL='https://cloud.langfuse.com'
export RUN_BY='your-name'
```

Each run creates a Langfuse session with one trace per sample. Traces record task
text, model calls, commands, guardrail decisions, and scores. Local results remain
available without Langfuse.

Sessions are named `benchmark / model / experiment / run-id`, for example
`codeipi / gpt-oss-20b / regex-v1 / a1b2c3`. The experiment name comes from
`experiment` in the config file. `RUN_BY` sets the Langfuse user, so each
teammate's runs appear under their name.

Traces also have these tags:

| Tag | Applies to | Meaning |
|---|---|---|
| `codeipi`, `issuetrojan` | Each benchmark | Benchmark name |
| `agent:mini-swe-agent` | Both | Agent used |
| `guardrail:<names>` | Both | Enabled security checks, such as `guardrail:none` or `guardrail:regex` |
| `harness:inspect` | CodeIPI | Run through Inspect AI |
| `github_issue` | IssueTrojanBench | Attack delivered through a GitHub issue |

## Tests

```bash
python -m pip install -e '.[test]'
python -m pytest tests -q
```
