from __future__ import annotations

from typing import Any

from .base import BaseLLMProvider, ChatResponse, LLMProviderResponseError, post_json


class AnthropicProvider(BaseLLMProvider):
    name = "anthropic"

    def __init__(
        self,
        *,
        api_key: str,
        model_name: str,
        base_url: str,
        temperature: float,
        max_tokens: int,
    ) -> None:
        self.api_key = api_key
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self.temperature = temperature
        self.max_tokens = max_tokens

    def chat(self, messages: list[dict[str, str]], **opts: Any) -> ChatResponse:
        system_parts: list[str] = []
        anthropic_messages: list[dict[str, str]] = []
        for message in messages:
            role = message.get("role")
            content = message.get("content") or ""
            if role == "system":
                system_parts.append(content)
                continue
            anthropic_messages.append(
                {
                    "role": "assistant" if role == "assistant" else "user",
                    "content": content,
                }
            )

        payload: dict[str, Any] = {
            "model": self.model_name,
            "messages": anthropic_messages,
            "temperature": float(opts.get("temperature", self.temperature)),
            "max_tokens": int(opts.get("max_tokens") or self.max_tokens),
        }
        if system_parts:
            payload["system"] = "\n\n".join(system_parts)

        raw = post_json(
            url=f"{self.base_url}/messages",
            payload=payload,
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
            },
        )
        try:
            content_parts = raw.get("content") or []
            text = "".join(
                part.get("text", "")
                for part in content_parts
                if isinstance(part, dict) and part.get("type") == "text"
            )
        except (KeyError, TypeError) as exc:
            raise LLMProviderResponseError("Anthropic returned an unexpected response.") from exc

        usage = raw.get("usage") or {}
        return ChatResponse(
            content=text,
            input_tokens=int(usage.get("input_tokens") or 0),
            output_tokens=int(usage.get("output_tokens") or 0),
            finish_reason=raw.get("stop_reason") or "",
            raw=raw,
        )
