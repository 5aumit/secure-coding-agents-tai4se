#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

# Optional first argument overrides the configured model; remaining arguments
# are forwarded to Inspect (e.g. --limit 1).
python - "$@" <<'PY'
import json
import os
import sys
from pathlib import Path

import yaml

config = yaml.safe_load(Path("configs/default.yaml").read_text())
args = sys.argv[1:]
model = args.pop(0) if args and not args[0].startswith("-") else config["model"]
model = model or os.environ.get("INSPECT_EVAL_MODEL")
if not model:
    sys.exit("Usage: bash scripts/run_codeipi.sh PROVIDER/MODEL [inspect options]")
source = Path("benchmarks/inspect_evals/src").resolve()
task = source / "inspect_evals/ipi_coding_agent/ipi_coding_agent.py"
if not task.is_file():
    sys.exit("Sparse-clone CodeIPI into benchmarks/inspect_evals (see README.md).")
os.environ["PYTHONPATH"] = str(source) + (
    os.pathsep + os.environ["PYTHONPATH"] if os.environ.get("PYTHONPATH") else ""
)

os.execvp("inspect", [
    "inspect", "eval", str(task.relative_to(Path.cwd())),
    "--solver", "agents/agent.py@coding_agent",
    "--model", model,
    "-S", "enabled_tools=" + json.dumps(config["enabled_tools"]),
    "--message-limit", str(config["max_messages"]),
    *args,
])
PY
