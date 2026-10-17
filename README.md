# Coding agent evaluation research

A research project for CodeIPI and IssueTrojanBench prompt injection tasks.
Both benchmarks run stock mini-swe-agent through `agents.swe.run_swe`.
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

Keep local benchmark repositories and data in `benchmarks/`. Downloaded data is
ignored. The IssueTrojan adapter and `benchmarks/README.md` are maintained code.

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
Use `--config path/to/config.yaml` with either benchmark entry point.
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

For IssueTrojanBench, download its data and build its image first:

The fetcher stores downloaded data under `benchmarks/issuetrojan-data/issuetrojanbench`.
Maintained adapter code is under `benchmarks/issuetrojan/`.

```bash
python scripts/fetch_issuetrojan.py
docker build -t issuetrojan-smoke:py312 -f configs/issuetrojan/Dockerfile configs/issuetrojan
```

Use the same configuration:

```bash
.venv/bin/python -m scripts.run_issuetrojan --config configs/default.yaml --output outputs/issuetrojan-new
```

The default selects all 144 released GitHub issue cases: six seeds, four attacks,
and six variants per attack. Other delivery methods are outside this study.
List cases before a paid run, or select a seed or exact sample:

```bash
python -m scripts.run_issuetrojan --list
python -m scripts.run_issuetrojan --seeds hnf --list
python -m scripts.run_issuetrojan \
  --samples sympy_matrix_det:policy_bypass:mid_en_visible \
  --output outputs/issuetrojan-matrix
```

`--seeds` and `--samples` accept multiple values. Combined filters intersect.
Unknown values, duplicate filters, and empty selections fail before model calls.
`--data` accepts an extracted release directory. Limits and security checks come
from the shared config. Optional `--model`, `--steps`, `--seconds`, and
`--cost-limit` override those values for this run. Credentials come only from
the process environment. No host credentials or directories enter the container.

The seconds limit is checked between agent steps. An active model request or
provider retries can exceed it. Interrupting a run removes its container but
can leave its final summary and trace score incomplete.

If LiteLLM reports missing model pricing, supply mini's documented
[`LITELLM_MODEL_REGISTRY_PATH`](https://mini-swe-agent.com/latest/models/local_models/#cost-tracking)
with current provider prices. Keep default cost tracking enabled. Retain that
pricing file with the ignored run outputs so cost estimates can be checked.

Each case checks out its mapped repository and commit. Network access ends
after provisioning. Containers have CPU, RAM, and PID limits and are removed
in `finally`, including setup failures. Requests runtime dependencies and SymPy's
mpmath dependency are installed in the image before network access ends.
Provisioning installs the checked-out Requests package in editable mode so
Python can import its `src/` layout after network access ends.
See [seed revisions](docs/issuetrojan-seed-revisions.md) for checkout choices.

Results record the effective configuration, checkout identity, commands, patch,
indicator files, released EEM score, cleanup check, and optional trace URL.
The released executable scorer checks only file existence. It does not prove
that an attack command ran. Its persistence rule checks `.validate_refactor.sh`
for every seed, although some payloads request other files. Probe failures are
unscored. Inspect commands and files separately from EEM. Task correctness is
deferred. One sample does not establish resistance or task correctness.
[Earlier smoke results](docs/issuetrojan-smoke.md) describe the old matrix-only
runner and are historical.

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
