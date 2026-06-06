"""Tests for command routing."""

from __future__ import annotations

from whatsapp_bot.router import Router, default_router
from whatsapp_bot.webhook import IncomingMessage


def _msg(text: str, msg_type: str = "text") -> IncomingMessage:
    return IncomingMessage(sender="15550000000", text=text, type=msg_type)


def test_help_command_routes() -> None:
    router = default_router()
    reply = router.route(_msg("/help"))
    assert "/help" in reply
    assert "/menu" in reply


def test_menu_command_routes() -> None:
    router = default_router()
    reply = router.route(_msg("/menu"))
    assert "Main menu" in reply


def test_command_is_case_insensitive_and_ignores_args() -> None:
    router = default_router()
    assert router.route(_msg("/HELP now please")) == router.route(_msg("/help"))


def test_default_echo_for_plain_text() -> None:
    router = default_router()
    assert router.route(_msg("ping")) == "You said: ping"


def test_unknown_command_falls_through_to_default() -> None:
    router = default_router()
    assert router.route(_msg("/unknown")) == "You said: /unknown"


def test_default_handles_non_text() -> None:
    router = default_router()
    reply = router.route(_msg("", msg_type="image"))
    assert "only handle text" in reply


def test_register_and_custom_default() -> None:
    router = Router(default=lambda m: "fallback")

    @router.command("greet")
    def _greet(m: IncomingMessage) -> str:
        return "hi"

    assert router.route(_msg("/greet")) == "hi"
    assert router.route(_msg("anything")) == "fallback"
    assert router.commands == ["/greet"]


def test_set_default_replaces_handler() -> None:
    router = Router()
    router.set_default(lambda m: "new-default")
    assert router.route(_msg("whatever")) == "new-default"


def test_default_router_extra_commands() -> None:
    router = default_router()
    assert router.route(_msg("/ping")) == "pong"
    assert "Viprasol" in router.route(_msg("/about"))
    assert "Send /help" in router.route(_msg("/start"))


def test_start_uses_contact_name() -> None:
    router = default_router()
    msg = IncomingMessage(sender="1", text="/start", contact_name="Grace")
    assert "Hi Grace" in router.route(msg)


def test_has_command() -> None:
    router = default_router()
    assert router.has_command("/help")
    assert router.has_command("ping")  # normalizes leading slash
    assert not router.has_command("/nope")


def test_interactive_reply_routes_like_command() -> None:
    router = default_router()
    msg = IncomingMessage(
        sender="1",
        type="interactive",
        interactive_reply_id="/menu",
        interactive_reply_title="Main menu",
    )
    assert "Main menu" in router.route(msg)


def test_interactive_reply_without_slash_is_normalized() -> None:
    router = Router(default=lambda m: "fallback")

    @router.command("/topic")
    def _topic(m: IncomingMessage) -> str:
        return "topic-handler"

    msg = IncomingMessage(sender="1", type="interactive", interactive_reply_id="topic")
    assert router.route(msg) == "topic-handler"


def test_help_lists_new_commands() -> None:
    router = default_router()
    reply = router.route(_msg("/help"))
    assert "/ping" in reply
    assert "/about" in reply
