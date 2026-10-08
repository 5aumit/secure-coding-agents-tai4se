# Coding agent evaluation research

A minimal research project for evaluating coding agents with Inspect AI,
starting with CodeIPI's indirect prompt injection tasks. Our solver wraps
Inspect's basic ReAct agent with bash and Python tools. Model selection happens
at runtime.

## Conda environment

From the repository root:

```bash
conda env create -f environment.yml
conda activate secure-coding-agents
```

This installs Python 3.12, Inspect AI, PyYAML, and this project's `agents`
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
is the only benchmark we need. Sparse checkout keeps its entire directory,
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
dependencies.

Record the benchmark commit and installed versions with each research run:

```bash
git -C benchmarks/inspect_evals rev-parse HEAD
python -m pip freeze
```

## Run CodeIPI

Set your model provider's API key in the environment, then supply a model:

```bash
export OPENAI_API_KEY='your-api-key'
bash scripts/run_codeipi.sh openai/gpt-4o --limit 1
# Omit --limit 1 to run the full benchmark.
```

Replace the example model with your chosen Inspect `provider/model` identifier.
For other providers, set their corresponding API key instead.

`configs/default.yaml` sets `model` (null by default), `enabled_tools`, and
`max_messages`. The first script argument overrides the configured model;
`INSPECT_EVAL_MODEL` is a fallback. Remaining arguments are passed to Inspect.
The runner maps `max_messages` to Inspect's `--message-limit` and passes the
tool list to our solver.

The equivalent default command is:

```bash
PYTHONPATH="$PWD/benchmarks/inspect_evals/src${PYTHONPATH:+:$PYTHONPATH}" \
inspect eval \
  benchmarks/inspect_evals/src/inspect_evals/ipi_coding_agent/ipi_coding_agent.py \
  --solver agents/agent.py@coding_agent \
  --model openai/gpt-4o \
  -S 'enabled_tools=["bash", "python"]' \
  --message-limit 30
```

The solver override preserves CodeIPI's workspace setup, dataset, sandbox,
and scorers. It replaces CodeIPI's default agent prompt (including its defense
warning) with Inspect's default ReAct prompt. Upstream `defense_prompt` therefore
does not change our agent's prompt. ReAct also supplies its standard submission
tool. Logs are written to `logs/`; view them with `inspect view`.

## Langfuse tracing

Tracing is disabled by default. To record CodeIPI runs, supply your Langfuse
project settings through the environment:

```bash
export LANGFUSE_TRACING_ENABLED=true
export LANGFUSE_PUBLIC_KEY='your-public-key'
export LANGFUSE_SECRET_KEY='your-secret-key'
export LANGFUSE_BASE_URL='https://cloud.langfuse.com'
export EXPERIMENT_NAME='baseline'
bash scripts/run_codeipi.sh openai/gpt-4o --limit 1
```

Each sample has a trace containing the task, agent model calls, tool results,
scores, and errors. Samples from the same Inspect run share a session.
`EXPERIMENT_NAME` labels that session. The hook sends pending records when the
run ends. Traces contain task text and model/tool inputs and outputs.

## Basic checks

```bash
python -m compileall -q agents
python -c 'from agents.agent import coding_agent; from agents.tools import get_tools; coding_agent(); print("Imports and solver construction OK")'
bash -n scripts/run_codeipi.sh
python -m pytest tests -q
```
