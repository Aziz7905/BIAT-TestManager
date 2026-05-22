from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BlockerDetection:
    blocked: bool
    blocker_type: str = ""
    message: str = ""
    evidence: tuple[str, ...] = ()


_BLOCKER_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "captcha",
        (
            "captcha",
            "recaptcha",
            "hcaptcha",
            "turnstile",
            "i'm not a robot",
            "i am not a robot",
        ),
    ),
    (
        "mfa",
        (
            "multi-factor",
            "multifactor",
            "two-factor",
            "2fa",
            "one-time password",
            "one time password",
            "otp",
            "authentication code",
            "verification code",
        ),
    ),
    (
        "security_check",
        (
            "cloudflare",
            "verify you are human",
            "checking your browser",
            "security check",
            "human verification",
            "access denied",
        ),
    ),
)


def detect_blocker(observation: dict[str, Any] | None) -> BlockerDetection:
    observation = observation or {}
    haystack = _observation_text(observation)
    for blocker_type, patterns in _BLOCKER_PATTERNS:
        evidence = tuple(pattern for pattern in patterns if pattern in haystack)
        if evidence:
            return BlockerDetection(
                blocked=True,
                blocker_type=blocker_type,
                message=(
                    "Human action is required before AI authoring can continue "
                    f"({blocker_type.replace('_', ' ')} detected)."
                ),
                evidence=evidence,
            )
    return BlockerDetection(blocked=False)


def _observation_text(observation: dict[str, Any]) -> str:
    parts = [
        observation.get("current_url") or "",
        observation.get("page_title") or "",
        observation.get("snapshot") or "",
        observation.get("visible_text_summary") or "",
    ]
    for element in observation.get("interactive_elements") or []:
        if isinstance(element, dict):
            parts.extend(
                [
                    str(element.get("role") or ""),
                    str(element.get("name") or ""),
                    str(element.get("line") or ""),
                ]
            )
    return " ".join(parts).lower()

