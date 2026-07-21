"""Optional Langfuse tracing for the assistant, behind a langfuse-agnostic seam.

The service depends on the :class:`Tracer` interface, not on Langfuse. The default
:class:`NoOpTracer` yields a no-op handle so the streaming code is unconditional and
adds nothing when tracing is off — and, crucially, the ``langfuse`` SDK is imported
**lazily** (only inside :class:`LangfuseTracer`), so a deployment with tracing
disabled never imports it. Mirrors the ABC/Protocol seam used for the model client.

When enabled, one ``/assistant/chat`` request becomes one Langfuse trace named
``assistant-chat`` (tagged with the therapist ``user_id`` and the conversation
``session_id``); the per-round model generations created by the OpenAI drop-in
(``langfuse.openai``) nest under it automatically via OpenTelemetry context.
"""

from __future__ import annotations

import logging
import sys
from abc import ABC, abstractmethod
from contextlib import AbstractContextManager, ExitStack, contextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterator

    from core.config import Settings

logger = logging.getLogger(__name__)

_TRACE_NAME = "assistant-chat"


class ChatTrace(ABC):
    """A live handle to the current chat trace: record its final output or an error.

    Both methods run mid-stream and must never raise — implementations swallow any
    tracing failure — so callers can record without guarding each call.
    """

    @abstractmethod
    def set_output(self, text: str) -> None: ...

    @abstractmethod
    def set_error(self, message: str) -> None: ...


class Tracer(ABC):
    """Opens a trace spanning one chat request. The model generations nest under it."""

    @abstractmethod
    def trace_chat(
        self, *, user_id: str | None, session_id: str | None
    ) -> AbstractContextManager[ChatTrace]: ...


class _NoOpChatTrace(ChatTrace):
    def set_output(self, text: str) -> None: ...

    def set_error(self, message: str) -> None: ...


class NoOpTracer(Tracer):
    """The default: does nothing, so the assistant behaves exactly as before."""

    @contextmanager
    def trace_chat(self, *, user_id: str | None, session_id: str | None) -> Iterator[ChatTrace]:
        yield _NoOpChatTrace()


class _LangfuseChatTrace(ChatTrace):
    def __init__(self, span: Any) -> None:
        self._span = span

    # Recording is best-effort: it runs mid-stream, so a Langfuse/SDK failure here must
    # be swallowed, never propagated into the response the caller is streaming.
    def set_output(self, text: str) -> None:
        try:
            self._span.update(output=text)
        except Exception:
            logger.warning("langfuse set_output failed", exc_info=True)

    def set_error(self, message: str) -> None:
        try:
            self._span.update(level="ERROR", status_message=message)
        except Exception:
            logger.warning("langfuse set_error failed", exc_info=True)


class LangfuseTracer(Tracer):
    """Traces each chat request with Langfuse, grouping the model rounds under it."""

    def __init__(self, client: Any) -> None:
        self._client = client

    @contextmanager
    def trace_chat(self, *, user_id: str | None, session_id: str | None) -> Iterator[ChatTrace]:
        # Imported here so the SDK is only required when tracing is actually enabled.
        from langfuse import propagate_attributes

        attrs: dict[str, Any] = {"trace_name": _TRACE_NAME, "tags": ["assistant"]}
        if user_id:
            attrs["user_id"] = user_id
        if session_id:
            attrs["session_id"] = session_id

        # Enter the span + attribute scopes and guard ONLY setup: a Langfuse failure
        # while opening the trace degrades to an untraced chat. The ExitStack unwinds any
        # scope that DID enter (so a half-open span can't leak into the worker context).
        # Critically, the `yield` is outside this guard — an exception thrown back in from
        # the streamed body must never be caught here (a second yield would raise
        # "generator didn't stop", breaking the stream); it belongs to the caller.
        stack = ExitStack()
        try:
            span = stack.enter_context(
                self._client.start_as_current_observation(name=_TRACE_NAME, as_type="span")
            )
            stack.enter_context(propagate_attributes(**attrs))
        except Exception:
            stack.close()
            logger.warning("langfuse trace setup failed; continuing untraced", exc_info=True)
            yield _NoOpChatTrace()
            return

        try:
            yield _LangfuseChatTrace(span)
        finally:
            # Close the scopes (innermost first), forwarding any in-flight exception so
            # the span records it. Teardown is guarded so closing the trace can never be
            # what breaks the stream.
            try:
                stack.__exit__(*sys.exc_info())
            except Exception:
                logger.warning("langfuse trace teardown failed", exc_info=True)


_client_singleton: Any = None


def _get_langfuse(settings: Settings) -> Any:
    """The process-wide Langfuse client (constructed once from settings)."""
    global _client_singleton
    if _client_singleton is None:
        from langfuse import Langfuse

        _client_singleton = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_base_url,
        )
    return _client_singleton


def build_tracer(settings: Settings) -> Tracer:
    """A :class:`LangfuseTracer` when tracing is enabled and keyed, else a no-op."""
    if not (
        settings.langfuse_enabled and settings.langfuse_public_key and settings.langfuse_secret_key
    ):
        return NoOpTracer()
    return LangfuseTracer(_get_langfuse(settings))


def shutdown_tracing() -> None:
    """Flush buffered Langfuse events on shutdown. No-op if tracing was never used, so
    it never imports the SDK unless a client was already built."""
    if _client_singleton is not None:
        try:
            _client_singleton.flush()
        except Exception:
            logger.warning("langfuse flush on shutdown failed", exc_info=True)


__all__ = [
    "ChatTrace",
    "Tracer",
    "NoOpTracer",
    "LangfuseTracer",
    "build_tracer",
    "shutdown_tracing",
]
