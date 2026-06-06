"""WhatsApp Cloud API webhook parsing and verification.

This module turns a raw WhatsApp Cloud API webhook payload (the JSON Meta POSTs
to your endpoint) into a typed :class:`IncomingMessage`, and implements the
``GET`` challenge handshake Meta uses to verify your webhook URL.

The functions here are pure and offline — they take dictionaries and strings,
not HTTP requests — so they can be wired into any web framework (FastAPI, Flask,
Django, ...) and fully unit-tested without a network.

Part of WhatsApp Bot by Viprasol Tech Private Limited (https://viprasol.com).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class IncomingMessage(BaseModel):
    """A single inbound WhatsApp message, normalized from a webhook payload.

    Attributes:
        sender: The sender's WhatsApp phone number in E.164 digits (the ``from``
            field; ``from`` is a Python keyword so the attribute is ``sender``).
        text: The message body for ``text`` messages, otherwise an empty string.
        type: The WhatsApp message type, e.g. ``"text"``, ``"image"``, ``"audio"``.
        message_id: The provider message id (``wamid....``), useful for de-duping.
        timestamp: The provider-supplied unix timestamp string, if present.
        contact_name: The sender's profile display name, if the payload included it.
    """

    sender: str = Field(..., description="Sender phone number (E.164 digits).")
    text: str = Field(default="", description="Text body, empty for non-text types.")
    type: str = Field(default="text", description="WhatsApp message type.")
    message_id: str = Field(default="", description="Provider message id (wamid...).")
    timestamp: str = Field(default="", description="Provider unix timestamp string.")
    contact_name: str = Field(default="", description="Sender profile display name.")
    interactive_reply_id: str = Field(
        default="",
        description="The id of the tapped button/list row for interactive replies.",
    )
    interactive_reply_title: str = Field(
        default="",
        description="The visible title of the tapped button/list row.",
    )
    media_id: str = Field(default="", description="Media id for image/audio/video/document.")
    media_mime_type: str = Field(default="", description="Media MIME type, if present.")
    caption: str = Field(default="", description="Caption for a media message, if present.")
    filename: str = Field(default="", description="Filename for a document message, if present.")

    @property
    def command_text(self) -> str:
        """Text used for command routing.

        For ``interactive`` messages this is the tapped reply id so that buttons
        and list rows can be routed exactly like slash commands; otherwise it is
        the plain :attr:`text`.
        """
        if self.type == "interactive" and self.interactive_reply_id:
            return self.interactive_reply_id
        return self.text


class WebhookParseError(ValueError):
    """Raised when a webhook payload is malformed or contains no message."""


def verify_challenge(
    params: dict[str, str],
    *,
    expected_token: str,
) -> str:
    """Validate a WhatsApp webhook verification (``GET``) request.

    When you register a webhook, Meta sends a ``GET`` request with the query
    parameters ``hub.mode``, ``hub.verify_token`` and ``hub.challenge``. You must
    echo back ``hub.challenge`` verbatim **only** if ``hub.mode`` is ``subscribe``
    and ``hub.verify_token`` matches the token you configured.

    Args:
        params: The request query parameters as a mapping of strings.
        expected_token: The verify token you configured with Meta.

    Returns:
        The ``hub.challenge`` value to write back in the HTTP response body.

    Raises:
        PermissionError: If the mode is not ``subscribe`` or the token mismatches.
        WebhookParseError: If the challenge parameter is missing.
    """
    mode = params.get("hub.mode", "")
    token = params.get("hub.verify_token", "")
    challenge = params.get("hub.challenge")

    if mode != "subscribe" or token != expected_token:
        raise PermissionError("webhook verification failed: mode/token mismatch")
    if challenge is None:
        raise WebhookParseError("missing hub.challenge")
    return challenge


def _iter_message_changes(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Yield each ``changes[].value`` block that carries inbound messages."""
    blocks: list[dict[str, Any]] = []
    entries = payload.get("entry")
    if not isinstance(entries, list):
        raise WebhookParseError("payload has no 'entry' list")
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        changes = entry.get("changes")
        if not isinstance(changes, list):
            continue
        for change in changes:
            if not isinstance(change, dict):
                continue
            value = change.get("value")
            if isinstance(value, dict) and isinstance(value.get("messages"), list):
                blocks.append(value)
    return blocks


