# Coding agent evaluation research

A research project for CodeIPI prompt injection tasks.
CodeIPI runs stock mini-swe-agent through `agents.swe.run_swe`.
`agents.security.GuardedEnvironment` checks commands proposed by the model.

## Conda environment

From the repository root:

```bash
conda env create -f environment.yml
conda activate tai4se-secure-coding-agents
```

This installs Python 3.12, Inspect AI, mini-swe-agent, and this project's `agents`
package in editable mode. Docker with the Compose plugin must also be installed
and running for CodeIPI's sandbox. Check it with `docker info` and
`docker compose version`.

## Benchmarks

Keep local benchmark repositories and data in `benchmarks/`. Its contents are
gitignored except for `benchmarks/README.md`.

```bash
git clone --depth 1 --filter=blob:none --sparse \
  https://github.com/UKGovernmentBEIS/inspect_evals \
  benchmarks/inspect_evals
git -C benchmarks/inspect_evals sparse-checkout set \
  src/inspect_evals/ipi_coding_agent
```

[CodeIPI](https://github.com/UKGovernmentBEIS/inspect_evals/blob/main/src/inspect_evals/ipi_coding_agent/README.md)
uses this upstream checkout. Sparse checkout keeps its entire directory,
including the dataset, scorers, setup code, and Docker files, plus files at the
repository root and ancestor directories. Other benchmark directories are not
checked out. `--depth 1` limits history; `--filter=blob:none` fetches file contents
as needed.

```text
benchmarks/
├── README.md
└── inspect_evals/
    ├── README.md, pyproject.toml, ...
    └── src/inspect_evals/
        ├── __init__.py, _registry.py, ...
        └── ipi_coding_agent/
            ├── ipi_coding_agent.py
            ├── setup.py, scorer.py, constants.py, ...
            ├── dataset/
            └── docker/
```

Do not install the sparse upstream checkout with `pip install -e`: its package
registry imports other benchmarks that are absent. The runner instead loads
CodeIPI by file path and adds the checkout's `src/` directory to `PYTHONPATH`
so its `inspect_evals.ipi_coding_agent` imports resolve. CodeIPI uses Inspect AI
and the Python standard library; the project environment supplies its Python
dependencies. Inspect and LiteLLM are pinned to compatible versions because
newer Inspect releases require OpenAI 3 while this LiteLLM release requires OpenAI 2.

Record the benchmark commit and installed versions with each research run:

```bash
git -C benchmarks/inspect_evals rev-parse HEAD
python -m pip freeze
```

## Run CodeIPI

Set your model provider's API key in the environment. Set the model in
`configs/default.yaml` or pass it as the first argument:

```bash
export OPENAI_API_KEY='your-api-key'
python -m scripts.run_codeipi openai/gpt-4o --limit 1
# Omit --limit 1 to run the full benchmark.
```

Replace the example model with your mini-swe-agent `provider/model` identifier.
For other providers, set their corresponding API key.

`configs/default.yaml` sets the model, mini limits, and ordered security checks.
Use `--config path/to/config.yaml` with the CodeIPI entry point.
The first script argument overrides the configured model. Other arguments go
to Inspect. Set `CODEIPI_SOURCE` to the upstream `src` directory when CodeIPI
is outside this worktree.

The equivalent default command is:

```bash
python -m scripts.run_codeipi openai/gpt-4o --config configs/default.yaml --limit 1
```

The solver override preserves CodeIPI's dataset, workspace setup, sandbox,
and scorer. It uses stock mini prompts and submission handling.
The upstream `defense_prompt` option does not change mini's prompt.
Setup and scoring run outside the command guard. Inspect logs include the
effective configuration and decisions in sample metadata. With Langfuse enabled,
mini model calls and shell commands appear under the sample agent trace.
CodeIPI's code-execution scorer reads attempted tool calls. It can count a
blocked command as compliance even though the command did not execute.
Logs are written to `logs/`; view them with `inspect view`.

## Langfuse tracing

Tracing is disabled by default. To record CodeIPI runs, supply your Langfuse
project settings through the environment:

```bash
export LANGFUSE_TRACING_ENABLED=true
export LANGFUSE_PUBLIC_KEY='your-public-key'
export LANGFUSE_SECRET_KEY='your-secret-key'
export LANGFUSE_BASE_URL='https://cloud.langfuse.com'
export EXPERIMENT_NAME='baseline'
python -m scripts.run_codeipi openai/gpt-4o --limit 1
```

Each sample has a trace containing the task, agent model calls, tool results,
scores, and errors. Samples from the same Inspect run share a session.
`EXPERIMENT_NAME` labels that session. The hook sends pending records when the
run ends. Traces contain task text and model/tool inputs and outputs.

## Basic checks

```bash
python -m compileall -q agents scripts
python -c 'from agents.agent import coding_agent; coding_agent(); print("Solver construction OK")'
python -m pytest tests -q
```
