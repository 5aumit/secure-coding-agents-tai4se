"""Deterministic shared mini loop and Inspect environment checks."""

import json
from threading import Event

import anyio
import pytest

from agents.agent import InspectEnvironment, _messages_for_scorer
from agents.guardrails import SUPPORTED_GUARDRAILS, Guardrail, GuardrailResult, RegexGuardrail
from agents.security import CheckFailure, GuardedEnvironment, validate_checks
from agents.swe import load_config, run_swe


def model_commands(monkeypatch, commands):
    """Replace provider calls in tests without a runtime model injection hook."""
    from minisweagent.models.litellm_model import LitellmModel

    responses = iter(commands)

    def query(self, messages):
        return {"role": "assistant", "content": "working", "extra": {"actions": [{"command": next(responses), "tool_call_id": "call-1"}], "cost": 0.0}}

    monkeypatch.setattr(LitellmModel, "query", query)


class FakeEnvironment:
    def __init__(self):
        self.commands = []

    def execute(self, action, **kwargs):
        from minisweagent.exceptions import Submitted

        self.commands.append(action["command"])
        if action["command"] == "echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT":
            raise Submitted({"role": "exit", "content": "done", "extra": {"exit_status": "Submitted", "submission": "done"}})
        return {"output": "ok", "returncode": 0, "exception_info": ""}

    def get_template_vars(self):
        return {"system": "Linux", "release": "test", "version": "test", "machine": "test"}

    def serialize(self):
        return {}


def config(enabled=False):
    return {"model": "test/model", "limits": {"steps": 4, "seconds": 30, "cost_usd": 1}, "security": {"checks": [{"name": "regex", "enabled": enabled, "patterns": ["forbidden"]}]}}


def test_guardrail_requires_check():
    class MissingCheck(Guardrail):
        pass

    with pytest.raises(TypeError, match="abstract"):
        Guardrail()
    with pytest.raises(TypeError, match="abstract"):
        MissingCheck()


@pytest.mark.parametrize("enabled,patterns,expected", [
    (True, ["forbidden"], [("second", "block")]),
    (True, ["absent"], [("second", "allow"), ("first", "block")]),
    (False, ["forbidden"], [("first", "block")]),
])
def test_explicit_registration_and_config_order(monkeypatch, enabled, patterns, expected):
    monkeypatch.setitem(SUPPORTED_GUARDRAILS, "first", RegexGuardrail())
    monkeypatch.setitem(SUPPORTED_GUARDRAILS, "second", RegexGuardrail())
    checks = [
        {"name": "second", "enabled": enabled, "patterns": patterns},
        {"name": "first", "enabled": True, "patterns": ["forbidden"]},
    ]
    raw, decisions = FakeEnvironment(), []
    GuardedEnvironment(raw, checks, decisions.append).execute({"command": "forbidden"})
    assert [(row["check"], row["decision"]) for row in decisions] == expected
    assert raw.commands == []


@pytest.mark.parametrize("invalid", [
    None,
    {"blocked": False},
    GuardrailResult(blocked="false"),
    GuardrailResult(blocked=0),
    GuardrailResult(blocked=False, details=None),
    GuardrailResult(blocked=False, details=[]),
    GuardrailResult(blocked=False, details={1: "invalid key"}),
    *[GuardrailResult(blocked=False, details={key: "override"})
      for key in ("action", "check", "decision", "result")],
])
def test_malformed_result_stops_sample(tmp_path, monkeypatch, invalid):
    model_commands(monkeypatch, ["forbidden"])
    monkeypatch.setattr(SUPPORTED_GUARDRAILS["regex"], "check", lambda *_: invalid)
    raw = FakeEnvironment()
    path = tmp_path / "trajectory.json"
    with pytest.raises(CheckFailure, match="TypeError"):
        run_swe("issue", raw, "test/model", config(True), output_path=path)
    assert raw.commands == []
    saved = json.loads(path.read_text())
    assert saved["info"]["security_decisions"] == [
        {"action": {"command": "forbidden", "tool_call_id": "call-1"}, "decision": "error", "error_type": "TypeError"}
    ]


