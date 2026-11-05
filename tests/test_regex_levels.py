"""Regex guardrail levels: config validity, nesting, and expected block levels."""

import pytest
import yaml

from agents.guardrails import RegexGuardrail
from agents.security import GuardedEnvironment
from regex_guardrail.cases import ATTACKS, BENIGN, SUBMIT_COMMAND
from regex_guardrail.replay import LEVEL_FILES, load_level, matched_pattern

LEVELS = (1, 2, 3)
CASES = ATTACKS + BENIGN


@pytest.fixture(scope="module")
def checks():
    return {level: load_level(level) for level in LEVELS}


def test_level_configs_match_default_settings():
    default = yaml.safe_load(open("configs/default.yaml", encoding="utf-8"))
    for path in LEVEL_FILES.values():
        config = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert set(config) == {"model", "limits", "security"}
        assert config["model"] == default["model"]
        assert config["limits"] == default["limits"]
        (check,) = config["security"]["checks"]
        assert check["name"] == "regex" and check["enabled"] is True


def test_runner_loads_level_configs():
    swe = pytest.importorskip("agents.swe", reason="needs the project environment (mini-swe-agent)")
    for path in LEVEL_FILES.values():
        assert swe.load_config(path)["security"]["checks"][0]["enabled"] is True


def test_each_level_contains_the_level_below(checks):
    for lower, higher in ((1, 2), (2, 3)):
        lower_patterns = checks[lower]["patterns"]
        higher_patterns = checks[higher]["patterns"]
        assert higher_patterns[: len(lower_patterns)] == lower_patterns
        assert len(higher_patterns) > len(lower_patterns)


def test_patterns_are_unique(checks):
    patterns = checks[3]["patterns"]
    assert len(patterns) == len(set(patterns))


@pytest.mark.parametrize("case", CASES, ids=[case.name for case in CASES])
def test_case_is_first_blocked_at_expected_level(case, checks):
    blocked = [level for level in LEVELS if matched_pattern(case.command, checks[level])]
    expected = [] if case.level is None else list(range(case.level, 4))
    assert blocked == expected


@pytest.mark.parametrize("level", LEVELS)
def test_submit_command_is_never_blocked(level, checks):
    assert matched_pattern(SUBMIT_COMMAND, checks[level]) is None


class RecordingEnvironment:
    def __init__(self):
        self.commands = []

    def execute(self, action, **kwargs):
        self.commands.append(action["command"])
        return {"output": "ok", "returncode": 0, "exception_info": ""}


def _attack(level):
    return next(case for case in ATTACKS if case.level == level)


STRICT_ONLY = next(case for case in BENIGN if case.level == 3)


@pytest.mark.parametrize(("level", "command", "blocked"), [
    (1, _attack(1).command, True),
    (1, _attack(2).command, False),
    (2, _attack(2).command, True),
    (2, STRICT_ONLY.command, False),
    (3, STRICT_ONLY.command, True),
])
def test_agent_loop_with_level_config(level, command, blocked, tmp_path, monkeypatch):
    """Run the real mini-swe-agent loop with a level config and a scripted model."""
    swe = pytest.importorskip("agents.swe", reason="needs the project environment (mini-swe-agent)")
    from minisweagent.exceptions import Submitted
    from minisweagent.models.litellm_model import LitellmModel

    benign = next(case for case in BENIGN if case.level is None).command
    responses = iter([command, benign, SUBMIT_COMMAND])
    monkeypatch.setattr(LitellmModel, "query", lambda self, messages: {
        "role": "assistant", "content": "working",
        "extra": {"actions": [{"command": next(responses), "tool_call_id": "call-1"}], "cost": 0.0},
    })

    class SubmittingEnvironment(RecordingEnvironment):
        def execute(self, action, **kwargs):
            if action["command"] == SUBMIT_COMMAND:
                raise Submitted({"role": "exit", "content": "done",
                                 "extra": {"exit_status": "Submitted", "submission": "done"}})
            return super().execute(action, **kwargs)

        def get_template_vars(self):
            return {"system": "Linux", "release": "test", "version": "test", "machine": "test"}

        def serialize(self):
            return {}

    env = SubmittingEnvironment()
    config = swe.load_config(LEVEL_FILES[level])
    run = swe.run_swe("issue", env, "test/model", config, output_path=tmp_path / "trajectory.json")

    assert run["result"]["exit_status"] == "Submitted"
    assert env.commands == ([benign] if blocked else [command, benign])
    assert run["decisions"][0]["decision"] == ("block" if blocked else "allow")
    tool_messages = [m["content"] for m in run["agent"].messages if m["role"] == "tool"]
    assert ("Command blocked by security policy." in tool_messages[0]) is blocked


@pytest.mark.parametrize("level", LEVELS)
def test_guarded_environment_enforces_level(level, checks):
    env, rows = RecordingEnvironment(), []
    guarded = GuardedEnvironment(env, [checks[level]], rows.append)
    attack = next(case for case in ATTACKS if case.level == 1)
    benign = next(case for case in BENIGN if case.level is None)

    blocked = guarded.execute({"command": attack.command})
    allowed = guarded.execute({"command": benign.command})

    assert blocked["output"] == "Command blocked by security policy."
    assert allowed["output"] == "ok"
    assert env.commands == [benign.command]
    block_row = next(row for row in rows if row["decision"] == "block")
    assert block_row["pattern"] in checks[level]["patterns"]
    assert RegexGuardrail().check(attack.command, checks[level]).details == {"pattern": block_row["pattern"]}
