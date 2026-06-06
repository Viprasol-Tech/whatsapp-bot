"""Command-line interface for WhatsApp Bot.

``whatsapp-bot demo`` feeds sample webhook payloads through a :class:`Bot` wired
to a :class:`FakeSender`, printing the replies it would send — no network, no API
keys, no WhatsApp account required.

Part of WhatsApp Bot by Viprasol Tech Private Limited (https://viprasol.com).
"""

from __future__ import annotations

from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from whatsapp_bot import __version__
from whatsapp_bot.bot import Bot
from whatsapp_bot.flow import Flow, StepResult
from whatsapp_bot.interactive import ListRow as _ListRow
from whatsapp_bot.interactive import ListSection as _ListSection
from whatsapp_bot.interactive import build_button_message, build_list_message
from whatsapp_bot.middleware import MiddlewareChain, logging_middleware, rate_limit_middleware
from whatsapp_bot.router import default_router
from whatsapp_bot.sender import FakeSender
from whatsapp_bot.session import Session, SessionStore
from whatsapp_bot.webhook import IncomingMessage, verify_challenge

app = typer.Typer(add_completion=False, help="WhatsApp Bot — by Viprasol Tech.")
console = Console()


def _sample_payload(sender: str, text: str) -> dict[str, Any]:
    """Build a minimal but realistic WhatsApp Cloud API webhook payload."""
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
                            "contacts": [{"wa_id": sender, "profile": {"name": "Demo User"}}],
                            "messages": [
                                {
                                    "from": sender,
                                    "id": f"wamid.demo.{abs(hash(text)) % 100000}",
                                    "timestamp": "1700000000",
                                    "type": "text",
                                    "text": {"body": text},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


@app.command()
def version() -> None:
    """Print the installed version."""
    console.print(f"whatsapp-bot [bold cyan]{__version__}[/] — by Viprasol Tech")


@app.command()
def demo() -> None:
    """Process sample inbound messages offline and show the bot's replies."""
    bot = Bot(default_router(), FakeSender())
    samples = [
        ("15551230001", "/help"),
        ("15551230002", "/menu"),
        ("15551230003", "Hello there!"),
    ]

    table = Table(title="WhatsApp Bot demo (offline)")
    table.add_column("From", style="cyan")
    table.add_column("Inbound", style="white")
    table.add_column("Reply", style="green")

    for sender, text in samples:
        replies = bot.process_webhook(_sample_payload(sender, text))
        reply_text = replies[0].text if replies else "(no reply)"
        table.add_row(sender, text, reply_text.replace("\n", " / "))

    console.print(table)
    sender_impl = bot.sender
    sent = len(sender_impl.sent) if isinstance(sender_impl, FakeSender) else 0
    console.print(f"Recorded [bold]{sent}[/] outgoing message(s) via FakeSender.")


def _build_signup_flow(store: SessionStore) -> Flow:
    """A two-step signup wizard used by the ``flow`` demo."""
    flow = Flow("signup", store)

    @flow.step("ask_name", start=True)
    def _ask_name(message: IncomingMessage, session: Session) -> StepResult:
        name = message.text.strip()
        if not name:
            return StepResult("What is your name?")
        session.set("name", name)
        return StepResult(f"Thanks {name}! What's your email?", next_step="ask_email")

    @flow.step("ask_email")
    def _ask_email(message: IncomingMessage, session: Session) -> StepResult:
        email = message.text.strip()
        if "@" not in email:
            return StepResult("That doesn't look like an email. Try again:")
        session.set("email", email)
        name = session.get("name")
        return StepResult(f"All set, {name}! We'll reach you at {email}.", done=True)

    return flow


@app.command()
def flow() -> None:
    """Walk a stateful multi-step signup flow offline, showing the transitions."""
    store = SessionStore()
    wizard = _build_signup_flow(store)
    user = "15551239999"
    turns = ["", "Ada Lovelace", "not-an-email", "ada@example.com"]

    table = Table(title="WhatsApp Bot flow demo (offline)")
    table.add_column("Step", style="cyan")
    table.add_column("Inbound", style="white")
    table.add_column("Reply", style="green")

    for text in turns:
        step = wizard.current_step(user) or "ask_name"
        reply = wizard.handle(IncomingMessage(sender=user, text=text))
        table.add_row(step, text or "(empty)", reply)

    console.print(table)
    session = store.get(user)
    collected = session.data if session else {}
    console.print(f"Collected: [bold]{collected}[/]")


@app.command()
def interactive() -> None:
    """Render sample interactive button and list payloads (the JSON Meta wants)."""
    buttons = build_button_message(
        "15551230001",
        "How can we help?",
        [("/menu", "Main menu"), ("support", "Talk to a human")],
        footer="Viprasol Tech",
    )
    listing = build_list_message(
        "15551230001",
        "Pick a topic",
        "Open topics",
        [
            _ListSection(
                title="Support",
                rows=[
                    _ListRow(id="billing", title="Billing", description="Invoices & plans"),
                    _ListRow(id="technical", title="Technical", description="Bugs & errors"),
                ],
            )
        ],
    )
    console.print("[bold]Reply-button message:[/]")
    console.print_json(data=buttons)
    console.print("[bold]List message:[/]")
    console.print_json(data=listing)


@app.command()
def middleware() -> None:
    """Show the middleware chain logging and rate-limiting messages offline."""
    chain = MiddlewareChain()
    chain.use(logging_middleware(lambda line: console.print(f"[dim]{line}[/]")))
    chain.use(rate_limit_middleware(2, 60.0))
    bot = Bot(default_router(), FakeSender(), middleware=chain)

    for text in ["/ping", "/ping", "/ping"]:
        bot.handle_message(IncomingMessage(sender="15551230007", text=text))
    console.print("Third /ping was throttled by the rate-limit middleware.")


@app.command()
def verify(
    token: str = typer.Option(..., help="The verify token you configured with Meta."),
    challenge: str = typer.Option("test-challenge", help="hub.challenge value."),
) -> None:
    """Demonstrate the webhook GET verification handshake offline."""
    params = {
        "hub.mode": "subscribe",
        "hub.verify_token": token,
        "hub.challenge": challenge,
    }
    try:
        echoed = verify_challenge(params, expected_token=token)
        console.print(f"Verification OK -> echo back: [bold green]{echoed}[/]")
    except PermissionError as exc:
        console.print(f"[red]Verification failed:[/] {exc}")
        raise typer.Exit(code=1) from exc


if __name__ == "__main__":
    app()
