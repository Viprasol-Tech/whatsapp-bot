"""Tests for the conversational flow state machine."""

from __future__ import annotations

import pytest

from whatsapp_bot.flow import Flow, FlowError, StepResult
from whatsapp_bot.session import Session, SessionStore
from whatsapp_bot.webhook import IncomingMessage


def _msg(sender: str, text: str) -> IncomingMessage:
    return IncomingMessage(sender=sender, text=text)


def _signup_flow(store: SessionStore) -> Flow:
    flow = Flow("signup", store)

    @flow.step("ask_name", start=True)
    def _ask_name(message: IncomingMessage, session: Session) -> StepResult:
        if not message.text.strip():
            return StepResult("Name?")
        session.set("name", message.text.strip())
        return StepResult("Email?", next_step="ask_email")

    @flow.step("ask_email")
    def _ask_email(message: IncomingMessage, session: Session) -> StepResult:
        if "@" not in message.text:
            return StepResult("Invalid, retry")
        session.set("email", message.text.strip())
        return StepResult("Done", done=True)

    return flow


def test_flow_full_happy_path() -> None:
    store = SessionStore()
    flow = _signup_flow(store)
    user = "1"

    assert flow.handle(_msg(user, "Ada")) == "Email?"
    assert flow.current_step(user) == "ask_email"
    assert flow.is_active(user)

    assert flow.handle(_msg(user, "ada@x.com")) == "Done"
    assert not flow.is_active(user)
    session = store.get(user)
    assert session is not None
    assert session.get("name") == "Ada"
    assert session.get("email") == "ada@x.com"


def test_flow_stays_on_step_when_next_is_none() -> None:
    store = SessionStore()
    flow = _signup_flow(store)
    assert flow.handle(_msg("1", "")) == "Name?"
    assert flow.current_step("1") == "ask_name"


def test_flow_reprompts_on_invalid_input() -> None:
    store = SessionStore()
    flow = _signup_flow(store)
    flow.handle(_msg("1", "Ada"))
    assert flow.handle(_msg("1", "bad-email")) == "Invalid, retry"
    assert flow.current_step("1") == "ask_email"


def test_flow_reset_clears_state() -> None:
    store = SessionStore()
    flow = _signup_flow(store)
    flow.handle(_msg("1", "Ada"))
    flow.reset("1")
    assert not flow.is_active("1")
    # restarting begins at the start step again
    assert flow.handle(_msg("1", "")) == "Name?"


def test_two_flows_share_store_without_clobbering() -> None:
    store = SessionStore()
    a = _signup_flow(store)
    b = Flow("survey", store)

    @b.step("q1", start=True)
    def _q1(message: IncomingMessage, session: Session) -> StepResult:
        return StepResult("answered", done=True)

    a.handle(_msg("1", "Ada"))  # a now on ask_email
    b.handle(_msg("1", "hi"))  # b completes immediately
    assert a.current_step("1") == "ask_email"
    assert not b.is_active("1")


def test_steps_property_sorted() -> None:
    store = SessionStore()
    flow = _signup_flow(store)
    assert flow.steps == ["ask_email", "ask_name"]


def test_duplicate_step_name_raises() -> None:
    flow = Flow("f", SessionStore())
    flow.add_step("s", lambda m, s: StepResult("x"), start=True)
    with pytest.raises(FlowError, match="duplicate step"):
        flow.add_step("s", lambda m, s: StepResult("y"))


def test_two_start_steps_raise() -> None:
    flow = Flow("f", SessionStore())
    flow.add_step("a", lambda m, s: StepResult("x"), start=True)
    with pytest.raises(FlowError, match="already has a start"):
        flow.add_step("b", lambda m, s: StepResult("y"), start=True)


def test_handle_without_start_raises() -> None:
    flow = Flow("f", SessionStore())
    flow.add_step("a", lambda m, s: StepResult("x"))
    with pytest.raises(FlowError, match="no start step"):
        flow.handle(_msg("1", "x"))


def test_transition_to_unknown_step_raises() -> None:
    flow = Flow("f", SessionStore())
    flow.add_step("a", lambda m, s: StepResult("x", next_step="ghost"), start=True)
    with pytest.raises(FlowError, match="unknown step"):
        flow.handle(_msg("1", "go"))


def test_current_step_none_for_unknown_user() -> None:
    flow = _signup_flow(SessionStore())
    assert flow.current_step("nobody") is None
