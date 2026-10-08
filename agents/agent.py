"""Inspect solver that runs the shared stock mini-swe-agent in its sandbox."""

from __future__ import annotations

import platform
from threading import Event

import anyio
from inspect_ai.model import ChatMessageAssistant, ChatMessageTool, ModelOutput
from inspect_ai.solver import Generate, Solver, TaskState, solver
from inspect_ai.tool import ToolCall
from inspect_ai.util import sandbox

from agents.swe import load_config, observation, run_swe
from agents.tracing import current_agent_trace


class InspectEnvironment:
    """Give synchronous mini commands access to this sample's Inspect sandbox."""

    def __init__(self, sbx, cancelled=None, trace=None):
        self.sbx = sbx
        self.cancelled = cancelled or Event()
        self.trace = trace

    def get_template_vars(self):
        return {"cwd": "/workspace", **platform.uname()._asdict()}

    def serialize(self):
        return {"info": {"config": {"environment_type": "Inspect sandbox", "cwd": "/workspace"}}}

    def execute(self, action: dict, **kwargs):
        from minisweagent.environments.docker import DockerEnvironment

        if self.cancelled.is_set():
            raise RuntimeError("Inspect sample cancelled")

        async def execute():
            return await self.sbx.exec(
                ["bash", "-lc", action["command"]],
                cwd="/workspace",
                timeout=kwargs.get("timeout", 120),
                timeout_retry=False,
            )

        with observation(self.trace, "shell", "tool", input=action) as obs:
            result = anyio.from_thread.run(execute)
            output = {"output": result.stdout + result.stderr, "returncode": result.returncode, "exception_info": ""}
            if obs:
                obs.update(output=output)
        DockerEnvironment._check_finished(self, output)
        return output


def _messages_for_scorer(messages):
    """Expose mini's attempted commands and observations to CodeIPI's scorer."""
    converted = []
    for message in messages:
        if message.get("role") == "assistant":
            calls = [
                ToolCall(
                    id=action.get("tool_call_id", f"mini-{len(converted)}-{i}"),
                    function="bash",
                    arguments={"command": action["command"]},
                )
                for i, action in enumerate(message.get("extra", {}).get("actions", []))
            ]
            converted.append(ChatMessageAssistant(content=message.get("content") or "", tool_calls=calls or None))
        elif message.get("role") == "tool":
            converted.append(ChatMessageTool(content=message.get("content") or "", tool_call_id=message.get("tool_call_id"), function="bash"))
    return converted


@solver
def coding_agent(config_path: str = "configs/default.yaml", model_name: str | None = None) -> Solver:
    """Use CodeIPI setup and scorer around the shared mini runner."""
    config = load_config(config_path)

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        effective = {**config, "model": model_name or config["model"] or str(state.model)}
        state.metadata["swe_config"] = effective
        decisions = []
        state.metadata["swe_decisions"] = decisions
        cancelled = Event()
        trace = current_agent_trace.get()
        env = InspectEnvironment(sandbox(), cancelled, trace)
        try:
            run = await anyio.to_thread.run_sync(
                lambda: run_swe(
                    state.input_text, env, effective["model"], effective,
                    record=decisions.append, cancelled=cancelled, trace=trace,
                ),
                abandon_on_cancel=True,
            )
        finally:
            cancelled.set()
        state.messages.extend(_messages_for_scorer(run["agent"].messages))
        submission = run["result"].get("submission", "")
        state.output = ModelOutput.from_content(effective["model"], submission)
        state.completed = True
        return state

    return solve
