"""Replay commands against each regex level without running a model.

Default: replay the labeled cases in ``cases.py`` and report blocks per level.
With ``--decisions``: replay the agent commands recorded in IssueTrojanBench
``decisions.jsonl`` files (or a directory containing them) from earlier runs.

    python -m regex_guardrail.replay
    python -m regex_guardrail.replay --decisions outputs/issuetrojan-run
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from agents.guardrails import RegexGuardrail
from agents.security import validate_checks
from regex_guardrail.cases import ATTACKS, BENIGN

LEVEL_FILES = {
    1: Path(__file__).with_name("l1_loose.yaml"),
    2: Path(__file__).with_name("l2_moderate.yaml"),
    3: Path(__file__).with_name("l3_strict.yaml"),
}


def load_level(level: int) -> dict:
    """Return the validated regex check from a level config."""
    config = yaml.safe_load(LEVEL_FILES[level].read_text(encoding="utf-8"))
    (check,) = validate_checks(config["security"]["checks"])
    return check


def matched_pattern(command: str, check: dict) -> str | None:
    """Use the repo's RegexGuardrail so replay matches real runs."""
    result = RegexGuardrail().check(command, check)
    return result.details.get("pattern") if result.blocked else None


def replay_cases(checks: dict[int, dict]) -> None:
    for label, cases in (("attacks", ATTACKS), ("benign", BENIGN)):
        print(f"\n{label} ({len(cases)} commands)")
        print(f"  {'name':40} {'L1':>3} {'L2':>3} {'L3':>3}")
        for case in cases:
            marks = ["X" if matched_pattern(case.command, checks[l]) else "." for l in (1, 2, 3)]
            print(f"  {case.name:40} {marks[0]:>3} {marks[1]:>3} {marks[2]:>3}")
    print("\nsummary (X = blocked)")
    for level, check in checks.items():
        attacks = sum(bool(matched_pattern(c.command, check)) for c in ATTACKS)
        benign = sum(bool(matched_pattern(c.command, check)) for c in BENIGN)
        print(f"  L{level}: attacks blocked {attacks}/{len(ATTACKS)}, benign blocked {benign}/{len(BENIGN)}")


def recorded_commands(path: Path) -> list[tuple[str, str]]:
    """Return (source, command) for each agent command in decisions.jsonl files.

    Each command is counted once, at its final "execute" or "block" row.
    """
    files = sorted(path.rglob("decisions.jsonl")) if path.is_dir() else [path]
    commands = []
    for file in files:
        for line in file.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if row.get("decision") in ("execute", "block"):
                commands.append((file.parent.name, row["action"].get("command", "")))
    return commands


def replay_decisions(path: Path, checks: dict[int, dict]) -> None:
    commands = recorded_commands(path)
    if not commands:
        raise SystemExit(f"No recorded commands found under {path}")
    print(f"{len(commands)} recorded commands from {path}")
    for level, check in checks.items():
        blocked = [(src, cmd) for src, cmd in commands if matched_pattern(cmd, check)]
        print(f"\nL{level}: would block {len(blocked)}/{len(commands)}")
        for src, cmd in blocked:
            print(f"  [{src}] {cmd.splitlines()[0][:120] if cmd else ''}")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--decisions", type=Path, help="decisions.jsonl file or run output directory")
    args = parser.parse_args(argv)
    checks = {level: load_level(level) for level in LEVEL_FILES}
    if args.decisions:
        replay_decisions(args.decisions, checks)
    else:
        replay_cases(checks)


if __name__ == "__main__":
    main()
