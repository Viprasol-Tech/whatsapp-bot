"""WhatsApp Bot — transport-agnostic WhatsApp Cloud API bot template by Viprasol Tech."""

from __future__ import annotations

from whatsapp_bot.bot import Bot, Reply
from whatsapp_bot.flow import Flow, FlowError, StepResult
from whatsapp_bot.interactive import (
    Button,
    ListRow,
    ListSection,
    build_button_message,
    build_list_message,
)
from whatsapp_bot.media import Media, build_media_message, media_from_message
from whatsapp_bot.middleware import (
    MiddlewareChain,
    keyword_block_middleware,
    logging_middleware,
    rate_limit_middleware,
)
from whatsapp_bot.router import Router, default_router
from whatsapp_bot.sender import FakeSender, Sender, build_text_message
from whatsapp_bot.session import Session, SessionStore
from whatsapp_bot.webhook import (
    IncomingMessage,
    WebhookParseError,
    parse_message,
    parse_messages,
    verify_challenge,
)

__version__ = "0.2.0"
__author__ = "Viprasol Tech Private Limited"
__all__ = [
    "Bot",
    "Button",
    "FakeSender",
    "Flow",
    "FlowError",
    "IncomingMessage",
    "ListRow",
    "ListSection",
    "Media",
    "MiddlewareChain",
    "Reply",
    "Router",
    "Sender",
    "Session",
    "SessionStore",
    "StepResult",
    "WebhookParseError",
    "__version__",
    "build_button_message",
    "build_list_message",
    "build_media_message",
    "build_text_message",
    "default_router",
    "keyword_block_middleware",
    "logging_middleware",
    "media_from_message",
    "parse_message",
    "parse_messages",
    "rate_limit_middleware",
    "verify_challenge",
]
