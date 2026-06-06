"""Per-user session state with optional TTL expiry.

Conversations are stateful: you need to remember which step a user is on, what
they answered, or a shopping cart. :class:`Session` is a tiny per-user bag of
data plus a ``state`` label (used by :mod:`whatsapp_bot.flow`).
:class:`SessionStore` keeps one session per phone number in memory and can expire
idle sessions after a configurable timeout.

The store takes an injectable ``clock`` so expiry is fully deterministic in
tests. Swap the in-memory store for Redis or a database in production by
implementing the same small surface.

Part of WhatsApp Bot by Viprasol Tech Private Limited (https://viprasol.com).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

Clock = Callable[[], float]
"""A zero-arg function returning the current unix time in seconds."""


@dataclass
class Session:
    """Mutable state for one user (keyed by phone number).

    Attributes:
        user_id: The user's WhatsApp number.
        state: A free-form state label (e.g. a flow step). Empty means "idle".
        data: Arbitrary per-user key/value data.
        created_at: When the session was first created (unix seconds).
        updated_at: When the session was last touched (unix seconds).
    """

    user_id: str
    state: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0
    updated_at: float = 0.0

    def get(self, key: str, default: Any = None) -> Any:
        """Read ``key`` from this session's data, returning ``default`` if absent."""
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set ``key`` to ``value`` in this session's data."""
        self.data[key] = value

    def update(self, **values: Any) -> None:
        """Merge ``values`` into this session's data."""
        self.data.update(values)


class SessionStore:
    """In-memory store of one :class:`Session` per user, with optional TTL.

    Args:
        ttl_seconds: If set, sessions untouched for longer than this are treated
            as expired and discarded on access. ``None`` disables expiry.
        clock: Injectable time source; defaults to :func:`time.time`.
    """

    def __init__(self, *, ttl_seconds: float | None = None, clock: Clock | None = None) -> None:
        self._sessions: dict[str, Session] = {}
        self._ttl = ttl_seconds
        self._clock: Clock = clock or time.time

    def _expired(self, session: Session, now: float) -> bool:
        return self._ttl is not None and (now - session.updated_at) > self._ttl

    def get(self, user_id: str) -> Session | None:
        """Return the live session for ``user_id``, or ``None`` if none/expired.

        Expired sessions are evicted as a side effect of this call.
        """
        session = self._sessions.get(user_id)
        if session is None:
            return None
        if self._expired(session, self._clock()):
            del self._sessions[user_id]
            return None
        return session

    def get_or_create(self, user_id: str) -> Session:
        """Return the live session for ``user_id``, creating a fresh one if needed.

        The returned session's ``updated_at`` is bumped so it counts as active.
        """
        now = self._clock()
        session = self.get(user_id)
        if session is None:
            session = Session(user_id=user_id, created_at=now, updated_at=now)
            self._sessions[user_id] = session
        else:
            session.updated_at = now
        return session

    def save(self, session: Session) -> None:
        """Persist ``session``, stamping its ``updated_at`` to now."""
        session.updated_at = self._clock()
        self._sessions[session.user_id] = session

    def reset(self, user_id: str) -> None:
        """Forget the session for ``user_id`` (if any)."""
        self._sessions.pop(user_id, None)

    def purge_expired(self) -> int:
        """Evict every expired session and return how many were removed."""
        if self._ttl is None:
            return 0
        now = self._clock()
        stale = [uid for uid, s in self._sessions.items() if self._expired(s, now)]
        for uid in stale:
            del self._sessions[uid]
        return len(stale)

    def __len__(self) -> int:
        """The number of currently stored sessions (including not-yet-purged)."""
        return len(self._sessions)
