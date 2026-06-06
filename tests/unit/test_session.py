"""Tests for per-user session state and the session store."""

from __future__ import annotations

from whatsapp_bot.session import Session, SessionStore


class FakeClock:
    """A controllable clock for deterministic TTL tests."""

    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_session_data_helpers() -> None:
    session = Session(user_id="1")
    session.set("a", 1)
    session.update(b=2, c=3)
    assert session.get("a") == 1
    assert session.get("missing", "d") == "d"
    assert session.data == {"a": 1, "b": 2, "c": 3}


def test_get_or_create_returns_same_instance() -> None:
    store = SessionStore()
    first = store.get_or_create("1")
    first.set("x", 9)
    second = store.get_or_create("1")
    assert second is first
    assert second.get("x") == 9
    assert len(store) == 1


def test_get_returns_none_for_unknown_user() -> None:
    assert SessionStore().get("nobody") is None


def test_reset_forgets_session() -> None:
    store = SessionStore()
    store.get_or_create("1")
    store.reset("1")
    assert store.get("1") is None
    assert len(store) == 0


def test_ttl_expires_idle_session_on_access() -> None:
    clock = FakeClock()
    store = SessionStore(ttl_seconds=10, clock=clock)
    store.get_or_create("1")
    clock.advance(11)
    assert store.get("1") is None
    assert len(store) == 0


def test_ttl_not_expired_within_window() -> None:
    clock = FakeClock()
    store = SessionStore(ttl_seconds=10, clock=clock)
    store.get_or_create("1")
    clock.advance(5)
    assert store.get("1") is not None


def test_save_refreshes_updated_at_and_prevents_expiry() -> None:
    clock = FakeClock()
    store = SessionStore(ttl_seconds=10, clock=clock)
    session = store.get_or_create("1")
    clock.advance(8)
    store.save(session)  # bumps updated_at to now (8)
    clock.advance(5)  # now 13, but last touch was 8 -> 5s < 10s
    assert store.get("1") is not None


def test_purge_expired_counts_and_removes() -> None:
    clock = FakeClock()
    store = SessionStore(ttl_seconds=10, clock=clock)
    store.get_or_create("a")
    store.get_or_create("b")
    clock.advance(11)
    store.get_or_create("c")  # fresh at t=11
    removed = store.purge_expired()
    assert removed == 2
    assert store.get("c") is not None


def test_purge_noop_without_ttl() -> None:
    store = SessionStore()
    store.get_or_create("a")
    assert store.purge_expired() == 0
