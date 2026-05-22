from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SuccessEvaluation:
    satisfied: bool
    evidence: tuple[str, ...] = ()
    reason: str = ""


_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "be",
    "displayed",
    "is",
    "it",
    "loaded",
    "on",
    "page",
    "shown",
    "the",
    "to",
    "user",
    "visible",
    "with",
}

_AUTH_TERMS = ("login", "log in", "signin", "sign in", "authenticate", "authentication")
_POST_AUTH_ACTION_TERMS = (
    "access",
    "add",
    "choose",
    "click",
    "create",
    "delete",
    "edit",
    "filter",
    "find",
    "go",
    "navigate",
    "open",
    "remove",
    "search",
    "select",
    "update",
    "view",
    "visit",
)
_AUTH_CONTEXT_TERMS = {
    "credential",
    "credentials",
    "email",
    "password",
    "success",
    "successful",
    "successfully",
    "username",
    "valid",
}
_POST_AUTH_CONTEXT_TERMS = _AUTH_CONTEXT_TERMS | {
    "from",
    "page",
    "read",
    "them",
    "then",
    "use",
    "uses",
    "using",
}


def evaluate_success(
    *,
    goal: dict[str, Any],
    observation: dict[str, Any] | None,
    trace: list[dict[str, Any]] | None = None,
    success_evidence: list[str] | tuple[str, ...] | None = None,
) -> SuccessEvaluation:
    observation = observation or {}
    trace = trace or []
    goal_text = _goal_text(goal)
    has_post_auth_work = has_post_auth_objective(goal)
    haystack = _observation_text(observation)
    supplied_evidence = [str(item).strip() for item in success_evidence or [] if str(item).strip()]

    if supplied_evidence:
        matched = tuple(item for item in supplied_evidence if _evidence_matches(item, haystack))
        if matched and (
            not has_post_auth_work
            or _evidence_satisfies_post_auth_objective(goal_text, matched)
        ):
            return SuccessEvaluation(
                satisfied=True,
                evidence=matched,
                reason="Supplied finish evidence is visible in the current browser state.",
            )

    auth_success = (
        ()
        if has_post_auth_work
        else _auth_success_signal(goal, observation, haystack)
    )
    if auth_success:
        return SuccessEvaluation(
            satisfied=True,
            evidence=auth_success,
            reason="Authentication objective appears satisfied by current URL/page state.",
        )

    expected = str(goal.get("expected_result") or "").strip()
    expected_terms = _important_terms(expected)
    if expected_terms:
        matched_terms = tuple(term for term in expected_terms if term in haystack)
        if matched_terms and len(matched_terms) >= min(2, len(expected_terms)):
            return SuccessEvaluation(
                satisfied=True,
                evidence=matched_terms,
                reason="Expected result terms are visible in the current browser state.",
            )

    for event in reversed(trace[-5:]):
        action = str(event.get("action") or event.get("tool") or "").lower()
        status = str(event.get("status") or "").lower()
        if status != "passed":
            continue
        if action in {
            "assert_text",
            "assert_visible",
            "assert_value",
            "browser_verify_text_visible",
            "browser_verify_element_visible",
            "browser_verify_value",
        }:
            target = str(event.get("target") or event.get("value") or event.get("text") or "").strip()
            target_terms = _important_terms(target)
            if target and (
                not expected_terms
                or any(term in target.lower() for term in expected_terms)
                or any(term in expected for term in target_terms)
            ):
                if has_post_auth_work and not _evidence_satisfies_post_auth_objective(
                    goal_text,
                    (target,),
                ):
                    continue
                return SuccessEvaluation(
                    satisfied=True,
                    evidence=(target,),
                    reason="A recent verification tool passed.",
                )

    return SuccessEvaluation(
        satisfied=False,
        reason="No deterministic success evidence is visible yet.",
    )


def has_post_auth_objective(goal: dict[str, Any]) -> bool:
    return bool(post_auth_objective_terms(goal))


