import asyncio

import pytest
from datetime import datetime, timezone
from types import SimpleNamespace
from contextlib import contextmanager
from dataclasses import replace

from inspect_ai.event import ModelEvent, ToolEvent
from inspect_ai.hooks import RunEnd, SampleEnd, SampleEvent, SampleScoring, SampleStart
from inspect_ai.log import EvalSample
from inspect_ai._util.error import EvalError
from inspect_ai.model import GenerateConfig, ModelOutput, ModelUsage
from inspect_ai.tool._tool_call import ToolCallError
from inspect_ai.scorer import Score

from agents.tracing import LangfuseHooks, validate_langfuse_config


@pytest.fixture(autouse=True)
def active_model(monkeypatch):
    monkeypatch.setattr("agents.tracing.get_model", lambda: SimpleNamespace(name="qwen/qwen3-coder-30b-a3b-instruct"))


class FakeObservation:
    def __init__(self, name="root"):
        self.name = name
        self.children = []
        self.updates = []
        self.ended = False
        self.scores = []
        self._otel_span = SimpleNamespace(
            get_span_context=lambda: SimpleNamespace(trace_id=123456789)
        )

    def start_observation(self, **kwargs):
        child = FakeObservation(kwargs["name"])
        child.params = kwargs
        self.children.append(child)
        return child

    def update(self, **kwargs):
        self.updates.append(kwargs)
        return self

    def end(self, **kwargs):
        self.ended = True
        return self

    def score_trace(self, **kwargs):
        self.scores.append(kwargs)


class FakeClient:
    def __init__(self):
        self.roots = []
        self.flushed = 0

    def start_observation(self, **kwargs):
        root = FakeObservation()
        root.params = kwargs
        self.roots.append(root)
        return root

    def flush(self):
        self.flushed += 1


def run(coro):
    return asyncio.run(coro)


def sample_start(sid):
    summary = SimpleNamespace(id=sid, input=f"task {sid}", target="ok", epoch=1, metadata={})
    return SampleStart(eval_set_id=None, run_id="run-1", eval_id="eval-1", sample_id=sid, summary=summary)


def test_concurrent_samples_capture_model_tool_scores_and_flush(monkeypatch):
    monkeypatch.setenv("LANGFUSE_TRACING_ENABLED", "true")
    client = FakeClient()
    hook = LangfuseHooks(client)
    run(sample_start_for(hook, "a"))
    run(sample_start_for(hook, "b"))

    model = ModelEvent(
        model="openrouter/example/model",
        input=[], tools=[], tool_choice="auto", config=GenerateConfig(),
        output=ModelOutput.from_content("openrouter/example/model", "done").model_copy(
            update={"usage": ModelUsage(input_tokens=11, output_tokens=3)}
        ),
        working_start=1.25, working_time=0.5, completed=datetime.now(timezone.utc),
    )
    tool = ToolEvent(
        id="tc-1", function="bash", arguments={"cmd": "echo ok"}, result="tool failed",
        error=ToolCallError(type="unknown", message="tool failed"), failed=True,
        working_start=1.75, working_time=0.02,
    )
    run(hook.on_sample_event(SampleEvent(None, "run-1", "eval-1", "a", model)))
    run(hook.on_sample_event(SampleEvent(None, "run-1", "eval-1", "a", model)))  # duplicated Inspect delivery
    run(hook.on_sample_event(SampleEvent(None, "run-1", "eval-1", "b", tool)))
    run(hook.on_sample_scoring(SampleScoring(None, "run-1", "eval-1", "a")))

    score = Score(value={"accuracy": 1.0, "detected": False}, explanation="passed")
    sample_a = EvalSample(id="a", epoch=1, input="task a", target="ok", scores={"match": score})
    sample_b = EvalSample(
        id="b", epoch=1, input="task b", target="ok",
        error=EvalError(message="sample failed", traceback="", traceback_ansi=""),
    )
    run(hook.on_sample_end(SampleEnd(None, "run-1", "eval-1", "a", sample_a)))
    run(hook.on_sample_end(SampleEnd(None, "run-1", "eval-1", "b", sample_b)))
    run(hook.on_run_end(RunEnd(None, "run-1", None, [])))

    root_a, root_b = client.roots
    assert root_a.params["input"]["task"] == "task a"
    assert root_b.params["input"]["task"] == "task b"
    assert root_a.params["as_type"] == "span"
    assert root_a.children[0].params["as_type"] == "agent"
    generation = root_a.children[0].children[0]
    assert generation.params["as_type"] == "generation"
    assert generation.params["usage_details"] == {"input": 11, "output": 3}
    assert generation.params["metadata"]["working_time_seconds"] == 0.5
    assert generation.params["metadata"]["event_timestamp"]
    assert len(root_a.children[0].children) == 1  # same event ID exported once
    assert root_a.children[0].params["input"] == {"task": "task a"}
    tool_obs = root_b.children[0].children[0]
    assert tool_obs.params["as_type"] == "tool"
    assert tool_obs.params["input"]["arguments"] == {"cmd": "echo ok"}
    assert tool_obs.params["level"] == "ERROR"
    assert root_b.updates[-1]["level"] == "ERROR"
    assert {entry["name"] for entry in root_a.scores} == {"inspect/match/accuracy", "inspect/match/detected"}
    assert root_a.scores[0]["value"] in (1.0, False)
    assert root_a.updates[-1]["metadata"]["scoring_phase"] == "complete"
    assert root_a.children[0].updates[-1]["output"] == {"answer": sample_a.output.model_dump(mode="json", exclude_none=True)}
    assert root_a.ended and root_b.ended
    assert client.flushed == 1


