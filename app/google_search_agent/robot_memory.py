"""Persistent one-row-per-dialogue SQLite history."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_DATABASE_PATH = Path(__file__).resolve().parents[1] / "robot_memory.db"


def database_path() -> Path:
    """Return the configured history database location."""
    configured = os.getenv("ROBOT_MEMORY_DB")
    return Path(configured).expanduser() if configured else DEFAULT_DATABASE_PATH


def _connect() -> sqlite3.Connection:
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA busy_timeout=10000")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS dialogue_history (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            mode TEXT NOT NULL,
            transcript TEXT NOT NULL DEFAULT '',
            actions_json TEXT NOT NULL DEFAULT '[]',
            assistant_text TEXT NOT NULL DEFAULT '',
            usage_json TEXT NOT NULL DEFAULT '[]'
        )
        """
    )
    columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(dialogue_history)")
    }
    if "usage_json" not in columns:
        connection.execute(
            "ALTER TABLE dialogue_history "
            "ADD COLUMN usage_json TEXT NOT NULL DEFAULT '[]'"
        )
    _migrate_legacy_tables(connection)
    return connection


def _table_exists(connection: sqlite3.Connection, name: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)
    ).fetchone() is not None


def _migrate_legacy_tables(connection: sqlite3.Connection) -> None:
    """Move the previous two-table history into dialogue_history once."""
    if not _table_exists(connection, "requests"):
        return
    legacy_requests = connection.execute("SELECT * FROM requests").fetchall()
    has_actions = _table_exists(connection, "actions")
    for request in legacy_requests:
        actions: list[dict[str, Any]] = []
        if has_actions:
            rows = connection.execute(
                "SELECT tool_name, arguments_json, result_json, created_at "
                "FROM actions WHERE request_id = ? ORDER BY id",
                (request["id"],),
            ).fetchall()
            actions = [
                {
                    "tool_name": row["tool_name"],
                    "arguments": json.loads(row["arguments_json"]),
                    "result": json.loads(row["result_json"]),
                    "created_at": row["created_at"],
                }
                for row in rows
            ]
        connection.execute(
            "INSERT OR IGNORE INTO dialogue_history "
            "(id, created_at, mode, transcript, actions_json, assistant_text, usage_json) "
            "VALUES (?, ?, ?, ?, ?, ?, '[]')",
            (
                request["id"],
                request["created_at"],
                request["mode"],
                request["user_text"],
                json.dumps(actions, ensure_ascii=False, default=str),
                request["assistant_text"],
            ),
        )
    if has_actions:
        connection.execute("DROP TABLE actions")
    connection.execute("DROP TABLE requests")
    connection.commit()


def create_request(request_id: str, mode: str, user_text: str = "") -> None:
    with _connect() as connection:
        connection.execute(
            "INSERT OR REPLACE INTO dialogue_history "
            "(id, created_at, mode, transcript, actions_json, assistant_text, usage_json) "
            "VALUES (?, ?, ?, ?, '[]', '', '[]')",
            (request_id, datetime.now(timezone.utc).isoformat(), mode, user_text.strip()),
        )


def update_request(
    request_id: str,
    *,
    user_text: str | None = None,
    assistant_text: str | None = None,
) -> None:
    fields: list[str] = []
    values: list[str] = []
    if user_text is not None:
        fields.append("transcript = ?")
        values.append(user_text.strip())
    if assistant_text is not None:
        fields.append("assistant_text = ?")
        values.append(assistant_text.strip())
    if not fields:
        return
    with _connect() as connection:
        connection.execute(
            f"UPDATE dialogue_history SET {', '.join(fields)} WHERE id = ?",
            (*values, request_id),
        )


def add_action(
    request_id: str,
    tool_name: str,
    arguments: dict[str, Any],
    result: dict[str, Any],
) -> None:
    with _connect() as connection:
        # Multiple robot tools can finish concurrently. Lock the short
        # read-modify-write transaction so none of their results is lost.
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT actions_json FROM dialogue_history WHERE id = ?", (request_id,)
        ).fetchone()
        if row is None:
            connection.rollback()
            return
        actions = json.loads(row["actions_json"])
        actions.append(
            {
                "tool_name": tool_name,
                "arguments": arguments,
                "result": result,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        connection.execute(
            "UPDATE dialogue_history SET actions_json = ? WHERE id = ?",
            (
                json.dumps(actions, ensure_ascii=False, default=str),
                request_id,
            ),
        )


def add_usage(request_id: str, usage: dict[str, Any]) -> None:
    """Append one model usage record, deduplicated by ADK event ID."""
    with _connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT usage_json FROM dialogue_history WHERE id = ?", (request_id,)
        ).fetchone()
        if row is None:
            connection.rollback()
            return
        records = json.loads(row["usage_json"])
        if any(record.get("event_id") == usage.get("event_id") for record in records):
            connection.rollback()
            return
        records.append(usage)
        connection.execute(
            "UPDATE dialogue_history SET usage_json = ? WHERE id = ?",
            (json.dumps(records, ensure_ascii=False, default=str), request_id),
        )


def get_history(limit: int = 20) -> list[dict[str, Any]]:
    """Return recent requests with their robot actions, newest first."""
    with _connect() as connection:
        rows = connection.execute(
            "SELECT * FROM ("
            "SELECT * FROM dialogue_history ORDER BY created_at DESC LIMIT ?"
            ") ORDER BY created_at ASC",
            (max(1, limit),),
        ).fetchall()
        return [
            {
                "id": row["id"],
                "created_at": row["created_at"],
                "mode": row["mode"],
                "user_text": row["transcript"],
                "actions": json.loads(row["actions_json"]),
                "assistant_text": row["assistant_text"],
                "usage": json.loads(row["usage_json"]),
            }
            for row in rows
        ]