def post_auth_objective_terms(goal: dict[str, Any]) -> tuple[str, ...]:
    goal_text = _goal_text(goal)
    after_auth = _text_after_first_auth_term(goal_text)
    if not after_auth:
        return ()

    has_action = any(term in after_auth for term in _POST_AUTH_ACTION_TERMS)
    if not has_action:
        return ()

    return _post_auth_terms_from_text(after_auth)


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
                    str(element.get("value") or ""),
                    str(element.get("line") or ""),
                ]
            )
    return " ".join(parts).lower()


def _auth_success_signal(
    goal: dict[str, Any],
    observation: dict[str, Any],
    haystack: str,
) -> tuple[str, ...]:
    goal_text = _goal_text(goal)
    if not any(term in goal_text for term in _AUTH_TERMS):
        return ()

    current_url = str(observation.get("current_url") or "").lower()
    positive_terms = (
        "dashboard",
        "home",
        "account",
        "profile",
        "logout",
        "log out",
        "my info",
        "welcome",
    )
    url_terms = tuple(term for term in ("dashboard", "home", "account", "profile") if term in current_url)
    if url_terms:
        return tuple(f"url contains: {term}" for term in url_terms[:3])

    if any(term in haystack for term in positive_terms):
        return tuple(term for term in positive_terms if term in haystack)[:3]

    leaving_login_page = current_url and not any(
        term in current_url for term in ("login", "signin", "sign-in", "auth/login")
    )
    if leaving_login_page and any(term in current_url for term in ("dashboard", "home", "account")):
        return (current_url,)

    return ()


def _goal_text(goal: dict[str, Any]) -> str:
    steps = goal.get("steps") if isinstance(goal.get("steps"), list) else []
    step_text = " ".join(
        str(step.get(key) or "")
        for step in steps
        if isinstance(step, dict)
        for key in ("action", "step", "description", "expected", "expected_outcome")
    )
    return " ".join(
        str(part or "")
        for part in (
            goal.get("title"),
            goal.get("preconditions"),
            goal.get("expected_result"),
            step_text,
        )
    ).lower()


def _text_after_first_auth_term(goal_text: str) -> str:
    matches = [
        match
        for term in _AUTH_TERMS
        for match in [re.search(rf"\b{re.escape(term)}\b", goal_text)]
        if match
    ]
    if not matches:
        return ""
    first = min(matches, key=lambda match: match.start())
    return goal_text[first.end() :]


def _evidence_satisfies_post_auth_objective(
    goal_text: str,
    evidence_items: tuple[str, ...],
) -> bool:
    evidence_text = " ".join(str(item or "").lower() for item in evidence_items)
    terms = list(_post_auth_terms_from_text(_text_after_first_auth_term(goal_text)))
    if not terms:
        return False
    matched_terms = [term for term in terms if term in evidence_text]
    return len(matched_terms) >= min(2, len(terms))


def _post_auth_terms_from_text(text: str) -> tuple[str, ...]:
    words = re.findall(r"[a-zA-Z0-9][a-zA-Z0-9_-]+", text.lower())
    terms = []
    ignored_stopwords = _STOPWORDS - {"user"}
    for word in words:
        if len(word) < 3:
            continue
        if (
            word in ignored_stopwords
            or word in _POST_AUTH_CONTEXT_TERMS
            or word in _POST_AUTH_ACTION_TERMS
        ):
            continue
        if word not in terms:
            terms.append(word)
    return tuple(terms[:6])


def _important_terms(text: str) -> tuple[str, ...]:
    words = re.findall(r"[a-zA-Z0-9][a-zA-Z0-9_-]+", text.lower())
    terms = []
    for word in words:
        if word in _STOPWORDS or len(word) < 3:
            continue
        if word not in terms:
            terms.append(word)
    return tuple(terms[:8])


def _evidence_matches(evidence: str, haystack: str) -> bool:
    evidence_text = evidence.lower()
    if evidence_text in haystack:
        return True
    terms = _important_terms(evidence_text)
    return bool(terms) and all(term in haystack for term in terms[:3])
