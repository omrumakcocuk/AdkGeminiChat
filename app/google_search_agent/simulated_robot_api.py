"""Small concurrent HTTP API that behaves like a remote demo robot."""

from __future__ import annotations

import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import robot_state


class _RobotApiHandler(BaseHTTPRequestHandler):
    server_version = "SimulatedRobotAPI/1.0"

    def log_message(self, format: str, *args) -> None:
        del format, args

    def _delay(self) -> None:
        delay_ms = max(0, int(os.getenv("ROBOT_API_DELAY_MS", "60")))
        time.sleep(delay_ms / 1000)

    def _send(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        self._delay()
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._send(200, {"status": "ok"})
            return
        if parsed.path == "/robot/state":
            keys = parse_qs(parsed.query).get("key", [])
            try:
                data = robot_state.read(*keys) if keys else robot_state.snapshot()
            except KeyError as error:
                self._send(404, {"status": "error", "message": str(error)})
                return
            self._send(200, {"status": "success", "data": data})
            return
        self._send(404, {"status": "error", "message": "endpoint not found"})

    def do_POST(self) -> None:
        self._delay()
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", "0"))
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._send(400, {"status": "error", "message": "invalid JSON"})
            return
        if parsed.path == "/robot/state":
            values = payload.get("values")
            if not isinstance(values, dict):
                self._send(400, {"status": "error", "message": "values must be an object"})
                return
            self._send(200, {"status": "success", "data": robot_state.update(**values)})
            return
        if parsed.path == "/robot/reset":
            self._send(200, {"status": "success", "data": robot_state.reset()})
            return
        self._send(404, {"status": "error", "message": "endpoint not found"})


_server: ThreadingHTTPServer | None = None
_server_lock = threading.Lock()


def ensure_server() -> str:
    """Start one localhost API server and return its base URL."""
    global _server
    with _server_lock:
        if _server is None:
            _server = ThreadingHTTPServer(("127.0.0.1", 0), _RobotApiHandler)
            threading.Thread(target=_server.serve_forever, daemon=True).start()
        host, port = _server.server_address
        return f"http://{host}:{port}"
