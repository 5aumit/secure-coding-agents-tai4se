"""Deterministic shared mini loop and Inspect environment checks."""

import json
from threading import Event

import anyio
import pytest

from agents.agent import InspectEnvironment, _messages_for_scorer
from agents.security import CheckFailure
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
    from agents import security

    raw = FakeEnvironment()
    model_commands(monkeypatch, ["forbidden"])
    monkeypatch.setattr(security.re, "search", lambda *_: (_ for _ in ()).throw(RuntimeError("broken")))
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
        assert "Blocked by security check regex" in messages[1].content

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
