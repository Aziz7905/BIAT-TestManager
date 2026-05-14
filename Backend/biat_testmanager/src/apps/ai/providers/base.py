from __future__ import annotations
import httpx
import json
import re
import time
from dataclasses import dataclass
from typing import Any, Protocol


class LLMProviderError(Exception):
    """Base exception for provider configuration and request failures."""


class LLMProviderNotConfiguredError(LLMProviderError):
    """Raised when a team has no usable AI provider configuration."""


class LLMProviderRequestError(LLMProviderError):
    """Raised when an upstream provider rejects or fails a request."""


class LLMProviderResponseError(LLMProviderError):
    """Raised when a provider returns an unexpected response shape."""


@dataclass
class ChatResponse:
    content: str
    input_tokens: int
    output_tokens: int
    finish_reason: str
    raw: dict[str, Any]


class LLMProvider(Protocol):
    name: str
    model_name: str

    def chat(self, messages: list[dict[str, str]], **opts: Any) -> ChatResponse:
        ...

    def chat_json(
        self,
        messages: list[dict[str, str]],
        schema: dict[str, Any],
        **opts: Any,
    ) -> dict[str, Any]:
        ...


def post_json(
    *,
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    timeout_seconds: int = 90,
    max_retries: int = 0,
) -> dict[str, Any]:
    request_headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "BIAT-TestManager/1.0",
        **headers,
    }

    attempts = max(0, max_retries) + 1
    response = None
    for attempt in range(attempts):
        try:
            with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
                response = client.post(
                    url,
                    json=payload,
                    headers=request_headers,
                )

            if response.status_code == 429 and attempt < attempts - 1:
                time.sleep(_retry_delay_seconds(response))
                continue

            if response.status_code >= 400:
                raise LLMProviderRequestError(
                    f"Provider request failed with HTTP {response.status_code}: "
                    f"{response.text[:1000]}"
                )
            break

        except httpx.TimeoutException as exc:
            raise LLMProviderRequestError("Provider request timed out.") from exc

        except httpx.RequestError as exc:
            raise LLMProviderRequestError(f"Provider request failed: {exc}") from exc

    if response is None:
        raise LLMProviderRequestError("Provider request failed before receiving a response.")

    try:
        return response.json()

    except ValueError as exc:
        raise LLMProviderResponseError("Provider returned non-JSON response.") from exc


def _retry_delay_seconds(response: httpx.Response) -> float:
    retry_after = response.headers.get("retry-after")
    if retry_after:
        try:
            return max(0.0, float(retry_after) + 1.0)
        except ValueError:
            pass

    match = re.search(r"try again in\s+([0-9]+(?:\.[0-9]+)?)s", response.text, re.IGNORECASE)
    if match:
        return float(match.group(1)) + 1.0
    return 1.0


def parse_json_content(content: str) -> dict[str, Any]:
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        start = content.find("{")
        end = content.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise LLMProviderResponseError("Provider did not return a JSON object.")
        try:
            parsed = json.loads(content[start : end + 1])
        except json.JSONDecodeError as exc:
            raise LLMProviderResponseError("Provider returned invalid JSON.") from exc

    if not isinstance(parsed, dict):
        raise LLMProviderResponseError("Provider JSON response must be an object.")
    return parsed


class BaseLLMProvider:
    name: str
    model_name: str

    def chat(self, messages: list[dict[str, str]], **opts: Any) -> ChatResponse:
        raise NotImplementedError

    def chat_json(
        self,
        messages: list[dict[str, str]],
        schema: dict[str, Any],
        **opts: Any,
    ) -> dict[str, Any]:
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
        response = self.chat(
            json_messages,
            response_format={"type": "json_object"},
            **opts,
        )
        return parse_json_content(response.content)
