"""Optional Inspect hooks that export CodeIPI sample traces to Langfuse."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from inspect_ai.event import ModelEvent, ToolEvent
from inspect_ai.hooks import Hooks, RunEnd, SampleEnd, SampleEvent, SampleScoring, SampleStart, hooks
from inspect_ai.model import get_model


def tracing_enabled() -> bool:
    return os.getenv("LANGFUSE_TRACING_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}


def validate_langfuse_config(environ: dict[str, str] | None = None) -> None:
    """Fail early with setting names only when tracing is explicitly enabled."""
    values = os.environ if environ is None else environ
    enabled = values.get("LANGFUSE_TRACING_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}
    if not enabled:
        return
    missing = [name for name in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY") if not values.get(name)]
    if not (values.get("LANGFUSE_BASE_URL") or values.get("LANGFUSE_HOST")):
        missing.append("LANGFUSE_BASE_URL (or LANGFUSE_HOST)")
    if missing:
        raise ValueError("Langfuse tracing is enabled but required settings are missing: " + ", ".join(missing))


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", exclude_none=True)
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _flatten_score(value: Any, prefix: str = "") -> list[tuple[str, int | float | bool | str]]:
    if isinstance(value, dict):
        flattened: list[tuple[str, int | float | bool | str]] = []
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            flattened.extend(_flatten_score(item, path))
        return flattened
    if isinstance(value, (bool, int, float, str)):
        return [(prefix, value)]
    return []


def _token_usage(event: ModelEvent) -> dict[str, int]:
    usage = getattr(event.output, "usage", None)
    if usage is None:
        return {}
    usage = _jsonable(usage)
    aliases = {
        "input": ("input_tokens", "prompt_tokens"),
        "output": ("output_tokens", "completion_tokens"),
    }
    result = {}
    for target, names in aliases.items():
        for name in names:
            value = usage.get(name) if isinstance(usage, dict) else None
            if isinstance(value, (int, float)):
                result[target] = int(value)
                break
    return result


@dataclass
class _SampleTrace:
    root: Any
    sample_id: str
    agent: Any = None
    scoring_started: bool = False
    seen_event_ids: set[str] = field(default_factory=set)


@hooks(name="Langfuse sample tracing", description="Exports Inspect sample, model, tool, scoring, and error events to Langfuse.")
class LangfuseHooks(Hooks):
    """One trace per sample, grouped into a Langfuse session per Inspect run."""

    def __init__(self, client: Any | None = None) -> None:
        self._client = client
        self._samples: dict[str, _SampleTrace] = {}
        self._sessions: dict[str, str] = {}

    def enabled(self) -> bool:
        return tracing_enabled()

    def _get_client(self) -> Any:
        if self._client is None:
            from langfuse import get_client

            self._client = get_client()
        return self._client

    async def on_sample_start(self, data: SampleStart) -> None:
        if not self.enabled():
            return
        from langfuse import propagate_attributes

        client = self._get_client()
        summary = data.summary
        sample_label = str(summary.id)
        trace_name = sample_label
        if data.run_id not in self._sessions:
            model = get_model().name.rsplit("/", 1)[-1]
            experiment = os.getenv("EXPERIMENT_NAME", "").strip() or "baseline"
            prefix = f"codeipi / {model} / {experiment}".encode("ascii", "replace").decode()
            suffix = f" / {data.run_id}"
            self._sessions[data.run_id] = prefix[:199 - len(suffix)] + suffix
        with propagate_attributes(
            session_id=self._sessions[data.run_id],
            trace_name=trace_name,
            metadata={"inspect_eval_id": data.eval_id, "inspect_run_id": data.run_id},
            tags=["inspect", "codeipi"],
        ):
            root = client.start_observation(
                name=trace_name,
                as_type="span",
                input={"task": _jsonable(summary.input), "target": _jsonable(summary.target)},
                metadata={
                    "sample_id": sample_label,
                    "sample_epoch": summary.epoch,
                    "sample_metadata": _jsonable(summary.metadata),
                    "setup_phase": "CodeIPI task-level sandbox setup precedes the coding agent",
                    "repo_files_present": bool(summary.metadata.get("repo_files")),
                    "injection_vector": summary.metadata.get("injection_vector"),
                    "payload_category": summary.metadata.get("payload_category"),
                    "severity": summary.metadata.get("severity"),
                    "scoring_phase": "pending",
                },
            )
        state = _SampleTrace(root=root, sample_id=sample_label)
        state.agent = root.start_observation(
            name="coding agent", as_type="agent", input={"task": _jsonable(summary.input)}
        )
        self._samples[data.sample_id] = state

    async def on_sample_event(self, data: SampleEvent) -> None:
        state = self._samples.get(data.sample_id)
        if state is None:
            return
        event = data.event
        event_id = getattr(event, "uuid", None)
        if event_id is not None:
            if event_id in state.seen_event_ids:
                return
            state.seen_event_ids.add(event_id)
        if isinstance(event, ModelEvent):
            output = _jsonable(event.output)
            usage = _token_usage(event)
            completed_at = _jsonable(event.completed)
            metadata = {
                "phase": "scoring" if state.scoring_started else "agent",
                "inspect_event_id": event.uuid,
                "role": event.role,
                "retries": event.retries,
                "cache": event.cache,
                "working_start_seconds": event.working_start,
                "working_time_seconds": event.working_time,
                "event_timestamp": _jsonable(event.timestamp),
                "completed_at": completed_at,
                "error": event.error,
                "traceback": event.traceback if event.error else None,
            }
            obs = state.agent.start_observation(
                name="model call",
                as_type="generation",
                model=event.model,
                input=_jsonable(event.input),
                output=output,
                usage_details=usage,
                metadata=metadata,
                level="ERROR" if event.error else None,
                status_message=event.error,
            )
            obs.end()
        elif isinstance(event, ToolEvent):
            failed = bool(event.failed or event.error)
            completed_at = _jsonable(event.completed)
            metadata = {
                "phase": "scoring" if state.scoring_started else "agent",
                "inspect_event_id": event.uuid,
                "tool_call_id": event.id,
                "working_start_seconds": event.working_start,
                "working_time_seconds": event.working_time,
                "event_timestamp": _jsonable(event.timestamp),
                "completed_at": completed_at,
                "truncated": event.truncated,
                "failed": failed,
                "error": _jsonable(event.error),
            }
            obs = state.agent.start_observation(
                name=f"tool: {event.function}",
                as_type="tool",
                input={"arguments": _jsonable(event.arguments), "code": _jsonable(event.view)},
                output=_jsonable(event.result),
                metadata=metadata,
                level="ERROR" if failed else None,
                status_message=str(event.error) if event.error else None,
            )
            obs.end()

    async def on_sample_scoring(self, data: SampleScoring) -> None:
        state = self._samples.get(data.sample_id)
        if state is None:
            return
        state.scoring_started = True
        state.root.update(metadata={"scoring_phase": "started"})

    async def on_sample_end(self, data: SampleEnd) -> None:
        state = self._samples.pop(data.sample_id, None)
        if state is None:
            return
        sample = data.sample
        scores = _jsonable(sample.scores or {})
        error = _jsonable(sample.error)
        state.root.update(
            output={"answer": _jsonable(sample.output), "scores": scores},
            metadata={
                "sample_id": state.sample_id,
                "scoring_phase": "complete" if state.scoring_started else "not_reached",
                "sample_error": error,
                "sample_total_time_seconds": sample.total_time,
                "sample_working_time_seconds": sample.working_time,
                "model_usage": _jsonable(sample.model_usage),
            },
            level="ERROR" if error else None,
            status_message=str(error) if error else None,
        )
        for scorer_name, score in (sample.scores or {}).items():
            value = getattr(score, "value", None)
            for metric_name, metric_value in _flatten_score(value):
                state.root.score_trace(
                    name=f"inspect/{scorer_name}/{metric_name}" if metric_name else f"inspect/{scorer_name}",
                    value=metric_value,
                    comment=getattr(score, "explanation", None),
                    metadata={
                        "answer": _jsonable(getattr(score, "answer", None)),
                        "reason": getattr(score, "reason", None),
                        "score_metadata": _jsonable(getattr(score, "metadata", None)),
                    },
                )
        state.agent.update(output={"answer": _jsonable(sample.output)}, metadata={"phase": "agent"}).end()
        state.root.end()

    async def on_run_end(self, data: RunEnd) -> None:
        self._sessions.pop(data.run_id, None)
        if not self.enabled():
            return
        client = self._client
        if client is not None:
            client.flush()
