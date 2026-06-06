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
from whatsapp_bot.router import default_router
from whatsapp_bot.sender import FakeSender
from whatsapp_bot.webhook import verify_challenge

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