def _name_by_wa_id(value: dict[str, Any]) -> dict[str, str]:
    """Build a ``wa_id -> profile name`` map from a value block's contacts."""
    names: dict[str, str] = {}
    contacts = value.get("contacts")
    if isinstance(contacts, list):
        for contact in contacts:
            if not isinstance(contact, dict):
                continue
            wa_id = contact.get("wa_id")
            profile = contact.get("profile")
            if isinstance(wa_id, str) and isinstance(profile, dict):
                name = profile.get("name")
                if isinstance(name, str):
                    names[wa_id] = name
    return names


_MEDIA_TYPES = frozenset({"image", "audio", "video", "document", "sticker"})


def _extract_text(raw: dict[str, Any]) -> str:
    """Pull the text body out of a ``text`` message, tolerating bad shapes."""
    body = raw.get("text")
    if isinstance(body, dict):
        value = body.get("body")
        if isinstance(value, str):
            return value
    return ""


def _extract_interactive(raw: dict[str, Any]) -> tuple[str, str]:
    """Return ``(reply_id, reply_title)`` for an interactive button/list reply."""
    interactive = raw.get("interactive")
    if not isinstance(interactive, dict):
        return "", ""
    kind = interactive.get("type")
    block = interactive.get(kind) if isinstance(kind, str) else None
    if not isinstance(block, dict):
        return "", ""
    reply_id = block.get("id")
    title = block.get("title")
    return (
        reply_id if isinstance(reply_id, str) else "",
        title if isinstance(title, str) else "",
    )


def _extract_media(raw: dict[str, Any], msg_type: str) -> tuple[str, str, str, str]:
    """Return ``(media_id, mime_type, caption, filename)`` for a media message."""
    block = raw.get(msg_type)
    if not isinstance(block, dict):
        return "", "", "", ""

    def _s(key: str) -> str:
        value = block.get(key)
        return value if isinstance(value, str) else ""

    return _s("id"), _s("mime_type"), _s("caption"), _s("filename")


def _parse_one(raw: dict[str, Any], names: dict[str, str]) -> IncomingMessage:
    """Normalize a single raw webhook message object into an IncomingMessage."""
    if not isinstance(raw, dict):
        raise WebhookParseError("message entry is not an object")
    sender = raw.get("from")
    if not isinstance(sender, str) or not sender:
        raise WebhookParseError("message missing 'from'")

    msg_type = raw.get("type")
    msg_type = msg_type if isinstance(msg_type, str) else "text"

    text = _extract_text(raw) if msg_type == "text" else ""
    reply_id, reply_title = _extract_interactive(raw) if msg_type == "interactive" else ("", "")
    media_id, mime_type, caption, filename = (
        _extract_media(raw, msg_type) if msg_type in _MEDIA_TYPES else ("", "", "", "")
    )

    return IncomingMessage(
        sender=sender,
        text=text,
        type=msg_type,
        message_id=str(raw.get("id", "")),
        timestamp=str(raw.get("timestamp", "")),
        contact_name=names.get(sender, ""),
        interactive_reply_id=reply_id,
        interactive_reply_title=reply_title,
        media_id=media_id,
        media_mime_type=mime_type,
        caption=caption,
        filename=filename,
    )


def parse_messages(payload: dict[str, Any]) -> list[IncomingMessage]:
    """Parse every inbound message in a WhatsApp webhook payload.

    Status callbacks (delivery/read receipts) carry no ``messages`` array and are
    silently skipped, so this returns only genuine inbound user messages.

    Args:
        payload: The decoded JSON body Meta POSTed to your webhook.

    Returns:
        A list of :class:`IncomingMessage`, possibly empty (e.g. a status-only
        callback).

    Raises:
        WebhookParseError: If ``payload`` is not a WhatsApp webhook envelope
            (no ``entry`` list) or a contained message is missing required fields.
    """
    if not isinstance(payload, dict):
        raise WebhookParseError("payload must be a JSON object")

    out: list[IncomingMessage] = []
    for value in _iter_message_changes(payload):
        names = _name_by_wa_id(value)
        for raw in value["messages"]:
            out.append(_parse_one(raw, names))
    return out


def parse_message(payload: dict[str, Any]) -> IncomingMessage:
    """Parse a payload expected to contain exactly one inbound message.

    Args:
        payload: The decoded JSON webhook body.

    Returns:
        The single :class:`IncomingMessage` found.

    Raises:
        WebhookParseError: If the payload contains zero messages.
    """
    messages = parse_messages(payload)
    if not messages:
        raise WebhookParseError("payload contained no inbound messages")
    return messages[0]
