from __future__ import annotations

import logging
from typing import Any

from .base import BaseLLMProvider, ChatResponse, LLMProviderResponseError, post_json

logger = logging.getLogger(__name__)


class GeminiProvider(BaseLLMProvider):
    name = "gemini"

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
        payload = self._build_payload(messages, opts)
        raw = post_json(
            url=f"{self.base_url}/models/{self.model_name}:generateContent",
            payload=payload,
            headers={"x-goog-api-key": self.api_key},
        )
        return self._parse_response(raw, payload["generationConfig"]["maxOutputTokens"])

    def _build_payload(
        self,
        messages: list[dict[str, str]],
        opts: dict[str, Any],
    ) -> dict[str, Any]:
        system_parts, gemini_contents = self._map_messages(messages)

        generation_config: dict[str, Any] = {
            "temperature": float(opts.get("temperature", self.temperature)),
            "maxOutputTokens": int(opts.get("max_tokens") or self.max_tokens),
            # Gemini 2.5 models silently spend maxOutputTokens on internal "thinking"
            # before emitting any visible text. We want structured output, not
            # chain-of-thought, so disable thinking outright.
            "thinkingConfig": {"thinkingBudget": 0},
        }
        response_format = opts.get("response_format") or {}
        if isinstance(response_format, dict) and response_format.get("type") == "json_object":
            generation_config["responseMimeType"] = "application/json"

        payload: dict[str, Any] = {
            "contents": gemini_contents,
            "generationConfig": generation_config,
        }
        if system_parts:
            payload["systemInstruction"] = {
                "parts": [{"text": "\n\n".join(system_parts)}],
            }
        return payload

    @staticmethod
    def _map_messages(
        messages: list[dict[str, str]],
    ) -> tuple[list[str], list[dict[str, Any]]]:
        system_parts: list[str] = []
        gemini_contents: list[dict[str, Any]] = []
        for message in messages:
            role = message.get("role")
            content = message.get("content") or ""
            if role == "system":
                system_parts.append(content)
                continue
            gemini_contents.append(
                {
                    "role": "model" if role == "assistant" else "user",
                    "parts": [{"text": content}],
                }
            )
        return system_parts, gemini_contents

    def _parse_response(
        self,
        raw: dict[str, Any],
        max_output_tokens: int,
    ) -> ChatResponse:
        try:
            candidates = raw.get("candidates") or []
            if not candidates:
                raise LLMProviderResponseError("Gemini returned no candidates.")
            candidate = candidates[0]
            content_parts = candidate.get("content", {}).get("parts") or []
            text = "".join(
                part.get("text", "")
                for part in content_parts
                if isinstance(part, dict)
            )
            finish_reason = candidate.get("finishReason") or ""
        except (KeyError, TypeError, IndexError) as exc:
            raise LLMProviderResponseError("Gemini returned an unexpected response.") from exc

        usage = raw.get("usageMetadata") or {}
        input_tokens = int(usage.get("promptTokenCount") or 0)
        output_tokens = int(usage.get("candidatesTokenCount") or 0)

        logger.info(
            "Gemini call: model=%s finish=%s in=%d out=%d max_out=%d text_chars=%d",
            self.model_name,
            finish_reason or "unknown",
            input_tokens,
            output_tokens,
            max_output_tokens,
            len(text),
        )

        if not text:
            raise LLMProviderResponseError(
                f"Gemini returned no text content. finishReason={finish_reason or 'unknown'}."
            )

        return ChatResponse(
            content=text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            finish_reason=finish_reason,
            raw=raw,
        )
