"""Run CodeIPI through Inspect with the shared mini-swe-agent solver."""

import os
import sys
from pathlib import Path

from agents.swe import load_config


def main():
    os.chdir(Path(__file__).resolve().parent.parent)
    args = sys.argv[1:]
    config_path = Path("configs/default.yaml")
    if "--config" in args:
        index = args.index("--config")
        try:
            config_path = Path(args[index + 1])
        except IndexError:
            sys.exit("--config needs a YAML path")
        del args[index:index + 2]
    config = load_config(config_path)
    model = args.pop(0) if args and not args[0].startswith("-") else config["model"]
    model = model or os.environ.get("INSPECT_EVAL_MODEL")
    if not model:
        sys.exit("Set model in --config or pass PROVIDER/MODEL")
    source = Path(os.environ.get("CODEIPI_SOURCE", "benchmarks/inspect_evals/src")).resolve()
    task = source / "inspect_evals/ipi_coding_agent/ipi_coding_agent.py"
    if not task.is_file():
        sys.exit("Set CODEIPI_SOURCE or sparse-clone CodeIPI into benchmarks/inspect_evals (see README.md).")
    os.environ["PYTHONPATH"] = str(source) + (
        os.pathsep + os.environ["PYTHONPATH"] if os.environ.get("PYTHONPATH") else ""
    )

    os.execv(sys.executable, [
        sys.executable, "-m", "inspect_ai", "eval", os.path.relpath(task, Path.cwd()),
        "--solver", "agents/agent.py@coding_agent",
        "--model", model,
        "-S", "config_path=" + str(config_path.resolve()),
        "-S", "model_name=" + model,
        *args,
    ])


if __name__ == "__main__":
    main()