async def sample_start_for(hook, sid):
    await hook.on_sample_start(sample_start(sid))


def test_disabled_hook_does_not_create_client(monkeypatch):
    monkeypatch.delenv("LANGFUSE_TRACING_ENABLED", raising=False)
    hook = LangfuseHooks()
    run(hook.on_sample_start(sample_start("a")))
    assert hook._client is None


def test_enabled_tracing_requires_keys_and_endpoint():
    validate_langfuse_config({"LANGFUSE_TRACING_ENABLED": "false"})
    with pytest.raises(ValueError) as exc_info:
        validate_langfuse_config({"LANGFUSE_TRACING_ENABLED": "true"})
    message = str(exc_info.value)
    assert "LANGFUSE_PUBLIC_KEY" in message
    assert "LANGFUSE_SECRET_KEY" in message
    assert "LANGFUSE_BASE_URL" in message
    assert "pk-lf" not in message


@pytest.mark.parametrize("label", [None, "smoke", "experiment-" + "x" * 250 + "é"])
def test_readable_sessions_group_samples_and_keep_runs_distinct(monkeypatch, label):
    monkeypatch.setenv("LANGFUSE_TRACING_ENABLED", "true")
    if label is None:
        monkeypatch.delenv("EXPERIMENT_NAME", raising=False)
    else:
        monkeypatch.setenv("EXPERIMENT_NAME", label)
    attributes = []

    @contextmanager
    def capture_attributes(**kwargs):
        attributes.append(kwargs)
        yield

    monkeypatch.setattr("langfuse.propagate_attributes", capture_attributes)
    client = FakeClient()
    hook = LangfuseHooks(client)
    run(hook.on_sample_start(sample_start("a")))
    run(hook.on_sample_start(sample_start("b")))
    run(hook.on_sample_start(replace(sample_start("c"), run_id="run-2")))
    first, second, third = [item["session_id"] for item in attributes]
    assert first == second
    assert first != third
    assert first.startswith("codeipi / qwen3-coder-30b-a3b-instruct / ")
    assert first.endswith(" / run-1") and third.endswith(" / run-2")
    assert first.isascii() and len(first) < 200
    if label is None:
        assert " / baseline / " in first
    elif label == "smoke":
        assert " / smoke / " in first
    assert attributes[0]["metadata"]["inspect_run_id"] == "run-1"
    assert [root.params["name"] for root in client.roots] == ["a", "b", "c"]
