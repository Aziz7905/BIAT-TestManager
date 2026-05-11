from __future__ import annotations

from typing import Any

from .base import BaseLLMProvider, ChatResponse, LLMProviderResponseError, post_json


class OpenAICompatibleProvider(BaseLLMProvider):
    def __init__(
        self,
        *,
        name: str,
        api_key: str,
        model_name: str,
        base_url: str,
        temperature: float,
        max_tokens: int,
        token_parameter: str = "max_tokens",
    ) -> None:
        self.name = name
        self.api_key = api_key
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.token_parameter = token_parameter

    def chat(self, messages: list[dict[str, str]], **opts: Any) -> ChatResponse:
        max_tokens = int(opts.get("max_tokens") or self.max_tokens)
        payload: dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "temperature": float(opts.get("temperature", self.temperature)),
            self.token_parameter: max_tokens,
        }
        response_format = opts.get("response_format")
        if response_format:
            payload["response_format"] = response_format

        raw = post_json(
            url=f"{self.base_url}/chat/completions",
            payload=payload,
            headers={"Authorization": f"Bearer {self.api_key}"},
        )
        try:
            choice = raw["choices"][0]
            content = choice["message"].get("content") or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMProviderResponseError(
                "OpenAI-compatible provider returned an unexpected response."
            ) from exc

        usage = raw.get("usage") or {}
        return ChatResponse(
            content=content,
            input_tokens=int(usage.get("prompt_tokens") or 0),
            output_tokens=int(usage.get("completion_tokens") or 0),
            finish_reason=choice.get("finish_reason") or "",
            raw=raw,
        )
