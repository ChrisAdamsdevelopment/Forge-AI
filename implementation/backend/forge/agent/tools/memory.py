from __future__ import annotations

from pathlib import Path

import aiosqlite

DB_PATH = Path.home() / ".forge" / "memory.db"


async def _ensure_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS memory (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.commit()


async def memory_store(key: str, value: str) -> dict[str, str | bool]:
    """Persist a key-value memory item."""
    await _ensure_db()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO memory (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = CURRENT_TIMESTAMP
            """,
            (key, value),
        )
        await db.commit()
    return {"key": key, "stored": True}


async def memory_retrieve(key: str) -> dict[str, str | bool | None]:
    """Retrieve a key from persistent memory."""
    await _ensure_db()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT value FROM memory WHERE key = ?", (key,))
        row = await cursor.fetchone()

    if row is None:
        return {"key": key, "value": None, "found": False}
    return {"key": key, "value": row[0], "found": True}
