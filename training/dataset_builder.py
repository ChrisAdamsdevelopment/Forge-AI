from __future__ import annotations

import json
import random
import sqlite3
from pathlib import Path

from forge.core.config import settings

TOOL_ERROR_MARKERS = ["unknown tool", "tool error", "invalid tool arguments", '"error"']


def _resolve_db_path() -> Path:
    return Path(settings.db_url.replace("sqlite+aiosqlite:///", ""))


def _ensure_is_good_column(conn: sqlite3.Connection) -> None:
    rows = conn.execute("PRAGMA table_info(sessions)").fetchall()
    columns = {row[1] for row in rows}
    if "is_good" not in columns:
        conn.execute("ALTER TABLE sessions ADD COLUMN is_good BOOLEAN NOT NULL DEFAULT 0")
        conn.commit()


def _is_bad_text(text: str) -> bool:
    lowered = (text or "").strip().lower()
    if not lowered:
        return True
    return any(marker in lowered for marker in TOOL_ERROR_MARKERS)


def build_dataset() -> None:
    db_path = _resolve_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as conn:
        _ensure_is_good_column(conn)

        sessions = conn.execute("SELECT id FROM sessions WHERE is_good = 1 ORDER BY created_at ASC").fetchall()
        session_ids = [row[0] for row in sessions]

        examples: list[dict] = []
        for session_id in session_ids:
            rows = conn.execute(
                "SELECT role, content FROM messages WHERE session_id = ? ORDER BY created_at ASC",
                (session_id,),
            ).fetchall()

            system_text = "You are Forge, a self-hosted research and execution agent."
            pending_user: str | None = None
            for role, content in rows:
                if role == "system" and content.strip():
                    system_text = content
                elif role == "user":
                    pending_user = content
                elif role == "assistant" and pending_user is not None:
                    if _is_bad_text(content):
                        pending_user = None
                        continue
                    examples.append(
                        {
                            "messages": [
                                {"role": "system", "content": system_text},
                                {"role": "user", "content": pending_user},
                                {"role": "assistant", "content": content},
                            ]
                        }
                    )
                    pending_user = None

    random.seed(42)
    random.shuffle(examples)
    split = int(len(examples) * 0.8)
    train, valid = examples[:split], examples[split:]

    out_dir = Path("training")
    out_dir.mkdir(parents=True, exist_ok=True)
    train_path = out_dir / "train.jsonl"
    valid_path = out_dir / "valid.jsonl"

    def _write_jsonl(path: Path, rows: list[dict]) -> None:
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                payload = json.dumps(row, ensure_ascii=False)
                parsed = json.loads(payload)
                if "messages" not in parsed or not isinstance(parsed["messages"], list):
                    raise ValueError(f"Invalid schema in row for {path}")
                f.write(payload + "\n")

    _write_jsonl(train_path, train)
    _write_jsonl(valid_path, valid)

    print(f"Total sessions used: {len(session_ids)}")
    print(f"Total examples generated: {len(examples)}")
    print(f"Train examples: {len(train)}")
    print(f"Valid examples: {len(valid)}")


if __name__ == "__main__":
    build_dataset()
