from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import aiosqlite


def _memory_db_path() -> Path:
    configured = os.environ.get("FORGE_MEMORY_DB", "").strip()
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".forge" / "memory.db"


DB_PATH = _memory_db_path()


async def _ensure_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS memory (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                tags TEXT NOT NULL DEFAULT '[]',
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        columns = [
            row[1]
            for row in await (await db.execute("PRAGMA table_info(memory)")).fetchall()
        ]
        if "tags" not in columns:
            await db.execute(
                "ALTER TABLE memory ADD COLUMN tags TEXT NOT NULL DEFAULT '[]'"
            )
        await db.commit()


async def memory_store(
    key: str, value: str, tags: list[str] | None = None
) -> dict[str, str | bool]:
    """Persist a key-value memory item in SQLite."""
    if not key.strip():
        return {"key": key, "stored": False, "error": "Memory key must not be empty"}
    await _ensure_db()
    tag_json = json.dumps(tags or [])
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """
                INSERT INTO memory (key, value, tags, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    tags = excluded.tags,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (key, value, tag_json),
            )
            await db.commit()
    except aiosqlite.Error as exc:
        return {"key": key, "stored": False, "error": str(exc)}
    return {"key": key, "stored": True, "db_path": str(DB_PATH)}


async def memory_retrieve(key: str) -> dict[str, Any]:
    """Retrieve a key from persistent SQLite memory."""
    if not key.strip():
        return {
            "key": key,
            "value": None,
            "found": False,
            "error": "Memory key must not be empty",
        }
    await _ensure_db()
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT value, tags, updated_at FROM memory WHERE key = ?", (key,)
            )
            row = await cursor.fetchone()
    except aiosqlite.Error as exc:
        return {"key": key, "value": None, "found": False, "error": str(exc)}

    if row is None:
        return {"key": key, "value": None, "found": False, "db_path": str(DB_PATH)}
    try:
        tags = json.loads(row[1] or "[]")
    except json.JSONDecodeError:
        tags = []
    return {
        "key": key,
        "value": row[0],
        "tags": tags,
        "updated_at": row[2],
        "found": True,
        "db_path": str(DB_PATH),
    }
