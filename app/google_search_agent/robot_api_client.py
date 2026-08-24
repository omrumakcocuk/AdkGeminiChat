"""HTTP client used by ADK tools to communicate with the simulated robot."""

from __future__ import annotations

import json
import os
import threading
import time
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .simulated_robot_api import ensure_server


_timing = threading.local()


def _request(method: str, path: str, payload: dict | None = None) -> dict[str, Any]:
    base_url = os.getenv("ROBOT_API_BASE_URL") or ensure_server()
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(
        f"{base_url.rstrip('/')}{path}",
        data=body,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    started_at = time.perf_counter()
    with urlopen(request, timeout=5) as response:
        result = json.loads(response.read())
    elapsed_ms = (time.perf_counter() - started_at) * 1000
    _timing.total_ms = getattr(_timing, "total_ms", 0.0) + elapsed_ms
    return result["data"]


def read(*keys: str) -> dict[str, Any]:
    query = urlencode([("key", key) for key in keys])
    return _request("GET", f"/robot/state?{query}")


def update(**values: Any) -> dict[str, Any]:
    return _request("POST", "/robot/state", {"values": values})


def snapshot() -> dict[str, Any]:
    return _request("GET", "/robot/state")


def consume_timing_ms() -> float:
    """Return and clear accumulated HTTP time for the current tool thread."""
    value = getattr(_timing, "total_ms", 0.0)
    _timing.total_ms = 0.0
    return value
