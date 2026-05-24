from __future__ import annotations

from sqlalchemy import update

from forge.core.database import get_session
from forge.core.models import Session


async def mark_session_good(session_id: str) -> dict:
    """Mark a session as good so it can be exported for training data."""
    async with get_session() as db:
        result = await db.execute(
            update(Session).where(Session.id == session_id).values(is_good=True)
        )
        if result.rowcount == 0:
            return {"ok": False, "error": f"Session not found: {session_id}"}
    return {"ok": True, "session_id": session_id, "is_good": True}
