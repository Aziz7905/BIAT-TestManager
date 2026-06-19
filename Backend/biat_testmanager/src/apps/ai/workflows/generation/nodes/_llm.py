from __future__ import annotations

import json
import time
from typing import Any

from apps.ai.providers.base import (
    ChatResponse,
    LLMProvider,
    LLMProviderResponseError,
    parse_json_content,
)
from apps.ai.workflows.generation.state import LLMJSONResult, TestGenerationState

TOKEN_LIMIT_FINISH_REASONS = frozenset(
    {
        "length",
        "max_tokens",
        "max_token",
        "max_output_tokens",
        "max_tokens_reached",
        "max_tokens_exceeded",
        "MAX_TOKENS",
    }
)
JSON_RETRY_TOKEN_MULTIPLIER = 2


def call_llm_json(
    provider: LLMProvider,
    *,
    messages: list[dict[str, str]],
    schema: dict[str, Any],
    allow_invalid_json: bool = False,
    max_tokens: int | None = None,
    num_ctx: int | None = None,
    retry_max_tokens: int | None = None,
    max_json_retries: int = 1,
) -> LLMJSONResult:
    schema_text = json.dumps(schema, ensure_ascii=True)
    json_messages = [
        {
            "role": "system",
            "content": (
                "Return only one valid JSON object. Do not wrap it in markdown. "
                f"The JSON object must match this schema: {schema_text}"
            ),
        },
        *messages,
    ]
    started = time.monotonic()
    responses: list[ChatResponse] = []
    current_max_tokens = _positive_int(max_tokens)
    retry_ceiling = _positive_int(retry_max_tokens)
    attempts_remaining = max(0, int(max_json_retries or 0))
    active_messages = json_messages

    while True:
        chat_options = _chat_options(max_tokens=current_max_tokens, num_ctx=num_ctx)
        response = provider.chat(active_messages, **chat_options)
        responses.append(response)
        duration_ms = int((time.monotonic() - started) * 1000)
        try:
            payload = parse_json_content(response.content)
            return LLMJSONResult(
                payload=payload,
                response=_merge_responses(responses),
                duration_ms=duration_ms,
            )
        except LLMProviderResponseError as exc:
            next_max_tokens = _next_retry_max_tokens(
                finish_reason=response.finish_reason,
                current_max_tokens=current_max_tokens,
                retry_ceiling=retry_ceiling,
            )
            if attempts_remaining > 0 and next_max_tokens:
                attempts_remaining -= 1
                current_max_tokens = next_max_tokens
                active_messages = _retry_messages(json_messages, exc)
                continue
            if not allow_invalid_json:
                raise
            payload = {"_invalid_json_content": response.content}
            return LLMJSONResult(
                payload=payload,
                response=_merge_responses(responses),
                duration_ms=duration_ms,
            )


def accumulate_usage(state: TestGenerationState, result: LLMJSONResult) -> None:
    state["input_tokens"] = int(state.get("input_tokens") or 0) + result.response.input_tokens
    state["output_tokens"] = int(state.get("output_tokens") or 0) + result.response.output_tokens
    state["duration_ms"] = int(state.get("duration_ms") or 0) + result.duration_ms


def limit_value(state: TestGenerationState, key: str) -> int | None:
    value = state.get("generation_limits", {}).get(key)
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _chat_options(*, max_tokens: int | None, num_ctx: int | None) -> dict[str, Any]:
    chat_options: dict[str, Any] = {"response_format": {"type": "json_object"}}
    if max_tokens:
        chat_options["max_tokens"] = max_tokens
    if num_ctx:
        chat_options["num_ctx"] = num_ctx
    return chat_options


def _next_retry_max_tokens(
    *,
    finish_reason: str,
    current_max_tokens: int | None,
    retry_ceiling: int | None,
) -> int | None:
    if not _is_token_limited_finish(finish_reason):
        return None
    if not current_max_tokens or not retry_ceiling or retry_ceiling <= current_max_tokens:
        return None
    return min(current_max_tokens * JSON_RETRY_TOKEN_MULTIPLIER, retry_ceiling)


def _is_token_limited_finish(finish_reason: str) -> bool:
    normalized = str(finish_reason or "").strip()
    return normalized in TOKEN_LIMIT_FINISH_REASONS or normalized.lower() in TOKEN_LIMIT_FINISH_REASONS


def _retry_messages(
    json_messages: list[dict[str, str]],
    error: Exception,
) -> list[dict[str, str]]:
    return [
        *json_messages,
        {
            "role": "system",
            "content": (
                "The previous response was cut off before valid JSON could be parsed. "
                "Return the complete JSON object only. "
                f"Parser error: {error}"
            ),
        },
    ]


def _merge_responses(responses: list[ChatResponse]) -> ChatResponse:
    if len(responses) == 1:
        return responses[0]
    final_response = responses[-1]
    return ChatResponse(
        content=final_response.content,
        input_tokens=sum(response.input_tokens for response in responses),
        output_tokens=sum(response.output_tokens for response in responses),
        finish_reason=final_response.finish_reason,
        raw={
            "attempt_count": len(responses),
            "final": final_response.raw,
            "attempts": [response.raw for response in responses],
        },
    )


def _positive_int(value: int | None) -> int | None:
    try:
        parsed = int(value) if value is not None else 0
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None
