"""Tests for the Typer CLI commands (run offline via the test runner)."""

from __future__ import annotations

from typer.testing import CliRunner

from whatsapp_bot import __version__
from whatsapp_bot.cli import app

runner = CliRunner()


def test_version_command() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_demo_command_runs() -> None:
    result = runner.invoke(app, ["demo"])
    assert result.exit_code == 0
    assert "WhatsApp Bot demo" in result.stdout
    assert "outgoing message" in result.stdout


def test_flow_command_collects_data() -> None:
    result = runner.invoke(app, ["flow"])
    assert result.exit_code == 0
    assert "flow demo" in result.stdout
    assert "ada@example.com" in result.stdout


def test_interactive_command_outputs_payloads() -> None:
    result = runner.invoke(app, ["interactive"])
    assert result.exit_code == 0
    assert "button" in result.stdout
    assert "list" in result.stdout


def test_middleware_command_runs() -> None:
    result = runner.invoke(app, ["middleware"])
    assert result.exit_code == 0
    assert "throttled" in result.stdout


def test_verify_command_ok() -> None:
    result = runner.invoke(app, ["verify", "--token", "s3cret", "--challenge", "abc"])
    assert result.exit_code == 0
    assert "abc" in result.stdout
