from __future__ import annotations

from typing import Any
from urllib.parse import quote

from .base import BaseLLMProvider, ChatResponse, LLMProviderResponseError, post_json


class AzureOpenAIProvider(BaseLLMProvider):
    name = "azure_openai"

    def __init__(
        self,
        *,
        api_key: str,
        endpoint: str,
        api_version: str,
        deployment_name: str,
        temperature: float,
        max_tokens: int,
    ) -> None:
        self.api_key = api_key
        self.endpoint = endpoint.rstrip("/")
        self.api_version = api_version
        self.model_name = deployment_name
        self.temperature = temperature
        self.max_tokens = max_tokens

    def chat(self, messages: list[dict[str, str]], **opts: Any) -> ChatResponse:
        deployment = quote(self.model_name, safe="")
        url = (
            f"{self.endpoint}/openai/deployments/{deployment}/chat/completions"
            f"?api-version={self.api_version}"
        )
        payload: dict[str, Any] = {
            "messages": messages,
            "temperature": float(opts.get("temperature", self.temperature)),
            "max_tokens": int(opts.get("max_tokens") or self.max_tokens),
        }
        response_format = opts.get("response_format")
        if response_format:
            payload["response_format"] = response_format

        raw = post_json(
            url=url,
            payload=payload,
            headers={"api-key": self.api_key},
        )
        try:
            choice = raw["choices"][0]
            content = choice["message"].get("content") or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMProviderResponseError(
                "Azure OpenAI returned an unexpected response."
            ) from exc

        usage = raw.get("usage") or {}
        return ChatResponse(
            content=content,
            input_tokens=int(usage.get("prompt_tokens") or 0),
            output_tokens=int(usage.get("completion_tokens") or 0),
            finish_reason=choice.get("finish_reason") or "",
            raw=raw,
        )
