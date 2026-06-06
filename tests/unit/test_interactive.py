"""Tests for interactive message builders (reply buttons and list menus)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from whatsapp_bot.interactive import (
    MAX_BUTTONS,
    Button,
    ListRow,
    ListSection,
    build_button_message,
    build_list_message,
)


def test_build_button_message_with_tuples() -> None:
    payload = build_button_message(
        "15551230001",
        "Pick one",
        [("yes", "Yes"), ("no", "No")],
        header="Confirm",
        footer="Viprasol",
    )
    assert payload["type"] == "interactive"
    assert payload["to"] == "15551230001"
    interactive = payload["interactive"]
    assert interactive["type"] == "button"
    assert interactive["body"]["text"] == "Pick one"
    assert interactive["header"] == {"type": "text", "text": "Confirm"}
    assert interactive["footer"] == {"text": "Viprasol"}
    buttons = interactive["action"]["buttons"]
    assert [b["reply"]["id"] for b in buttons] == ["yes", "no"]
    assert all(b["type"] == "reply" for b in buttons)


def test_build_button_message_with_button_objects() -> None:
    payload = build_button_message("1", "Hi", [Button(id="a", title="A")])
    assert payload["interactive"]["action"]["buttons"][0]["reply"]["title"] == "A"


def test_button_message_omits_optional_header_footer() -> None:
    payload = build_button_message("1", "Hi", [("a", "A")])
    interactive = payload["interactive"]
    assert "header" not in interactive
    assert "footer" not in interactive


def test_too_many_buttons_raises() -> None:
    too_many = [(f"id{i}", f"B{i}") for i in range(MAX_BUTTONS + 1)]
    with pytest.raises(ValueError, match=r"1\.\.3 buttons"):
        build_button_message("1", "x", too_many)


def test_zero_buttons_raises() -> None:
    with pytest.raises(ValueError, match=r"1\.\.3 buttons"):
        build_button_message("1", "x", [])


def test_button_title_too_long_rejected() -> None:
    with pytest.raises(ValidationError):
        Button(id="a", title="x" * 21)


def test_build_list_message_structure() -> None:
    section = ListSection(
        title="Topics",
        rows=[
            ListRow(id="billing", title="Billing", description="Plans"),
            ListRow(id="tech", title="Technical"),
        ],
    )
    payload = build_list_message("15551230002", "Choose", "Open", [section])
    interactive = payload["interactive"]
    assert interactive["type"] == "list"
    action = interactive["action"]
    assert action["button"] == "Open"
    rows = action["sections"][0]["rows"]
    assert rows[0] == {"id": "billing", "title": "Billing", "description": "Plans"}
    assert rows[1] == {"id": "tech", "title": "Technical"}  # no description key


def test_list_message_requires_sections() -> None:
    with pytest.raises(ValueError, match="at least one section"):
        build_list_message("1", "x", "Open", [])


def test_list_button_label_too_long() -> None:
    section = ListSection(title="S", rows=[ListRow(id="a", title="A")])
    with pytest.raises(ValueError, match="button label"):
        build_list_message("1", "x", "x" * 21, [section])


def test_list_total_rows_capped() -> None:
    rows = [ListRow(id=f"r{i}", title=f"R{i}") for i in range(11)]
    section = ListSection(title="S", rows=rows)
    with pytest.raises(ValueError, match="too many list rows"):
        build_list_message("1", "x", "Open", [section])
