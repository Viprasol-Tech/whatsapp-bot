"""Tests for webhook parsing and the verification handshake."""

from __future__ import annotations

from typing import Any

import pytest

from whatsapp_bot.webhook import (
    WebhookParseError,
    parse_message,
    parse_messages,
    verify_challenge,
)


def _payload(messages: list[dict[str, Any]], contacts: list[dict[str, Any]]) -> dict[str, Any]:
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
                            "contacts": contacts,
                            "messages": messages,
                        },
                    }
                ],
            }
        ],
    }


def test_parse_text_message() -> None:
    payload = _payload(
        messages=[
            {
                "from": "15551230001",
                "id": "wamid.AAA",
                "timestamp": "1700000000",
                "type": "text",
                "text": {"body": "hello world"},
            }
        ],
        contacts=[{"wa_id": "15551230001", "profile": {"name": "Ada"}}],
    )
    message = parse_message(payload)
    assert message.sender == "15551230001"
    assert message.text == "hello world"
    assert message.type == "text"
    assert message.message_id == "wamid.AAA"
    assert message.timestamp == "1700000000"
    assert message.contact_name == "Ada"


def test_parse_non_text_message_has_empty_text() -> None:
    payload = _payload(
        messages=[{"from": "15551230002", "id": "wamid.IMG", "type": "image"}],
        contacts=[],
    )
    message = parse_message(payload)
    assert message.type == "image"
    assert message.text == ""
    assert message.contact_name == ""


def test_parse_multiple_messages() -> None:
    payload = _payload(
        messages=[
            {"from": "1", "type": "text", "text": {"body": "a"}},
            {"from": "2", "type": "text", "text": {"body": "b"}},
        ],
        contacts=[],
    )
    messages = parse_messages(payload)
    assert [m.text for m in messages] == ["a", "b"]


def test_status_only_payload_yields_no_messages() -> None:
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "0",
                "changes": [
                    {"field": "messages", "value": {"statuses": [{"status": "delivered"}]}}
                ],
            }
        ],
    }
    assert parse_messages(payload) == []


def test_malformed_payload_no_entry() -> None:
    with pytest.raises(WebhookParseError):
        parse_messages({"object": "whatsapp_business_account"})


def test_malformed_payload_not_a_dict() -> None:
    with pytest.raises(WebhookParseError):
        parse_messages("nope")  # type: ignore[arg-type]


def test_message_missing_from_raises() -> None:
    payload = _payload(messages=[{"type": "text", "text": {"body": "x"}}], contacts=[])
    with pytest.raises(WebhookParseError):
        parse_messages(payload)


def test_parse_message_requires_at_least_one() -> None:
    payload = _payload(messages=[], contacts=[])
    with pytest.raises(WebhookParseError):
        parse_message(payload)


def test_verify_challenge_accepts_matching_token() -> None:
    params = {
        "hub.mode": "subscribe",
        "hub.verify_token": "s3cret",
        "hub.challenge": "1158201444",
    }
    assert verify_challenge(params, expected_token="s3cret") == "1158201444"


def test_verify_challenge_rejects_wrong_token() -> None:
    params = {
        "hub.mode": "subscribe",
        "hub.verify_token": "wrong",
        "hub.challenge": "x",
    }
    with pytest.raises(PermissionError):
        verify_challenge(params, expected_token="s3cret")


def test_verify_challenge_rejects_wrong_mode() -> None:
    params = {
        "hub.mode": "unsubscribe",
        "hub.verify_token": "s3cret",
        "hub.challenge": "x",
    }
    with pytest.raises(PermissionError):
        verify_challenge(params, expected_token="s3cret")


def test_verify_challenge_missing_challenge() -> None:
    params = {"hub.mode": "subscribe", "hub.verify_token": "s3cret"}
    with pytest.raises(WebhookParseError):
        verify_challenge(params, expected_token="s3cret")


def test_parse_interactive_button_reply() -> None:
    payload = _payload(
        messages=[
            {
                "from": "15551230003",
                "id": "wamid.BTN",
                "type": "interactive",
                "interactive": {
                    "type": "button_reply",
                    "button_reply": {"id": "/menu", "title": "Main menu"},
                },
            }
        ],
        contacts=[],
    )
    message = parse_message(payload)
    assert message.type == "interactive"
    assert message.interactive_reply_id == "/menu"
    assert message.interactive_reply_title == "Main menu"
    assert message.command_text == "/menu"


def test_parse_interactive_list_reply() -> None:
    payload = _payload(
        messages=[
            {
                "from": "15551230004",
                "type": "interactive",
                "interactive": {
                    "type": "list_reply",
                    "list_reply": {"id": "billing", "title": "Billing"},
                },
            }
        ],
        contacts=[],
    )
    message = parse_message(payload)
    assert message.interactive_reply_id == "billing"
    assert message.command_text == "billing"


def test_parse_image_message_media_fields() -> None:
    payload = _payload(
        messages=[
            {
                "from": "15551230005",
                "type": "image",
                "image": {
                    "id": "MID-99",
                    "mime_type": "image/png",
                    "caption": "look",
                },
            }
        ],
        contacts=[],
    )
    message = parse_message(payload)
    assert message.type == "image"
    assert message.media_id == "MID-99"
    assert message.media_mime_type == "image/png"
    assert message.caption == "look"


def test_parse_document_message_filename() -> None:
    payload = _payload(
        messages=[
            {
                "from": "15551230006",
                "type": "document",
                "document": {"id": "DOC-1", "filename": "report.pdf"},
            }
        ],
        contacts=[],
    )
    message = parse_message(payload)
    assert message.filename == "report.pdf"
    assert message.media_id == "DOC-1"


def test_command_text_for_plain_text_is_text() -> None:
    payload = _payload(
        messages=[{"from": "1", "type": "text", "text": {"body": "hi"}}],
        contacts=[],
    )
    assert parse_message(payload).command_text == "hi"
