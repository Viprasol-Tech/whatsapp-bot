# Changelog

All notable changes to this project are documented here. Format based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning follows
[SemVer](https://semver.org/).

## [0.2.0] - 2025

### Added
- **Interactive messages** (`whatsapp_bot.interactive`): builders for reply-button
  and sectioned list messages (`build_button_message`, `build_list_message`) with
  validated provider limits, plus `Button`, `ListRow` and `ListSection` models.
- **Media parsing** (`whatsapp_bot.media`): typed `Media` model, `media_from_message`
  extraction for image/audio/video/document/sticker, MIME-derived `extension`, and
  `build_media_message` for outgoing media.
- **Per-user sessions** (`whatsapp_bot.session`): `Session` and `SessionStore` with
  optional TTL expiry and an injectable clock for deterministic tests.
- **Conversational flows** (`whatsapp_bot.flow`): `Flow` state machine with named
  `Step` handlers, `StepResult` transitions, and session-backed step tracking.
- **Middleware chain** (`whatsapp_bot.middleware`): composable onion-model
  `MiddlewareChain` plus built-in `logging_middleware`, `rate_limit_middleware`, and
  `keyword_block_middleware`.
- More built-in commands in `default_router`: `/start`, `/ping`, `/about`.
- New CLI subcommands: `flow`, `interactive`, `middleware`.

### Changed
- `IncomingMessage` now carries interactive-reply and media fields and a
  `command_text` property; the router routes interactive button/list taps like
  commands.
- `Bot` accepts an optional `middleware` chain that wraps routing.
- Top-level package now re-exports the full public API.

## [0.1.0] - 2025

### Added
- Initial release of whatsapp-bot: WhatsApp bot template — webhook parsing, command routing, and a fake sender (offline).
