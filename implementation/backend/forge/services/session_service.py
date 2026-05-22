"""
forge/services/session_service.py

CRUD for conversation sessions and their messages.
Context window management: trims oldest messages when the token
budget is exceeded, always preserving the system message.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from forge.core.models import Message, Session

logger = logging.getLogger(__name__)

_CHARS_PER_TOKEN = 4  # rough approximation


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // _CHARS_PER_TOKEN)


class SessionService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Sessions ──────────────────────────────────────────────────────────────

    async def create_session(self, model_name: str, title: str = "New conversation") -> Session:
        session = Session(model_name=model_name, title=title)
        self._db.add(session)
        await self._db.flush()
        logger.debug("Created session %s", session.id)
        return session

    async def get_session(self, session_id: str) -> Session | None:
        result = await self._db.execute(select(Session).where(Session.id == session_id))
        return result.scalar_one_or_none()

    async def list_sessions(self, archived: bool = False) -> list[Session]:
        result = await self._db.execute(
            select(Session)
            .where(Session.is_archived == archived)
            .order_by(Session.updated_at.desc())
        )
        return list(result.scalars().all())

    async def archive_session(self, session_id: str) -> None:
        await self._db.execute(
            update(Session)
            .where(Session.id == session_id)
            .values(is_archived=True)
        )

    # ── Messages ──────────────────────────────────────────────────────────────

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        tool_calls: list[dict] | None = None,
        tool_call_id: str | None = None,
        tool_name: str | None = None,
    ) -> Message:
        msg = Message(
            session_id=session_id,
            role=role,
            content=content,
            tool_calls=tool_calls,
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            token_count=_estimate_tokens(content),
        )
        self._db.add(msg)
        await self._db.flush()

        # Auto-title the session from first user message
        if role == "user":
            session = await self.get_session(session_id)
            if session and session.title == "New conversation":
                title = content[:72].strip().replace("\n", " ")
                session.title = title
                session.updated_at = datetime.now(timezone.utc)

        return msg

    async def get_messages(self, session_id: str) -> list[Message]:
        result = await self._db.execute(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at.asc())
        )
        return list(result.scalars().all())

    # ── Context window assembly ───────────────────────────────────────────────

    async def build_context(
        self,
        session_id: str,
        system_prompt: str,
        max_tokens: int = 30_000,
    ) -> list[dict]:
        """
        Build the messages list for inference, respecting max_tokens.

        Strategy:
        - System prompt is always kept.
        - Newest messages are kept first; oldest user/assistant pairs are
          dropped until it fits.
        - Tool messages are kept paired with their triggering assistant message.
        """
        messages = await self.get_messages(session_id)
        system_tokens = _estimate_tokens(system_prompt)
        budget = max_tokens - system_tokens

        # Walk backwards keeping messages until budget exhausted
        kept: list[dict] = []
        used = 0
        for msg in reversed(messages):
            cost = msg.token_count or _estimate_tokens(msg.content)
            if used + cost > budget and kept:
                break
            kept.insert(0, {
                "role": msg.role,
                "content": msg.content,
                **({"tool_calls": msg.tool_calls} if msg.tool_calls else {}),
                **({"tool_call_id": msg.tool_call_id} if msg.tool_call_id else {}),
                **({"name": msg.tool_name} if msg.tool_name else {}),
            })
            used += cost

        return [{"role": "system", "content": system_prompt}] + kept
