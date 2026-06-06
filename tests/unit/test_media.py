"""Tests for media message parsing and builders."""

from __future__ import annotations

import pytest

from whatsapp_bot.media import (
    Media,
    build_media_message,
    is_media_message,
    media_from_message,
)
from whatsapp_bot.webhook import IncomingMessage


def _media_msg(msg_type: str, **kw: str) -> IncomingMessage:
    return IncomingMessage(sender="15550000000", type=msg_type, **kw)


def test_media_from_image_message() -> None:
    msg = _media_msg(
        "image",
        media_id="MID-1",
        media_mime_type="image/jpeg",
        caption="a cat",
    )
    media = media_from_message(msg)
    assert media is not None
    assert media.is_image
    assert media.media_id == "MID-1"
    assert media.caption == "a cat"
    assert media.extension == "jpeg"


def test_media_from_document_message_has_filename() -> None:
    msg = _media_msg(
        "document",
        media_id="DOC-1",
        media_mime_type="application/pdf",
        filename="invoice.pdf",
    )
    media = media_from_message(msg)
    assert media is not None
    assert media.is_document
    assert media.filename == "invoice.pdf"
    assert media.extension == "pdf"


def test_text_message_has_no_media() -> None:
    msg = IncomingMessage(sender="1", text="hi", type="text")
    assert media_from_message(msg) is None
    assert not is_media_message(msg)


def test_media_message_without_id_is_not_media() -> None:
    msg = _media_msg("image")  # no media_id
    assert not is_media_message(msg)
    assert media_from_message(msg) is None


def test_extension_handles_parameters_and_missing() -> None:
    assert Media(type="audio", media_id="x", mime_type="audio/ogg; codecs=opus").extension == "ogg"
    assert Media(type="audio", media_id="x", mime_type="").extension == ""


def test_build_media_message_image_with_caption() -> None:
    payload = build_media_message("1", "image", "MID", caption="hello")
    assert payload["type"] == "image"
    assert payload["image"] == {"id": "MID", "caption": "hello"}


def test_build_media_message_document_with_filename() -> None:
    payload = build_media_message("1", "document", "DOC", filename="r.pdf")
    assert payload["document"] == {"id": "DOC", "filename": "r.pdf"}


def test_build_media_message_audio_ignores_caption_and_filename() -> None:
    payload = build_media_message("1", "audio", "AID", caption="x", filename="y")
    assert payload["audio"] == {"id": "AID"}


def test_build_media_message_rejects_bad_type() -> None:
    with pytest.raises(ValueError, match="unsupported media type"):
        build_media_message("1", "location", "X")
