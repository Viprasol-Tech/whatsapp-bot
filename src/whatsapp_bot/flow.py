"""A tiny conversational state machine for multi-step flows.

Many bot interactions are wizards: ask for a name, then an email, then confirm.
:class:`Flow` models that as named :class:`Step` handlers. Each step receives the
inbound message and the user's :class:`~whatsapp_bot.session.Session`, does its
work, and returns a :class:`StepResult` saying what to reply and where to go next
(stay, advance to a named step, or finish).

The flow stores the current step name in ``session.state`` (namespaced by the
flow name) so multiple flows can coexist and a user can be resumed mid-flow after
a restart if your session store is persistent.

Part of WhatsApp Bot by Viprasol Tech Private Limited (https://viprasol.com).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from whatsapp_bot.session import Session, SessionStore
from whatsapp_bot.webhook import IncomingMessage


@dataclass
class StepResult:
    """The outcome of running a flow step.

    Attributes:
        reply: Text to send back to the user.
        next_step: Name of the step to move to; ``None`` means stay on the
            current step (e.g. re-prompt after invalid input).
        done: If ``True``, the flow ends and the user's flow state is cleared.
    """

    reply: str
    next_step: str | None = None
    done: bool = False


Step = Callable[[IncomingMessage, Session], StepResult]
"""A flow step: ``(message, session) -> StepResult``."""


class FlowError(ValueError):
    """Raised when a flow is misconfigured (unknown step, no start, ...)."""


class Flow:
    """A named, session-backed conversational state machine.

    Args:
        name: A unique flow name; used to namespace the step pointer in the
            session so multiple flows don't clobber each other.
        store: The :class:`SessionStore` holding per-user state.

    Example:
        >>> from whatsapp_bot.session import SessionStore
        >>> store = SessionStore()
        >>> flow = Flow("signup", store)
        >>> @flow.step("ask_name", start=True)
        ... def _ask(msg, sess):
        ...     if not msg.text.strip():
        ...         return StepResult("What's your name?")
        ...     sess.set("name", msg.text.strip())
        ...     return StepResult(f"Thanks, {sess.get('name')}!", done=True)
    """

    def __init__(self, name: str, store: SessionStore) -> None:
        self.name = name
        self._store = store
        self._steps: dict[str, Step] = {}
        self._start: str | None = None

    @property
    def _state_key(self) -> str:
        return f"__flow__:{self.name}"

    def step(self, name: str, *, start: bool = False) -> Callable[[Step], Step]:
        """Decorator registering ``handler`` as the step called ``name``.

        Args:
            name: The step's unique name within this flow.
            start: Mark this as the entry step (exactly one is required).

        Returns:
            A decorator that registers and returns the step unchanged.
        """

        def decorator(handler: Step) -> Step:
            self.add_step(name, handler, start=start)
            return handler

        return decorator

    def add_step(self, name: str, handler: Step, *, start: bool = False) -> None:
        """Register ``handler`` as step ``name`` (imperative form of :meth:`step`)."""
        if name in self._steps:
            raise FlowError(f"duplicate step name: {name!r}")
        self._steps[name] = handler
        if start:
            if self._start is not None:
                raise FlowError("flow already has a start step")
            self._start = name

    @property
    def steps(self) -> list[str]:
        """The registered step names, sorted."""
        return sorted(self._steps)

    def is_active(self, user_id: str) -> bool:
        """Return True if ``user_id`` is currently part-way through this flow."""
        session = self._store.get(user_id)
        return bool(session and session.get(self._state_key))

    def current_step(self, user_id: str) -> str | None:
        """Return the user's current step name, or ``None`` if not in the flow."""
        session = self._store.get(user_id)
        if session is None:
            return None
        value = session.get(self._state_key)
        return value if isinstance(value, str) else None

    def reset(self, user_id: str) -> None:
        """Clear this flow's state for ``user_id`` (other flows untouched)."""
        session = self._store.get(user_id)
        if session is not None:
            session.data.pop(self._state_key, None)
            self._store.save(session)

    def handle(self, message: IncomingMessage) -> str:
        """Advance the flow for ``message`` and return the reply text.

        If the user has no active step, the flow starts at the entry step. The
        chosen step runs, the session is updated to point at the next step (or
        cleared if the step finished), and the step's reply is returned.

        Raises:
            FlowError: If the flow has no start step or points at an unknown step.
        """
        if self._start is None:
            raise FlowError("flow has no start step")

        session = self._store.get_or_create(message.sender)
        current = session.get(self._state_key) or self._start
        if current not in self._steps:
            raise FlowError(f"unknown step: {current!r}")

        result = self._steps[current](message, session)

        if result.done:
            session.data.pop(self._state_key, None)
        else:
            target = result.next_step if result.next_step is not None else current
            if target not in self._steps:
                raise FlowError(f"step transitioned to unknown step: {target!r}")
            session.set(self._state_key, target)

        self._store.save(session)
        return result.reply
