"""A composable middleware chain for inbound message handling.

Middleware lets you wrap the core "message in, reply out" step with reusable,
cross-cutting behaviour — logging, rate limiting, authentication, normalization —
without touching the router or the bot. Each middleware is a callable
``(message, next_) -> str`` that may inspect/modify the message, short-circuit
with its own reply, or call ``next_(message)`` to continue down the chain.

Middleware runs in registration order (the first added is the outermost), and the
innermost ``next_`` is the bot's actual handler. This mirrors the onion model used
by Express/ASGI middleware.

Part of WhatsApp Bot by Viprasol Tech Private Limited (https://viprasol.com).
"""

from __future__ import annotations

import time
from collections.abc import Callable

from whatsapp_bot.webhook import IncomingMessage

Next = Callable[[IncomingMessage], str]
"""Continuation: call it to hand control to the next middleware / the handler."""

Middleware = Callable[[IncomingMessage, Next], str]
"""A middleware: ``(message, next_) -> reply``."""


class MiddlewareChain:
    """An ordered chain of middleware wrapping a terminal handler.

    Use :meth:`use` to append middleware, then :meth:`run` to process a message
    through the whole chain ending at ``handler``.
    """

    def __init__(self) -> None:
        self._middleware: list[Middleware] = []

    def use(self, middleware: Middleware) -> MiddlewareChain:
        """Append ``middleware`` to the chain and return ``self`` for chaining."""
        self._middleware.append(middleware)
        return self

    @property
    def size(self) -> int:
        """The number of registered middleware."""
        return len(self._middleware)

    def run(self, message: IncomingMessage, handler: Next) -> str:
        """Process ``message`` through the chain, ending at ``handler``.

        Args:
            message: The inbound message.
            handler: The terminal handler invoked after all middleware call
                ``next_`` (typically the bot's route-and-build step).

        Returns:
            The reply text produced by the chain.
        """
        chain: Next = handler
        for middleware in reversed(self._middleware):
            nxt = chain

            def wrapped(msg: IncomingMessage, mw: Middleware = middleware, nxt: Next = nxt) -> str:
                return mw(msg, nxt)

            chain = wrapped
        return chain(message)


def logging_middleware(sink: Callable[[str], None]) -> Middleware:
    """Middleware that logs each inbound message and its reply via ``sink``.

    Args:
        sink: A callback receiving a one-line log string (e.g. ``print``).

    Returns:
        A middleware suitable for :meth:`MiddlewareChain.use`.
    """

    def middleware(message: IncomingMessage, next_: Next) -> str:
        sink(f"-> [{message.sender}] {message.type}: {message.command_text!r}")
        reply = next_(message)
        sink(f"<- [{message.sender}] {reply!r}")
        return reply

    return middleware


def rate_limit_middleware(
    max_per_window: int,
    window_seconds: float,
    *,
    clock: Callable[[], float] | None = None,
    message: str = "You're sending messages too fast. Please slow down.",
) -> Middleware:
    """Middleware that throttles each user to ``max_per_window`` per time window.

    Uses a simple per-user sliding window. When a user exceeds the limit, the
    chain short-circuits and ``message`` is returned without calling ``next_``.

    Args:
        max_per_window: Allowed messages per user within the window.
        window_seconds: The sliding window length in seconds.
        clock: Injectable time source (defaults to :func:`time.time`).
        message: The reply sent when the limit is exceeded.

    Returns:
        A middleware suitable for :meth:`MiddlewareChain.use`.
    """
    now_fn = clock or time.time
    history: dict[str, list[float]] = {}

    def middleware(msg: IncomingMessage, next_: Next) -> str:
        now = now_fn()
        recent = [t for t in history.get(msg.sender, []) if now - t < window_seconds]
        if len(recent) >= max_per_window:
            history[msg.sender] = recent
            return message
        recent.append(now)
        history[msg.sender] = recent
        return next_(msg)

    return middleware


def keyword_block_middleware(
    blocked: set[str],
    *,
    reply: str = "Sorry, I can't help with that.",
) -> Middleware:
    """Middleware that blocks messages whose text contains a banned keyword.

    Matching is case-insensitive on whole, whitespace-delimited words.

    Args:
        blocked: The set of banned words (compared lowercased).
        reply: The reply returned when a blocked word is present.

    Returns:
        A middleware suitable for :meth:`MiddlewareChain.use`.
    """
    lowered = {word.lower() for word in blocked}

    def middleware(msg: IncomingMessage, next_: Next) -> str:
        words = {token.lower() for token in msg.text.split()}
        if words & lowered:
            return reply
        return next_(msg)

    return middleware
