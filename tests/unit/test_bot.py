"""Tests for the bot core and the fake sender."""

from __future__ import annotations

from typing import Any

from whatsapp_bot.bot import Bot
from whatsapp_bot.middleware import MiddlewareChain, Next, rate_limit_middleware
from whatsapp_bot.router import default_router
from whatsapp_bot.sender import FakeSender, Sender, build_text_message
from whatsapp_bot.webhook import IncomingMessage


def _payload(sender: str, text: str) -> dict[str, Any]:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "0",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "contacts": [{"wa_id": sender, "profile": {"name": "T"}}],
                            "messages": [{"from": sender, "type": "text", "text": {"body": text}}],
                        },
                    }
                ],
            }
        ],
    }


def test_build_text_message_schema() -> None:
    payload = build_text_message("15551230001", "hi")
    assert payload["messaging_product"] == "whatsapp"
    assert payload["to"] == "15551230001"
    assert payload["type"] == "text"
    assert payload["text"]["body"] == "hi"


def test_fake_sender_records_and_returns_ids() -> None:
    sender = FakeSender()
    id1 = sender.send(build_text_message("1", "a"))
    id2 = sender.send(build_text_message("2", "b"))
    assert id1 == "wamid.fake.1"
    assert id2 == "wamid.fake.2"
    assert sender.texts == ["a", "b"]
    assert len(sender.sent) == 2


def test_fake_sender_satisfies_protocol() -> None:
    assert isinstance(FakeSender(), Sender)


def test_fake_sender_clear() -> None:
    sender = FakeSender()
    sender.send(build_text_message("1", "a"))
    sender.clear()
    assert sender.sent == []
    assert sender.send(build_text_message("1", "b")) == "wamid.fake.1"


def test_bot_process_webhook_routes_and_sends() -> None:
    sender = FakeSender()
    bot = Bot(default_router(), sender)
    replies = bot.process_webhook(_payload("15551230001", "/help"))
    assert len(replies) == 1
    assert replies[0].to == "15551230001"
    assert "/menu" in replies[0].text
    assert replies[0].message_id == "wamid.fake.1"
    assert sender.texts == [replies[0].text]


def test_bot_echo_default() -> None:
    sender = FakeSender()
    bot = Bot(default_router(), sender)
    replies = bot.process_webhook(_payload("15551230002", "hello"))
    assert replies[0].text == "You said: hello"


def test_try_process_webhook_swallows_malformed() -> None:
    bot = Bot(default_router(), FakeSender())
    assert bot.try_process_webhook({"bad": "payload"}) == []


def test_bot_runs_middleware_before_router() -> None:
    seen: list[str] = []

    def tap(message: IncomingMessage, next_: Next) -> str:
        seen.append(message.text)
        return next_(message)

    chain = MiddlewareChain().use(tap)
    bot = Bot(default_router(), FakeSender(), middleware=chain)
    bot.process_webhook(_payload("1", "/ping"))
    assert seen == ["/ping"]


def test_bot_middleware_short_circuits_router() -> None:
    class FakeClock:
        def __init__(self) -> None:
            self.now = 0.0

        def __call__(self) -> float:
            return self.now

    chain = MiddlewareChain().use(rate_limit_middleware(1, 60.0, clock=FakeClock()))
    sender = FakeSender()
    bot = Bot(default_router(), sender, middleware=chain)
    bot.process_webhook(_payload("1", "/ping"))
    replies = bot.process_webhook(_payload("1", "/ping"))
    assert "too fast" in replies[0].text
    # both attempts still produced one outgoing message each
    assert len(sender.sent) == 2


def test_bot_handles_interactive_reply_end_to_end() -> None:
    sender = FakeSender()
    bot = Bot(default_router(), sender)
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "0",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "messages": [
                                {
                                    "from": "1",
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "button_reply",
                                        "button_reply": {"id": "/menu", "title": "Menu"},
                                    },
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    replies = bot.process_webhook(payload)
    assert "Main menu" in replies[0].text


def test_status_only_payload_sends_nothing() -> None:
    sender = FakeSender()
    bot = Bot(default_router(), sender)
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{"id": "0", "changes": [{"field": "messages", "value": {"statuses": []}}]}],
    }
    assert bot.process_webhook(payload) == []
    assert sender.sent == []
