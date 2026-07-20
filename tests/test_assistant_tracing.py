import contextlib
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any, Literal

import pytest

from assistant.tracing import LangfuseTracer, NoOpTracer, build_tracer, shutdown_tracing


class _FakeSpan:
    def __init__(self) -> None:
        self.updates: list[dict[str, Any]] = []

    def update(self, **kwargs: Any) -> None:
        self.updates.append(kwargs)


class _FakeLangfuse:
    """The slice of the Langfuse client the tracer touches."""

    def __init__(self) -> None:
        self.span = _FakeSpan()
        self.started: list[dict[str, Any]] = []

    @contextlib.contextmanager
    def start_as_current_observation(self, **kwargs: Any) -> Iterator[_FakeSpan]:
        self.started.append(kwargs)
        yield self.span


@pytest.fixture
def recorded_attrs(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Capture what LangfuseTracer passes to ``propagate_attributes`` (patched)."""
    recorded: dict[str, Any] = {}

    @contextlib.contextmanager
    def fake_propagate(**kwargs: Any) -> Iterator[None]:
        recorded.clear()
        recorded.update(kwargs)
        yield

    monkeypatch.setattr("langfuse.propagate_attributes", fake_propagate)
    return recorded


def test_noop_tracer_is_inert() -> None:
    with NoOpTracer().trace_chat(user_id="u", session_id="s") as trace:
        # No exception, and the handle accepts both calls.
        trace.set_output("done")
        trace.set_error("boom")


def test_langfuse_tracer_opens_span_and_records_output(recorded_attrs: dict[str, Any]) -> None:
    langfuse = _FakeLangfuse()

    with LangfuseTracer(langfuse).trace_chat(user_id="u1", session_id="s1") as trace:
        trace.set_output("שלום עולם")

    assert langfuse.started == [{"name": "assistant-chat", "as_type": "span"}]
    assert recorded_attrs == {
        "trace_name": "assistant-chat",
        "tags": ["assistant"],
        "user_id": "u1",
        "session_id": "s1",
    }
    assert {"output": "שלום עולם"} in langfuse.span.updates


def test_langfuse_tracer_records_an_error(recorded_attrs: dict[str, Any]) -> None:
    langfuse = _FakeLangfuse()

    with LangfuseTracer(langfuse).trace_chat(user_id="u1", session_id="s1") as trace:
        trace.set_error("overloaded")

    assert {"level": "ERROR", "status_message": "overloaded"} in langfuse.span.updates


def test_langfuse_tracer_omits_missing_user_and_session(recorded_attrs: dict[str, Any]) -> None:
    langfuse = _FakeLangfuse()

    with LangfuseTracer(langfuse).trace_chat(user_id=None, session_id=None):
        pass

    # Only the always-present attributes are propagated; no empty user/session.
    assert recorded_attrs == {"trace_name": "assistant-chat", "tags": ["assistant"]}


def test_langfuse_tracer_degrades_to_noop_when_span_fails(
    recorded_attrs: dict[str, Any],
) -> None:
    class _Broken:
        def start_as_current_observation(self, **_: Any) -> Any:
            raise RuntimeError("langfuse down")

    # A tracing failure must never break the chat: the block still runs.
    with LangfuseTracer(_Broken()).trace_chat(user_id="u", session_id="s") as trace:
        trace.set_output("still works")


class _RaisingSpan:
    def update(self, **_: Any) -> None:
        raise RuntimeError("langfuse down")


class _RaisingLangfuse:
    @contextlib.contextmanager
    def start_as_current_observation(self, **_: Any) -> Iterator[_RaisingSpan]:
        yield _RaisingSpan()


def test_langfuse_tracer_swallows_recording_failures(recorded_attrs: dict[str, Any]) -> None:
    # set_output/set_error run mid-stream; a Langfuse failure there must not surface.
    with LangfuseTracer(_RaisingLangfuse()).trace_chat(user_id="u", session_id="s") as trace:
        trace.set_output("still streaming")
        trace.set_error("still streaming")


class _TrackingCM:
    def __init__(self, span: _FakeSpan) -> None:
        self._span = span
        self.exit_exc_types: list[Any] = []

    def __enter__(self) -> _FakeSpan:
        return self._span

    def __exit__(self, *exc: Any) -> Literal[False]:
        self.exit_exc_types.append(exc[0])
        return False


class _TrackingLangfuse:
    def __init__(self) -> None:
        self.cm = _TrackingCM(_FakeSpan())

    def start_as_current_observation(self, **_: Any) -> _TrackingCM:
        return self.cm


def test_langfuse_tracer_propagates_body_errors_and_still_closes_span(
    recorded_attrs: dict[str, Any],
) -> None:
    # An error from the streamed body must reach the caller unchanged (NOT be masked by
    # a "generator didn't stop" RuntimeError), and the span must still be closed.
    langfuse = _TrackingLangfuse()

    with (
        pytest.raises(ValueError, match="boom"),
        LangfuseTracer(langfuse).trace_chat(user_id="u", session_id="s"),
    ):
        raise ValueError("boom")

    assert langfuse.cm.exit_exc_types == [ValueError]


class _FailingAttrCM:
    def __enter__(self) -> None:
        raise RuntimeError("attr setup boom")

    def __exit__(self, *_: Any) -> Literal[False]:
        return False


def test_langfuse_tracer_rolls_back_span_when_attr_setup_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # If the span enters but propagate_attributes' entry fails, the span must be closed
    # (not left "current" in the OTEL context, where it would mis-nest later requests) —
    # and the chat degrades to an untraced no-op.
    monkeypatch.setattr("langfuse.propagate_attributes", lambda **_: _FailingAttrCM())
    langfuse = _TrackingLangfuse()

    with LangfuseTracer(langfuse).trace_chat(user_id="u", session_id="s") as trace:
        trace.set_output("still streaming")  # no-op handle; must not raise

    assert langfuse.cm.exit_exc_types == [None]  # span was entered then rolled back


def test_shutdown_tracing_is_noop_when_tracing_was_never_used(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("assistant.tracing._client_singleton", None)

    shutdown_tracing()  # must not raise / must not import the SDK


def test_shutdown_tracing_flushes_the_client(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Flushable:
        def __init__(self) -> None:
            self.flushes = 0

        def flush(self) -> None:
            self.flushes += 1

    client = _Flushable()
    monkeypatch.setattr("assistant.tracing._client_singleton", client)

    shutdown_tracing()

    assert client.flushes == 1


def _settings(**over: Any) -> Any:
    base = {
        "langfuse_enabled": False,
        "langfuse_public_key": None,
        "langfuse_secret_key": None,
        "langfuse_host": "https://cloud.langfuse.com",
    }
    base.update(over)
    return SimpleNamespace(**base)


def test_build_tracer_is_noop_when_disabled() -> None:
    assert isinstance(
        build_tracer(_settings(langfuse_public_key="pk", langfuse_secret_key="sk")),
        NoOpTracer,
    )


@pytest.mark.parametrize(
    ("public_key", "secret_key"),
    [(None, "sk"), ("pk", None), (None, None)],
)
def test_build_tracer_is_noop_when_keys_missing(
    public_key: str | None, secret_key: str | None
) -> None:
    settings = _settings(
        langfuse_enabled=True, langfuse_public_key=public_key, langfuse_secret_key=secret_key
    )

    assert isinstance(build_tracer(settings), NoOpTracer)


def test_build_tracer_is_langfuse_when_enabled_and_keyed(monkeypatch: pytest.MonkeyPatch) -> None:
    langfuse = _FakeLangfuse()
    monkeypatch.setattr("assistant.tracing._get_langfuse", lambda settings: langfuse)
    settings = _settings(langfuse_enabled=True, langfuse_public_key="pk", langfuse_secret_key="sk")

    tracer = build_tracer(settings)

    assert isinstance(tracer, LangfuseTracer)
