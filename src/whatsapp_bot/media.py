"""Typed helpers for media messages (image, audio, video, document, sticker).

WhatsApp delivers media by reference: the webhook contains a ``media_id`` and
metadata, and you later fetch the bytes from the Graph API. This module models
that reference as :class:`Media` and provides :func:`media_from_message`, which
pulls the media fields out of an :class:`~whatsapp_bot.webhook.IncomingMessage`,
plus small convenience predicates (``is_image`` etc.) and a builder for outgoing
media messages.

Everything is offline: no bytes are downloaded here. The actual download is a
single authenticated ``GET`` you wire in at the transport layer.

Part of WhatsApp Bot by Viprasol Tech Private Limited (https://viprasol.com).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from whatsapp_bot.webhook import IncomingMessage

MEDIA_TYPES = frozenset({"image", "audio", "video", "document", "sticker"})
"""WhatsApp message types that carry a media reference."""


class Media(BaseModel):
    """A reference to media attached to an inbound message.

    Attributes:
        type: The owning message type (``"image"``, ``"document"``, ...).
        media_id: The provider media id used to download the bytes.
        mime_type: The MIME type, if the provider supplied one.
        caption: The user's caption, for image/video/document messages.
        filename: The original filename, for document messages.
    """

    type: str
    media_id: str = Field(..., min_length=1)
    mime_type: str = ""
    caption: str = ""
    filename: str = ""

    @property
    def is_image(self) -> bool:
        """True for image messages."""
        return self.type == "image"

    @property
    def is_document(self) -> bool:
        """True for document messages."""
        return self.type == "document"

    @property
    def is_audio(self) -> bool:
        """True for audio (including voice note) messages."""
        return self.type == "audio"

    @property
    def is_video(self) -> bool:
        """True for video messages."""
        return self.type == "video"

    @property
    def extension(self) -> str:
        """Best-effort file extension derived from the MIME type (no dot).

        ``"image/jpeg"`` -> ``"jpeg"``; unknown/empty -> ``""``.
        """
        if "/" not in self.mime_type:
            return ""
        subtype = self.mime_type.split("/", 1)[1]
        return subtype.split(";", 1)[0].strip()


def is_media_message(message: IncomingMessage) -> bool:
    """Return True if ``message`` carries a downloadable media reference."""
    return message.type in MEDIA_TYPES and bool(message.media_id)


def media_from_message(message: IncomingMessage) -> Media | None:
    """Extract a :class:`Media` from ``message``, or ``None`` if it has none.

    Args:
        message: The inbound message to inspect.

    Returns:
        A populated :class:`Media`, or ``None`` for non-media messages or media
        messages that lacked an id (which should not happen for valid payloads).
    """
    if not is_media_message(message):
        return None
    return Media(
        type=message.type,
        media_id=message.media_id,
        mime_type=message.media_mime_type,
        caption=message.caption,
        filename=message.filename,
    )


def build_media_message(
    to: str,
    media_type: str,
    media_id: str,
    *,
    caption: str = "",
    filename: str = "",
) -> dict[str, Any]:
    """Build a Cloud API outgoing media message that references an uploaded id.

    Args:
        to: Recipient WhatsApp number in E.164 digits.
        media_type: One of :data:`MEDIA_TYPES`.
        media_id: The id returned when you uploaded the media to WhatsApp.
        caption: Optional caption (image/video/document only).
        filename: Optional filename (document only).

    Returns:
        A Cloud API message body for the requested media type.

    Raises:
        ValueError: If ``media_type`` is not a supported media type.
    """
    if media_type not in MEDIA_TYPES:
        raise ValueError(f"unsupported media type: {media_type!r}")

    block: dict[str, Any] = {"id": media_id}
    if caption and media_type in {"image", "video", "document"}:
        block["caption"] = caption
    if filename and media_type == "document":
        block["filename"] = filename

    return {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": media_type,
        media_type: block,
    }
