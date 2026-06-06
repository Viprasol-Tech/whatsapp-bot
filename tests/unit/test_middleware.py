"""Tests for the middleware chain and built-in middleware."""

from __future__ import annotations

from whatsapp_bot.middleware import (
    MiddlewareChain,
    Next,
    keyword_block_middleware,
    logging_middleware,
    rate_limit_middleware,
)
from whatsapp_bot.webhook import IncomingMessage


def _msg(text: str, sender: str = "1") -> IncomingMessage:
    return IncomingMessage(sender=sender, text=text)


def _echo(message: IncomingMessage) -> str:
    return f"echo:{message.text}"


def test_empty_chain_calls_handler() -> None:
    chain = MiddlewareChain()
    assert chain.size == 0
    assert chain.run(_msg("hi"), _echo) == "echo:hi"


def test_middleware_runs_in_registration_order() -> None:
    events: list[str] = []

    def outer(message: IncomingMessage, next_: Next) -> str:
        events.append("outer-before")
        result = next_(message)
        events.append("outer-after")
        return result

    def inner(message: IncomingMessage, next_: Next) -> str:
        events.append("inner-before")
        result = next_(message)
        events.append("inner-after")
        return result

    chain = MiddlewareChain().use(outer).use(inner)
    assert chain.size == 2
    chain.run(_msg("hi"), _echo)
    assert events == ["outer-before", "inner-before", "inner-after", "outer-after"]


def test_middleware_can_short_circuit() -> None:
    def block(message: IncomingMessage, next_: Next) -> str:
        return "blocked"

    reached = False

    def handler(message: IncomingMessage) -> str:
        nonlocal reached
        reached = True
        return "handler"

    chain = MiddlewareChain().use(block)
    assert chain.run(_msg("hi"), handler) == "blocked"
    assert reached is False


def test_logging_middleware_records_in_and_out() -> None:
    lines: list[str] = []
    chain = MiddlewareChain().use(logging_middleware(lines.append))
    chain.run(_msg("hi"), _echo)
    assert any("-> [1]" in line for line in lines)
    assert any("<- [1]" in line and "echo:hi" in line for line in lines)


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_rate_limit_blocks_after_threshold() -> None:
    clock = FakeClock()
    chain = MiddlewareChain().use(rate_limit_middleware(2, 60.0, clock=clock))
    assert chain.run(_msg("a"), _echo) == "echo:a"
    assert chain.run(_msg("b"), _echo) == "echo:b"
    third = chain.run(_msg("c"), _echo)
    assert "too fast" in third


def test_rate_limit_window_resets() -> None:
    clock = FakeClock()
    chain = MiddlewareChain().use(rate_limit_middleware(1, 60.0, clock=clock))
    assert chain.run(_msg("a"), _echo) == "echo:a"
    assert "too fast" in chain.run(_msg("b"), _echo)
    clock.advance(61)
    assert chain.run(_msg("c"), _echo) == "echo:c"


def test_rate_limit_is_per_user() -> None:
    clock = FakeClock()
    chain = MiddlewareChain().use(rate_limit_middleware(1, 60.0, clock=clock))
    assert chain.run(_msg("a", sender="1"), _echo) == "echo:a"
    assert chain.run(_msg("b", sender="2"), _echo) == "echo:b"


def test_keyword_block_blocks_banned_word() -> None:
    chain = MiddlewareChain().use(keyword_block_middleware({"spam"}))
    assert chain.run(_msg("buy SPAM now"), _echo) == "Sorry, I can't help with that."
    assert chain.run(_msg("hello there"), _echo) == "echo:hello there"
