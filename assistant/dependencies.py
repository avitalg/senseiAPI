"""Wiring for the assistant endpoint: build the service (with tools) from settings.

The ``openai`` SDK is imported lazily so it is only needed when a chat request is
actually served (mirroring ``summaries/dependencies.py``).
"""

from typing import Any

import httpx
from fastapi import Depends, Header, HTTPException, status

from assistant.client import OpenAIAssistant
from assistant.service import AssistantService
from assistant.tools import Tools
from assistant.tracing import LangfuseTracer, build_tracer
from core.config import Settings, get_settings


async def _httpx_get(
    url: str, *, headers: dict[str, str], params: dict[str, str] | None = None
) -> tuple[int, Any]:
    """Perform one GET for the assistant's tools (the injected production fetcher)."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url, headers=headers, params=params or None)
    try:
        return response.status_code, response.json()
    except ValueError:
        return response.status_code, response.text


def get_assistant_service(
    settings: Settings = Depends(get_settings),
    authorization: str | None = Header(default=None),
) -> AssistantService:
    """Build the assistant service, or fail clearly if it is unavailable."""
    if not settings.assistant_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="the assistant is disabled",
        )
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="the assistant is not configured (missing OPENAI_API_KEY)",
        )

    # Build the tracer first: constructing it initialises the Langfuse client that the
    # OpenAI drop-in below reuses to nest each model round under the request's trace.
    tracer = build_tracer(settings)

    # Imported lazily so the SDK is only required when the assistant is actually used.
    # With tracing on, use Langfuse's drop-in AsyncOpenAI, which auto-traces every
    # chat completion (model, tokens, cost, latency, errors) — otherwise the plain SDK.
    if isinstance(tracer, LangfuseTracer):
        from langfuse.openai import AsyncOpenAI  # type: ignore[attr-defined]
    else:
        from openai import AsyncOpenAI

    # Tools call back into this API's PHI-safe context surface, forwarding the
    # caller's bearer token so the self-request is authenticated.
    tools = Tools(
        base_url=settings.assistant_self_base_url,
        fetch=_httpx_get,
        auth_header=authorization,
        allow_all_gets=settings.assistant_allow_all_gets,
    )
    client = OpenAIAssistant(
        client=AsyncOpenAI(api_key=settings.openai_api_key),
        model=settings.openai_model,
        tools=tools,
        max_output_tokens=settings.assistant_max_output_tokens,
    )
    return AssistantService(
        client=client,
        max_input_tokens=settings.assistant_max_total_input_tokens,
        tracer=tracer,
    )


__all__ = ["get_assistant_service"]
