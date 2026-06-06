"""The bot core: glue webhook parsing, routing, and sending together.

:class:`Bot` takes a :class:`~whatsapp_bot.router.Router` and a
:class:`~whatsapp_bot.sender.Sender`, and exposes :meth:`process_webhook`, which
parses an inbound payload, routes each message to a reply, and sends the replies.
Everything is offline-friendly because the transport is injected.

Part of WhatsApp Bot by Viprasol Tech Private Limited (https://viprasol.com).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from whatsapp_bot.router import Router
from whatsapp_bot.sender import Sender, build_text_message
from whatsapp_bot.webhook import IncomingMessage, WebhookParseError, parse_messages


class Reply(BaseModel):
    """A reply that the bot produced and dispatched for one inbound message.

    Attributes:
        to: The recipient phone number (the original sender).
        text: The reply body that was sent.
        message_id: The provider id returned by the sender for the reply.
    """

    to: str
    text: str
    message_id: str


class Bot:
    """A WhatsApp bot wiring a router to a sender.

    Args:
        router: Routes inbound messages to reply text.
        sender: Transport used to deliver the replies.
    """

    def __init__(self, router: Router, sender: Sender) -> None:
        self.router = router
        self.sender = sender

    def handle_message(self, message: IncomingMessage) -> Reply:
        """Route a single inbound message and send its reply.

        Args:
            message: The inbound message to handle.

        Returns:
            The :class:`Reply` that was dispatched.
        """
        text = self.router.route(message)
        payload = build_text_message(message.sender, text)
        message_id = self.sender.send(payload)
        return Reply(to=message.sender, text=text, message_id=message_id)

    def process_webhook(self, payload: dict[str, Any]) -> list[Reply]:
        """Process a full webhook payload end to end.

        Parses every inbound message in ``payload``, routes each to a reply, and
        sends them. Status-only callbacks (no messages) yield an empty list.

        Args:
            payload: The decoded JSON body Meta POSTed to your webhook.

        Returns:
            One :class:`Reply` per inbound message handled.

        Raises:
            WebhookParseError: If the payload is not a valid webhook envelope.
        """
        replies: list[Reply] = []
        for message in parse_messages(payload):
            replies.append(self.handle_message(message))
        return replies

    def try_process_webhook(self, payload: dict[str, Any]) -> list[Reply]:
        """Like :meth:`process_webhook` but swallow malformed payloads.

        Useful at the HTTP boundary where you want to return ``200 OK`` even for
        junk so the provider does not retry indefinitely.

        Args:
            payload: The decoded JSON webhook body (possibly malformed).

        Returns:
            The dispatched replies, or an empty list if the payload was invalid.
        """
        try:
            return self.process_webhook(payload)
        except WebhookParseError:
            return []
