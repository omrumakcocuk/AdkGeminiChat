"""Per-request timing output emitted as soon as each ADK tool starts."""

from __future__ import annotations

import threading
import time


_lock = threading.RLock()
_request_started_at: float | None = None
_reported_call_ids: set[str] = set()


def begin_request(started_at: float) -> None:
    """Start collecting completion timings for one terminal request."""
    global _request_started_at
    with _lock:
        _request_started_at = started_at
        _reported_call_ids.clear()


def update_request_start(started_at: float) -> None:
    """Move the start timestamp without losing already reported tool calls."""
    global _request_started_at
    with _lock:
        if _request_started_at is not None:
            _request_started_at = started_at


def end_request() -> None:
    """Stop terminal timing output for the current request."""
    global _request_started_at
    with _lock:
        _request_started_at = None
        _reported_call_ids.clear()


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