def test_internal_details_never_change_agent_feedback(tmp_path, monkeypatch):
    model_commands(monkeypatch, ["forbidden", "echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT"])
    details = {"pattern": "forbidden", "reason": "internal reason", "output": "private output",
               "returncode": 0, "exception_info": "private exception"}
    monkeypatch.setattr(SUPPORTED_GUARDRAILS["regex"], "check", lambda command, _: (
        GuardrailResult(blocked=True, details=details) if command == "forbidden" else GuardrailResult(blocked=False)
    ))
    path = tmp_path / "trajectory.json"
    run = run_swe("issue", FakeEnvironment(), "test/model", config(True), output_path=path)
    expected = {"returncode": 1, "output": "Command blocked by security policy.", "exception_info": ""}
    assert run["decisions"][0] == {
        "action": {"command": "forbidden", "tool_call_id": "call-1"}, "check": "regex",
        "decision": "block", **details, "result": expected,
    }
    saved = json.loads(path.read_text())
    assert saved["info"]["security_decisions"] == run["decisions"]
    tool_message = next(message for message in run["agent"].messages if message["role"] == "tool")
    assert json.loads(tool_message["content"]) == {"returncode": 1, "output": expected["output"]}


@pytest.mark.parametrize("checks", [
    [{"name": "unknown", "enabled": True, "patterns": []}],
    [{"name": "regex", "enabled": True, "patterns": []}] * 2,
    [{"name": "regex", "enabled": False, "patterns": ["["]}],
])
def test_registration_does_not_relax_config_validation(checks):
    import re

    with pytest.raises((ValueError, re.error)):
        validate_checks(checks)


@pytest.mark.parametrize("enabled,patterns,blocked_pattern", [
    (False, ["forbidden"], None),
    (True, [], None),
    (True, ["absent"], None),
    (True, ["absent", "forbidden", "forbid"], "forbidden"),
    (True, [""], ""),
])
def test_guarded_environment_decisions_and_forwarding(enabled, patterns, blocked_pattern):
    calls, decisions = [], []
    result = {"output": "ok", "returncode": 0, "exception_info": ""}

    class Environment:
        def execute(self, action, **kwargs):
            calls.append((action, kwargs))
            return result

    action = {"command": "echo forbidden", "tool_call_id": "call-1"}
    guarded = GuardedEnvironment(Environment(), [{"name": "regex", "enabled": enabled, "patterns": patterns}], decisions.append)
    actual = guarded.execute(action, timeout=7)
    if blocked_pattern is not None:
        expected = {"returncode": 1, "output": "Command blocked by security policy.", "exception_info": ""}
        assert actual == expected
        assert decisions == [{"action": action, "check": "regex", "decision": "block", "pattern": blocked_pattern, "result": expected}]
        assert calls == []
    else:
        assert actual is result
        assert calls == [(action, {"timeout": 7})]
        expected = [{"action": action, "check": "regex", "decision": "allow"}] if enabled else []
        assert decisions == expected + [{"action": action, "decision": "execute"}]


@pytest.mark.parametrize("enabled,executed", [(False, True), (True, False)])
def test_stock_loop_and_security(tmp_path, monkeypatch, enabled, executed):
    model_commands(monkeypatch, ["forbidden", "echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT"])
    raw = FakeEnvironment()
    run = run_swe("issue", raw, "test/model", config(enabled), output_path=tmp_path / "trajectory.json")
    assert ("forbidden" in raw.commands) is executed
    assert run["result"]["exit_status"] == "Submitted"
    assert run["decisions"][0]["decision"] == ("block" if enabled else "execute")
    assert json.loads((tmp_path / "trajectory.json").read_text())["info"]["security_decisions"] == run["decisions"]


def test_check_failure_stops_sample_and_never_executes(tmp_path, monkeypatch):
    from agents import guardrails

    raw = FakeEnvironment()
    model_commands(monkeypatch, ["forbidden"])
    monkeypatch.setattr(guardrails.re, "search", lambda *_: (_ for _ in ()).throw(RuntimeError("broken")))
    with pytest.raises(CheckFailure):
        run_swe("issue", raw, "test/model", config(True), output_path=tmp_path / "trajectory.json")
    assert raw.commands == []
    saved = json.loads((tmp_path / "trajectory.json").read_text())
    assert saved["info"]["security_decisions"][0]["decision"] == "error"
    assert "broken" not in (tmp_path / "trajectory.json").read_text()


