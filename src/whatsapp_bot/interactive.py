"""Builders for WhatsApp interactive messages (reply buttons and list menus).

The WhatsApp Cloud API supports two flavours of interactive message:

* **Reply buttons** — up to three tappable buttons.
* **List messages** — a single button that opens a sectioned, scrollable list.

These functions assemble the exact JSON bodies you POST to the ``/messages``
endpoint. They are pure and offline, validate the provider's documented limits up
front (so you fail fast in tests rather than with a 400 from Meta), and pair with
:attr:`whatsapp_bot.webhook.IncomingMessage.interactive_reply_id` for routing the
user's tap straight back into your :class:`~whatsapp_bot.router.Router`.

Part of WhatsApp Bot by Viprasol Tech Private Limited (https://viprasol.com).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel, Field

MAX_BUTTONS = 3
"""WhatsApp allows at most three reply buttons per message."""

MAX_BUTTON_TITLE = 20
"""Reply-button and list-row titles are capped at 20 characters."""

MAX_LIST_ROWS = 10
"""A list message may contain at most ten rows in total across all sections."""


class Button(BaseModel):
    """A single reply button.

    Attributes:
        id: The identifier echoed back when the user taps it (route on this).
        title: The visible label (max 20 chars).
    """

    id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1, max_length=MAX_BUTTON_TITLE)


class ListRow(BaseModel):
    """A single selectable row inside a list section.

    Attributes:
        id: The identifier echoed back when the user selects it.
        title: The visible row title (max 24 chars).
        description: Optional secondary text shown under the title.
    """

    id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1, max_length=24)
    description: str = Field(default="", max_length=72)


class ListSection(BaseModel):
    """A titled group of rows within a list message."""

    title: str = Field(..., min_length=1, max_length=24)
    rows: list[ListRow] = Field(..., min_length=1)


def _coerce_buttons(buttons: Sequence[Button | tuple[str, str]]) -> list[Button]:
    """Accept ``Button`` objects or ``(id, title)`` tuples for ergonomics."""
    out: list[Button] = []
    for item in buttons:
        out.append(item if isinstance(item, Button) else Button(id=item[0], title=item[1]))
    return out


def build_button_message(
    to: str,
    body: str,
    buttons: Sequence[Button | tuple[str, str]],
    *,
    header: str = "",
    footer: str = "",
) -> dict[str, Any]:
    """Build an interactive reply-button message payload.

    Args:
        to: Recipient WhatsApp number in E.164 digits.
        body: The main prompt text shown above the buttons.
        buttons: 1-3 buttons, as :class:`Button` objects or ``(id, title)`` tuples.
        header: Optional bold header text.
        footer: Optional small footer text.

    Returns:
        A Cloud API ``interactive`` message body of subtype ``button``.

    Raises:
        ValueError: If there are zero buttons or more than :data:`MAX_BUTTONS`.
    """
    resolved = _coerce_buttons(buttons)
    if not 1 <= len(resolved) <= MAX_BUTTONS:
        raise ValueError(f"need 1..{MAX_BUTTONS} buttons, got {len(resolved)}")

    interactive: dict[str, Any] = {
        "type": "button",
        "body": {"text": body},
        "action": {
            "buttons": [
                {"type": "reply", "reply": {"id": b.id, "title": b.title}} for b in resolved
            ]
        },
    }
    if header:
        interactive["header"] = {"type": "text", "text": header}
    if footer:
        interactive["footer"] = {"text": footer}

    return {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "interactive",
        "interactive": interactive,
    }


def build_list_message(
    to: str,
    body: str,
    button: str,
    sections: Sequence[ListSection],
    *,
    header: str = "",
    footer: str = "",
) -> dict[str, Any]:
    """Build an interactive list message payload.

    Args:
        to: Recipient WhatsApp number in E.164 digits.
        body: The prompt text shown above the list-open button.
        button: The label of the button that opens the list (max 20 chars).
        sections: One or more :class:`ListSection` groups of rows.
        header: Optional bold header text.
        footer: Optional small footer text.

    Returns:
        A Cloud API ``interactive`` message body of subtype ``list``.

    Raises:
        ValueError: If there are no sections, the open button is too long, or the
            total number of rows exceeds :data:`MAX_LIST_ROWS`.
    """
    if not sections:
        raise ValueError("a list message needs at least one section")
    if not 1 <= len(button) <= MAX_BUTTON_TITLE:
        raise ValueError(f"list button label must be 1..{MAX_BUTTON_TITLE} chars")
    total_rows = sum(len(s.rows) for s in sections)
    if total_rows > MAX_LIST_ROWS:
        raise ValueError(f"too many list rows: {total_rows} > {MAX_LIST_ROWS}")

    interactive: dict[str, Any] = {
        "type": "list",
        "body": {"text": body},
        "action": {
            "button": button,
            "sections": [
                {
                    "title": section.title,
                    "rows": [
                        {"id": row.id, "title": row.title, "description": row.description}
                        if row.description
                        else {"id": row.id, "title": row.title}
                        for row in section.rows
                    ],
                }
                for section in sections
            ],
        },
    }
    if header:
        interactive["header"] = {"type": "text", "text": header}
    if footer:
        interactive["footer"] = {"text": footer}

    return {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "interactive",
        "interactive": interactive,
    }
