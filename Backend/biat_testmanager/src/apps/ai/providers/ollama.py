from __future__ import annotations

import json
from typing import Any

from .base import (
    BaseLLMProvider,
    ChatResponse,
    LLMProviderResponseError,
    parse_json_content,
    post_json,
)


class OllamaProvider(BaseLLMProvider):
    name = "ollama"

    def __init__(
        self,
        *,
        endpoint: str,
        model_name: str,
        temperature: float,
        max_tokens: int,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens

    def chat(self, messages: list[dict[str, str]], **opts: Any) -> ChatResponse:
        payload: dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": float(opts.get("temperature", self.temperature)),
                "num_predict": int(opts.get("max_tokens") or self.max_tokens),
            },
        }
        if opts.get("num_ctx"):
            payload["options"]["num_ctx"] = int(opts["num_ctx"])
        if opts.get("response_format"):
            payload["format"] = "json"

        raw = post_json(
            url=f"{self.endpoint}/api/chat",
            payload=payload,
            headers={},
            timeout_seconds=300,
            max_retries=0,
        )
        try:
            content = raw["message"].get("content") or ""
        except (KeyError, TypeError) as exc:
            raise LLMProviderResponseError("Ollama returned an unexpected response.") from exc

        return ChatResponse(
            content=content,
            input_tokens=int(raw.get("prompt_eval_count") or 0),
            output_tokens=int(raw.get("eval_count") or 0),
            finish_reason=raw.get("done_reason") or "",
            raw=raw,
        )

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
        response = self.chat(json_messages, response_format={"type": "json_object"}, **opts)
        return parse_json_content(response.content)
