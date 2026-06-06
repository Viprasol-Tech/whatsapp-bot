"""Outbound message transport: the ``Sender`` protocol and a fake implementation.

A :class:`Sender` is anything that can deliver an outgoing WhatsApp payload to a
recipient. The real transport (an HTTP POST to the WhatsApp Cloud API
``/messages`` endpoint) lives behind this interface so the bot core never touches
the network. :class:`FakeSender` records everything it is asked to send, which is
exactly what you want in tests and in the offline CLI demo.

Part of WhatsApp Bot by Viprasol Tech Private Limited (https://viprasol.com).
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


def build_text_message(to: str, body: str) -> dict[str, Any]:
    """Build a WhatsApp Cloud API outgoing text-message payload.

    This is the JSON body you would POST to
    ``https://graph.facebook.com/v20.0/<phone-number-id>/messages``.

    Args:
        to: The recipient WhatsApp number in E.164 digits.
        body: The text to send.

    Returns:
        A dict matching the Cloud API ``text`` message schema.
    """
    return {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "text",
        "text": {"preview_url": False, "body": body},
    }


@runtime_checkable
class Sender(Protocol):
    """Transport interface for delivering outgoing WhatsApp payloads.

    Implement this with an HTTP client for production; use :class:`FakeSender`
    for tests and demos.
    """

    def send(self, payload: dict[str, Any]) -> str:
        """Deliver one outgoing message payload.

        Args:
            payload: A Cloud API message body (see :func:`build_text_message`).

        Returns:
            A provider message id for the sent message.
        """
        ...


class FakeSender:
    """In-memory :class:`Sender` that records sends instead of making requests.

    Attributes:
        sent: Every payload passed to :meth:`send`, in order.
    """

    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []
        self._counter = 0

    def send(self, payload: dict[str, Any]) -> str:
        """Record ``payload`` and return a deterministic fake message id.

        Args:
            payload: A Cloud API message body.

        Returns:
            A synthetic id of the form ``wamid.fake.<n>``.
        """
        self.sent.append(payload)
        self._counter += 1
        return f"wamid.fake.{self._counter}"

    @property
    def texts(self) -> list[str]:
        """The body text of every recorded text message, in order."""
        bodies: list[str] = []
        for payload in self.sent:
            text = payload.get("text")
            if isinstance(text, dict):
                body = text.get("body")
                if isinstance(body, str):
                    bodies.append(body)
        return bodies

    def clear(self) -> None:
        """Forget all recorded sends and reset the id counter."""
        self.sent.clear()
        self._counter = 0
