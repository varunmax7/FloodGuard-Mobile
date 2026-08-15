"""Redis-backed CallState store (§8.3).

Persisted after every transition so a worker crash mid-call leaves
enough context for the post-call enrichment DAG to run even though
the caller's WebSocket dropped.

Lives under `conversation/` rather than `persistence/` because the
layered import contract forbids persistence-layer modules from
depending on the CallState type (a conversation-layer concern).
`persistence/session_store.py` still holds one row per call for the
finalisation metadata; this store holds the *in-flight* CallState."""

from __future__ import annotations

from typing import Protocol

import redis.asyncio as redis

from fg_voice.config import get_settings
from fg_voice.conversation.state import CallState

_CALL_STATE_TTL_SEC = 7200  # 2 h, matches SessionStore
_KEY_PREFIX = "fg:call:state:"


class CallStateStore(Protocol):
    async def save(self, state: CallState) -> None: ...
    async def load(self, call_sid: str) -> CallState | None: ...
    async def delete(self, call_sid: str) -> None: ...


class RedisCallStateStore:
    """Redis SETEX-per-transition. Idempotent: overwriting is the point."""

    def __init__(self, client: redis.Redis[str]) -> None:
        self._r = client

    def _key(self, call_sid: str) -> str:
        return _KEY_PREFIX + call_sid

    async def save(self, state: CallState) -> None:
        await self._r.set(self._key(state.call_sid), state.to_json(), ex=_CALL_STATE_TTL_SEC)

    async def load(self, call_sid: str) -> CallState | None:
        raw = await self._r.get(self._key(call_sid))
        if raw is None:
            return None
        return CallState.from_json(raw)

    async def delete(self, call_sid: str) -> None:
        await self._r.delete(self._key(call_sid))


class InMemoryCallStateStore:
    """Test double. Not used in the request path."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def save(self, state: CallState) -> None:
        self._store[state.call_sid] = state.to_json()

    async def load(self, call_sid: str) -> CallState | None:
        raw = self._store.get(call_sid)
        if raw is None:
            return None
        return CallState.from_json(raw)

    async def delete(self, call_sid: str) -> None:
        self._store.pop(call_sid, None)


_singleton: RedisCallStateStore | None = None


async def get_call_state_store() -> CallStateStore:
    """Process-wide Redis-backed store. Lazily instantiated on first use."""
    global _singleton
    if _singleton is None:
        client = redis.from_url(
            get_settings().redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        _singleton = RedisCallStateStore(client)
    return _singleton


__all__ = [
    "CallStateStore",
    "InMemoryCallStateStore",
    "RedisCallStateStore",
    "get_call_state_store",
]
