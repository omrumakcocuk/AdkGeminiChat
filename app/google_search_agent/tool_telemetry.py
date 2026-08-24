"""Per-request timing output emitted as soon as each ADK tool starts."""

from __future__ import annotations

import threading
import time
import uuid

from . import robot_memory


_lock = threading.RLock()
_request_started_at: float | None = None
_reported_call_ids: set[str] = set()
_request_id: str | None = None


def begin_request(started_at: float, user_text: str = "", mode: str = "text") -> None:
    """Start collecting completion timings for one terminal request."""
    global _request_started_at, _request_id
    with _lock:
        _request_started_at = started_at
        _reported_call_ids.clear()
        _request_id = str(uuid.uuid4())
        robot_memory.create_request(_request_id, mode, user_text)


def update_request_text(user_text: str) -> None:
    """Persist a progressively completed voice transcription."""
    with _lock:
        if _request_id is not None:
            robot_memory.update_request(_request_id, user_text=user_text)


def update_request_start(started_at: float) -> None:
    """Move the start timestamp without losing already reported tool calls."""
    global _request_started_at
    with _lock:
        if _request_started_at is not None:
            _request_started_at = started_at


def end_request(assistant_text: str = "") -> None:
    """Stop terminal timing output for the current request."""
    global _request_started_at, _request_id
    with _lock:
        if _request_id is not None and assistant_text:
            robot_memory.update_request(_request_id, assistant_text=assistant_text)
        _request_started_at = None
        _request_id = None
        _reported_call_ids.clear()


def record_tool_result(
    tool_name: str,
    arguments: dict,
    result: dict,
) -> None:
    """Store one completed action under the active request."""
    with _lock:
        if _request_id is not None:
            robot_memory.add_action(_request_id, tool_name, arguments, result)


def record_model_usage(event) -> None:
    """Persist token and modality usage exposed by an ADK model event."""
    usage = event.usage_metadata
    if usage is None:
        return
    with _lock:
        if _request_id is not None:
            robot_memory.add_usage(
                _request_id,
                {
                    "event_id": event.id,
                    "author": event.author,
                    "model": event.model_version or "",
                    "usage": usage.model_dump(mode="json", exclude_none=True),
                },
            )


def report_tool_start(
    tool_name: str,
    call_id: str | None,
) -> None:
    """Print tool start latency; safe for concurrently starting tools."""
    with _lock:
        if _request_started_at is None:
            return
        identity = call_id or tool_name
        if identity in _reported_call_ids:
            return
        _reported_call_ids.add(identity)

        elapsed = time.perf_counter() - _request_started_at
        print(f"\n⚡ İşlem tepkimesi ({tool_name}): {elapsed:.3f} sn")
