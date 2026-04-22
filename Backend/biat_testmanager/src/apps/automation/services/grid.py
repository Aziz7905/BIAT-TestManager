from __future__ import annotations

import os
import time
from urllib.parse import urlencode, urlparse, urlunparse

import requests
from django.conf import settings


def get_grid_session_info(session_id: str) -> dict:
    hub_url = getattr(settings, "SELENIUM_GRID_HUB_URL", "")
    if not hub_url or not session_id:
        return {}
    hub_url = hub_url.rstrip("/")
    try:
        response = requests.get(
            f"{hub_url}/se/grid/api/session/{session_id}",
            timeout=5,
        )
        if response.status_code == 200:
            return response.json().get("value", {})
    except Exception:
        pass

    try:
        response = requests.get(f"{hub_url}/status", timeout=5)
        if response.status_code != 200:
            return {}
        nodes = response.json().get("value", {}).get("nodes", [])
        for node in nodes:
            for slot in node.get("slots", []):
                session = slot.get("session") or {}
                if session.get("sessionId") == session_id:
                    return {
                        **session,
                        "nodeUri": session.get("uri") or node.get("uri", ""),
                    }
    except Exception:
        pass
    return {}


def get_session_vnc_websocket_url(
    session_id: str,
    *,
    attempts: int = 1,
    delay_seconds: float = 0,
) -> str | None:
    hub_url = getattr(settings, "SELENIUM_GRID_HUB_URL", "").rstrip("/")
    if not hub_url:
        return None

    for attempt in range(max(attempts, 1)):
        info = get_grid_session_info(session_id)
        capabilities = info.get("capabilities") or {}
        raw_vnc_url = capabilities.get("se:vnc")
        if raw_vnc_url:
            hub = urlparse(hub_url)
            vnc = urlparse(raw_vnc_url)
            scheme = "wss" if hub.scheme == "https" else "ws"
            return urlunparse((scheme, hub.netloc, vnc.path, "", vnc.query, ""))

        if info:
            return _build_hub_vnc_websocket_url(session_id)

        if attempt < attempts - 1 and delay_seconds:
            time.sleep(delay_seconds)

    return _build_hub_vnc_websocket_url(session_id)


def cache_browser_session_urls(execution_id: str, session_id: str) -> str | None:
    browser_ws_url = get_session_vnc_websocket_url(
        session_id,
        attempts=5,
        delay_seconds=0.2,
    )
    vnc_url = get_node_vnc_url_for_session(session_id)
    if not browser_ws_url and not vnc_url:
        return None

    try:
        import redis as redis_lib

        client = redis_lib.from_url(
            getattr(settings, "REDIS_URL", "redis://localhost:6379/0"),
            decode_responses=True,
        )
        if vnc_url:
            client.set(f"biat:exec:{execution_id}:vnc_url", vnc_url, ex=14400)
        if browser_ws_url:
            client.set(
                f"biat:exec:{execution_id}:browser_ws_url",
                browser_ws_url,
                ex=14400,
            )
    except Exception:
        pass

    return browser_ws_url


def get_browser_view_urls_for_session(session_id: str) -> list[str]:
    urls: list[str] = []
    resolved_vnc_url = get_node_vnc_url_for_session(session_id)
    if resolved_vnc_url and _is_host_reachable_vnc_url(resolved_vnc_url):
        urls.append(_build_no_vnc_page_url(resolved_vnc_url))

    for candidate in _configured_vnc_urls():
        page_url = _build_no_vnc_page_url(candidate)
        if page_url not in urls:
            urls.append(page_url)
    return urls


def _build_hub_vnc_websocket_url(session_id: str) -> str | None:
    hub_url = getattr(settings, "SELENIUM_GRID_HUB_URL", "").rstrip("/")
    if not hub_url or not session_id:
        return None
    hub = urlparse(hub_url)
    scheme = "wss" if hub.scheme == "https" else "ws"
    return urlunparse(
        (scheme, hub.netloc, f"/session/{session_id}/se/vnc", "", "", "")
    )


def get_node_vnc_url_for_session(session_id: str) -> str | None:
    info = get_grid_session_info(session_id)
    node_uri = info.get("nodeUri", "")
    if not node_uri:
        return None
    return _resolve_vnc_url(node_uri)


def _resolve_vnc_url(node_uri: str) -> str | None:
    parsed = urlparse(node_uri)
    node_host = parsed.hostname
    if not node_host:
        return None

    # Try to find the host-mapped port via Docker SDK (needed on macOS/Windows
    # where container IPs are not reachable from the host).
    mapped_port = _find_mapped_vnc_port(node_host)
    if mapped_port:
        return f"http://localhost:{mapped_port}"

    # Fallback: assume VNC is directly reachable at port 7900 on the same host
    # (works on Linux hosts or when Django runs inside the same Docker network).
    return f"http://{node_host}:7900"


def _configured_vnc_urls() -> list[str]:
    configured = os.environ.get("SELENIUM_VNC_URLS", "")
    if configured:
        return [item.strip().rstrip("/") for item in configured.split(",") if item.strip()]

    hub_url = getattr(settings, "SELENIUM_GRID_HUB_URL", "")
    hub_host = urlparse(hub_url).hostname
    if hub_host in {"localhost", "127.0.0.1"}:
        return [
            "http://localhost:7900",
            "http://localhost:7901",
            "http://localhost:7902",
        ]
    return []


def _is_host_reachable_vnc_url(url: str) -> bool:
    host = urlparse(url).hostname
    return host in {"localhost", "127.0.0.1", "host.docker.internal"}


def _build_no_vnc_page_url(base_url: str) -> str:
    query = urlencode(
        {
            "autoconnect": "1",
            "resize": "scale",
            "password": os.environ.get("SELENIUM_VNC_PASSWORD", "secret"),
        }
    )
    return f"{base_url.rstrip('/')}/?{query}"


def _find_mapped_vnc_port(node_host: str) -> str | None:
    try:
        import docker
    except ImportError:
        return None

    try:
        client = docker.from_env()
        for container in client.containers.list():
            if _container_matches(container, node_host):
                ports = container.attrs.get("NetworkSettings", {}).get("Ports", {})
                bindings = ports.get("7900/tcp")
                if bindings:
                    host_port = bindings[0].get("HostPort")
                    if host_port:
                        return host_port
    except Exception:
        pass
    return None


def _container_matches(container, node_host: str) -> bool:
    if container.name.lstrip("/") == node_host:
        return True

    hostname = container.attrs.get("Config", {}).get("Hostname", "")
    if hostname == node_host:
        return True

    networks = container.attrs.get("NetworkSettings", {}).get("Networks", {})
    for network in networks.values():
        if network.get("IPAddress") == node_host:
            return True

    return False
