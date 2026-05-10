from __future__ import annotations

import time
from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse

import requests
from django.conf import settings


@dataclass(frozen=True)
class BrowserSessionHandle:
    session_id: str
    browser_ws_url: str | None = None


def get_webdriver_url(*, for_runner: bool = False) -> str:
    if for_runner:
        return getattr(settings, "SELENOID_RUNNER_HUB_URL", "")
    return getattr(settings, "SELENOID_HUB_URL", "")


def cache_browser_session_urls(execution_id: str, session_id: str) -> BrowserSessionHandle:
    browser_ws_url = get_browser_ws_url_by_ids(str(execution_id), session_id)
    if browser_ws_url:
        _cache_browser_ws_url(str(execution_id), browser_ws_url)
    return BrowserSessionHandle(
        session_id=session_id,
        browser_ws_url=browser_ws_url,
    )


def get_browser_ws_url(execution) -> str | None:
    session_id = getattr(execution, "selenium_session_id", "")
    if not session_id:
        return None
    return get_browser_ws_url_by_ids(str(execution.id), session_id)


def get_browser_ws_url_by_ids(execution_id: str, session_id: str) -> str | None:
    cached = _get_cached_browser_ws_url(execution_id)
    if cached:
        return cached
    return build_selenoid_vnc_websocket_url(
        getattr(settings, "SELENOID_PUBLIC_URL", "") or get_webdriver_url(),
        session_id,
    )


def resize_browser_window(
    session_id: str,
    *,
    width: int = 1920,
    height: int = 1080,
    hub_url: str | None = None,
) -> bool:
    hub_url = (hub_url or get_webdriver_url()).rstrip("/")
    if not hub_url or not session_id:
        return False

    root_url = _webdriver_root_url(hub_url)
    endpoints = [
        (f"{root_url}/session/{session_id}/window/maximize", {}),
        (
            f"{root_url}/session/{session_id}/window/rect",
            {"x": 0, "y": 0, "width": int(width), "height": int(height)},
        ),
    ]
    for attempt in range(3):
        for url, payload in endpoints:
            try:
                response = requests.post(url, json=payload, timeout=5)
                if response.status_code < 400:
                    return True
            except Exception:
                continue
        if attempt < 2:
            time.sleep(0.25)
    return False


def build_selenoid_vnc_websocket_url(base_url: str, session_id: str) -> str | None:
    if not base_url or not session_id:
        return None
    parsed = urlparse(base_url.rstrip("/"))
    scheme = "wss" if parsed.scheme == "https" else "ws"
    return urlunparse((scheme, parsed.netloc, f"/vnc/{session_id}", "", "", ""))


def _webdriver_root_url(hub_url: str) -> str:
    return hub_url.removesuffix("/wd/hub").rstrip("/")


def _get_cached_browser_ws_url(execution_id: str) -> str | None:
    try:
        import redis as redis_lib

        client = redis_lib.from_url(
            getattr(settings, "REDIS_URL", "redis://localhost:6379/0"),
            decode_responses=True,
        )
        return client.get(f"biat:exec:{execution_id}:browser_ws_url")
    except Exception:
        return None


def _cache_browser_ws_url(execution_id: str, browser_ws_url: str) -> None:
    try:
        import redis as redis_lib

        client = redis_lib.from_url(
            getattr(settings, "REDIS_URL", "redis://localhost:6379/0"),
            decode_responses=True,
        )
        client.set(f"biat:exec:{execution_id}:browser_ws_url", browser_ws_url, ex=14400)
    except Exception:
        pass