def test_invalid_config_fails_before_run(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("model: test/model\nlimits: {steps: 2, seconds: 5, cost_usd: 1}\nsecurity:\n  checks:\n    - {name: llm, enabled: true, patterns: []}\n")
    with pytest.raises(ValueError, match="Unknown"):
        load_config(path)


def test_inspect_path_uses_workspace_and_preserves_scorer_inputs(monkeypatch):
    model_commands(monkeypatch, ["forbidden", "allowed", "echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT"])
    class Sandbox:
        def __init__(self):
            self.calls = []

        async def exec(self, cmd, **kwargs):
            self.calls.append((cmd, kwargs))
            class Result:
                stdout = "COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT\n" if "COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT" in cmd[-1] else "ok\n"
                stderr = ""
                returncode = 0

            return Result()

    async def check():
        sbx = Sandbox()
        env = InspectEnvironment(sbx)
        run = await anyio.to_thread.run_sync(lambda: run_swe("code task", env, "test/model", config(True)))
        assert [call[0][-1] for call in sbx.calls] == ["allowed", "echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT"]
        assert run["result"]["exit_status"] == "Submitted"
        assert all(call[1]["cwd"] == "/workspace" for call in sbx.calls)
        messages = _messages_for_scorer(run["agent"].messages)
        assert messages[0].tool_calls[0].arguments == {"command": "forbidden"}
        assert messages[1].content == '{\n  "returncode": 1,\n  "output": "Command blocked by security policy."\n}'

    anyio.run(check)


def test_inspect_cancellation_prevents_later_command(monkeypatch):
    import agents.agent as module
    from inspect_ai.model import ModelName
    from inspect_ai.solver import TaskState

    started, release, finished = Event(), Event(), Event()
    observed = []

    def delayed_run(task, env, model_name, config, **kwargs):
        started.set()
        release.wait(5)
        try:
            env.execute({"command": "after cancellation"})
        except RuntimeError as exc:
            observed.append(str(exc))
        finally:
            finished.set()

    monkeypatch.setattr(module, "run_swe", delayed_run)
    monkeypatch.setattr(module, "sandbox", lambda: object())
    state = TaskState(model=ModelName("test/model"), sample_id="one", epoch=0, input="task", messages=[], metadata={})

    async def check():
        async with anyio.create_task_group() as group:
            group.start_soon(module.coding_agent(), state, None)
            await anyio.to_thread.run_sync(started.wait)
            group.cancel_scope.cancel()
        release.set()
        await anyio.to_thread.run_sync(finished.wait)

    anyio.run(check)
    assert observed == ["Inspect sample cancelled"]


def test_codeipi_solver_records_effective_config_and_scorer_messages(monkeypatch):
    import agents.agent as module
    from inspect_ai.model import ModelName
    from inspect_ai.solver import TaskState

    captured = {}

    def fake_run(task, env, model_name, config, **kwargs):
        captured.update(task=task, model_name=model_name, config=config)
        kwargs["record"]({"decision": "block"})
        agent = type("Agent", (), {"messages": [
            {"role": "assistant", "content": "work", "extra": {"actions": [{"command": "forbidden", "tool_call_id": "call-1"}]}},
            {"role": "tool", "content": "blocked", "tool_call_id": "call-1"},
        ]})()
        return {"agent": agent, "result": {"submission": "done"}}

    monkeypatch.setattr(module, "run_swe", fake_run)
    monkeypatch.setattr(module, "sandbox", lambda: object())
    state = TaskState(model=ModelName("test/model"), sample_id="one", epoch=0, input="task text", messages=[], metadata={})

    async def check():
        return await module.coding_agent(model_name="override/model")(state, None)

    result = anyio.run(check)
    assert captured["task"] == "task text"
    assert captured["model_name"] == "override/model"
    assert result.metadata["swe_config"]["model"] == "override/model"
    assert result.metadata["swe_decisions"] == [{"decision": "block"}]
    assert result.messages[0].tool_calls[0].arguments == {"command": "forbidden"}
    assert result.messages[1].content == "blocked"
    assert result.output.completion == "done"


@pytest.mark.parametrize("reported, expected", [(0.0042, 0.0042), (None, "litellm"), (0, 0.0)])
def test_traced_model_prefers_provider_cost(monkeypatch, reported, expected):
    from types import SimpleNamespace

    from minisweagent.models.litellm_model import LitellmModel

    from agents.swe import TracedModel

    monkeypatch.setattr(LitellmModel, "_calculate_cost", lambda self, response: {"cost": "litellm"})
    model = TracedModel(trace=None, calls=[], cancelled=None, model_name="openrouter/example/model")
    response = SimpleNamespace(usage=SimpleNamespace(cost=reported))
    assert model._calculate_cost(response) == {"cost": expected}
