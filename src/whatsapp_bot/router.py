"""Command routing: map an inbound message to a reply.

The :class:`Router` lets you register slash-style command handlers (``/help``,
``/menu``, ...) and a default handler for everything else. A handler is a pure
function ``IncomingMessage -> str`` returning the reply text, which keeps routing
trivial to test.

Part of WhatsApp Bot by Viprasol Tech Private Limited (https://viprasol.com).
"""

from __future__ import annotations

from collections.abc import Callable

from whatsapp_bot.webhook import IncomingMessage

Handler = Callable[[IncomingMessage], str]
"""A command handler: takes the inbound message, returns the reply text."""


def _normalize_command(text: str) -> str:
    """Extract the leading command token (lowercased) from message text.

    ``"/Help me please"`` -> ``"/help"``; non-command text -> ``""``.
    """
    stripped = text.strip()
    if not stripped.startswith("/"):
        return ""
    return stripped.split(maxsplit=1)[0].lower()


def _default_echo(message: IncomingMessage) -> str:
    """Built-in fallback handler: echo the user's text back to them."""
    if message.type != "text" or not message.text.strip():
        return "Sorry, I can only handle text messages right now."
    return f"You said: {message.text.strip()}"


def _routing_key(message: IncomingMessage) -> str:
    """Compute the lookup key for ``message``.

    Interactive button/list replies route on their reply id (which may itself be a
    command such as ``/menu``); plain text routes on its leading slash command.
    """
    if message.type == "interactive" and message.interactive_reply_id:
        token = message.interactive_reply_id.strip().lower()
        return token if token.startswith("/") else f"/{token}"
    return _normalize_command(message.text)


class Router:
    """Registry of command handlers with a default fallback.

    Commands are matched case-insensitively on the first whitespace-delimited
    token of the message text (e.g. ``/menu``). Anything that is not a registered
    command is passed to the default handler (an echo, unless you override it).
    """

    def __init__(self, *, default: Handler | None = None) -> None:
        """Create a router.

        Args:
            default: Handler used when no command matches. Defaults to an echo.
        """
        self._handlers: dict[str, Handler] = {}
        self._default: Handler = default or _default_echo

    def command(self, name: str) -> Callable[[Handler], Handler]:
        """Decorator registering a handler for a command such as ``"/help"``.

        Args:
            name: The command keyword, with or without a leading slash.

        Returns:
            A decorator that registers and returns the handler unchanged.
        """

        def decorator(handler: Handler) -> Handler:
            self.register(name, handler)
            return handler

        return decorator

    def register(self, name: str, handler: Handler) -> None:
        """Register ``handler`` for command ``name``.

        Args:
            name: The command keyword, with or without a leading slash.
            handler: The handler to invoke for that command.
        """
        key = name if name.startswith("/") else f"/{name}"
        self._handlers[key.lower()] = handler

    def set_default(self, handler: Handler) -> None:
        """Replace the fallback handler used for unmatched messages."""
        self._default = handler

    @property
    def commands(self) -> list[str]:
        """The registered command keywords, sorted."""
        return sorted(self._handlers)

    def route(self, message: IncomingMessage) -> str:
        """Resolve ``message`` to a reply via the matching or default handler.

        Args:
            message: The inbound message to route.

        Returns:
            The reply text produced by the chosen handler.
        """
        handler = self._handlers.get(_routing_key(message), self._default)
        return handler(message)

    def has_command(self, name: str) -> bool:
        """Return ``True`` if a handler is registered for command ``name``."""
        key = name if name.startswith("/") else f"/{name}"
        return key.lower() in self._handlers


def default_router() -> Router:
    """Build a router pre-wired with ``/help`` and ``/menu`` plus echo default.

    Returns:
        A ready-to-use :class:`Router` demonstrating the common commands.
    """
    router = Router()

    @router.command("/help")
    def _help(_: IncomingMessage) -> str:
        return (
            "Available commands:\n"
            "/help - show this message\n"
            "/menu - show the main menu\n"
            "/start - greet and get started\n"
            "/ping - health check\n"
            "/about - about this bot\n"
            "Anything else is echoed back to you."
        )

    @router.command("/menu")
    def _menu(_: IncomingMessage) -> str:
        return "Main menu:\n1. Talk to support\n2. Check status\n3. Pricing"

    @router.command("/start")
    def _start(message: IncomingMessage) -> str:
        who = message.contact_name or "there"
        return f"Hi {who}! Send /help to see what I can do."

    @router.command("/ping")
    def _ping(_: IncomingMessage) -> str:
        return "pong"

    @router.command("/about")
    def _about(_: IncomingMessage) -> str:
        return "WhatsApp Bot by Viprasol Tech — https://viprasol.com"

    return router
