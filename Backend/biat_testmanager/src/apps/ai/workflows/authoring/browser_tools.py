from __future__ import annotations

import asyncio
import os
import re
import threading
import time
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol

from django.conf import settings


class BrowserAuthoringTool(Protocol):
    def start(self) -> None: ...

    def observe(self) -> dict[str, Any]: ...

    def execute(self, action: dict[str, Any], observation: dict[str, Any]) -> dict[str, Any]: ...

    def get_stream_session_id(self) -> str | None: ...

    def close(self) -> None: ...


class PlaywrightMCPError(RuntimeError):
    """Raised when the Playwright MCP browser tool cannot start or execute."""


class PlaywrightMCPClient:
    """Synchronous wrapper around the official Playwright MCP server over stdio."""

    def __init__(
        self,
        *,
        command: str,
        args: list[str],
        env: dict[str, str] | None = None,
        start_timeout_seconds: int = 30,
        call_timeout_seconds: int = 30,
    ) -> None:
        self.command = command
        self.args = args
        self.env = env
        self.start_timeout_seconds = start_timeout_seconds
        self.call_timeout_seconds = call_timeout_seconds
        self.tool_schemas: dict[str, dict[str, Any]] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._startup_error: BaseException | None = None
        self._exit_stack: AsyncExitStack | None = None
        self._session: Any = None

    def start(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="biat-playwright-mcp",
            daemon=True,
        )
        self._thread.start()

        if not self._ready.wait(self.start_timeout_seconds):
            self.close()
            raise PlaywrightMCPError("Timed out while starting Playwright MCP server.")

        if self._startup_error is not None:
            raise PlaywrightMCPError(str(self._startup_error)) from self._startup_error

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        if self._loop is None or self._session is None:
            raise PlaywrightMCPError("Playwright MCP session is not started.")

        future = asyncio.run_coroutine_threadsafe(
            self._session.call_tool(name, arguments or {}),
            self._loop,
        )
        return future.result(timeout=self.call_timeout_seconds)

    def close(self) -> None:
        if self._loop is not None and self._exit_stack is not None:
            future = asyncio.run_coroutine_threadsafe(self._exit_stack.aclose(), self._loop)
            try:
                future.result(timeout=10)
            except Exception:
                pass

        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._loop.stop)

        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=10)

        if self._loop is not None:
            self._loop.close()

        self._loop = None
        self._thread = None
        self._exit_stack = None
        self._session = None

    def _run_loop(self) -> None:
        assert self._loop is not None
        asyncio.set_event_loop(self._loop)
        self._loop.create_task(self._async_start())
        self._loop.run_forever()

    async def _async_start(self) -> None:
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client

            self._exit_stack = AsyncExitStack()

            server_params = StdioServerParameters(
                command=self.command,
                args=self.args,
                env=self.env,
            )

            # Important for Celery:
            # Celery may replace sys.stderr with a LoggingProxy object.
            # LoggingProxy does not implement fileno(), but subprocess/MCP stdio
            # startup may require a real file descriptor for stderr logging.
            # Therefore we explicitly pass a real file handle as errlog.
            errlog = self._open_mcp_errlog()
            read_stream, write_stream = await self._exit_stack.enter_async_context(
                stdio_client(server_params, errlog=errlog)
            )

            self._session = await self._exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )

            await self._session.initialize()

            tools_result = await self._session.list_tools()
            self.tool_schemas = {
                tool.name: _tool_input_schema(tool)
                for tool in getattr(tools_result, "tools", [])
            }

        except BaseException as exc:
            self._startup_error = exc

        finally:
            self._ready.set()

    def _open_mcp_errlog(self):
        log_path = getattr(settings, "AI_PLAYWRIGHT_MCP_LOG_FILE", "")

        if log_path:
            path = Path(log_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            return self._exit_stack.enter_context(
                open(path, "a", encoding="utf-8")
            )

        return self._exit_stack.enter_context(
            open(os.devnull, "w", encoding="utf-8")
        )


@dataclass
class PlaywrightMCPBrowserAuthoringTool:
    """Browser authoring adapter backed by the official Playwright MCP server."""

    browser: str
    command: str | None = None
    args: list[str] | None = None
    env: dict[str, str] | None = None
    client_factory: Callable[..., PlaywrightMCPClient] = PlaywrightMCPClient
    _client: PlaywrightMCPClient | None = field(default=None, init=False)
    _last_snapshot: str = field(default="", init=False)

    def start(self) -> None:
        self._client = self.client_factory(
            command=self.command or settings.AI_PLAYWRIGHT_MCP_COMMAND,
            args=list(self.args or settings.AI_PLAYWRIGHT_MCP_ARGS),
            env=self.env,
            start_timeout_seconds=settings.AI_PLAYWRIGHT_MCP_START_TIMEOUT_SECONDS,
            call_timeout_seconds=settings.AI_PLAYWRIGHT_MCP_CALL_TIMEOUT_SECONDS,
        )

        self._client.start()

        if self.browser and self.browser not in {"chromium", "chrome"}:
            # Playwright MCP decides browser selection at server startup.
            # Keep this explicit so unsupported per-session browser values
            # do not silently pretend to work.
            self._client.close()
            self._client = None
            raise PlaywrightMCPError(
                "Playwright MCP authoring currently starts with the configured MCP browser. "
                "Use chromium/chrome in BIAT until per-browser MCP launch profiles are added."
            )

    def observe(self) -> dict[str, Any]:
        result = self._call_tool("browser_snapshot", {})
        snapshot = _mcp_text(result)
        self._last_snapshot = snapshot

        return {
            "current_url": _extract_snapshot_value(snapshot, "Page URL"),
            "page_title": _extract_snapshot_value(snapshot, "Page Title"),
            "snapshot": snapshot,
            "visible_text_summary": _compact_snapshot_text(snapshot),
            "interactive_elements": _extract_interactive_elements(snapshot),
        }

    def execute(self, action: dict[str, Any], observation: dict[str, Any]) -> dict[str, Any]:
        action_name = action.get("action")
        started = time.monotonic()

        if action_name == "navigate":
            url = action.get("url") or action.get("value")
            if not url:
                raise PlaywrightMCPError("Navigate action requires a url.")

            result = self._call_tool("browser_navigate", {"url": url})
            return _action_result(action_name, url, result, started)

        if action_name == "wait":
            result = self._call_wait(action)
            return _action_result(action_name, action.get("value") or "wait", result, started)

        if action_name == "assert_text":
            expected_text = str(action.get("assertion") or action.get("value") or "").strip()
            if not expected_text:
                raise PlaywrightMCPError("assert_text action requires assertion or value.")

            snapshot = observation.get("snapshot") or self.observe().get("snapshot") or ""
            if expected_text.lower() not in str(snapshot).lower():
                raise AssertionError(f"Expected text not found in snapshot: {expected_text}")

            return _action_result(action_name, expected_text, "Text found in snapshot.", started)

        ref = _resolve_element_ref(action, observation)

        if action_name == "click":
            result = self._call_ref_tool(
                "browser_click",
                ref,
                element=action.get("target") or action.get("element") or action.get("reason"),
            )
            return _action_result(action_name, ref, result, started)

        if action_name == "fill":
            text = action.get("value")
            if text is None:
                raise PlaywrightMCPError("fill action requires value.")

            result = self._call_ref_tool("browser_type", ref, text=str(text))
            return _action_result(action_name, ref, result, started)

        if action_name == "select":
            value = action.get("value")
            if value is None:
                raise PlaywrightMCPError("select action requires value.")

            result = self._call_ref_tool(
                "browser_select_option",
                ref,
                values=[str(value)],
                value=str(value),
            )
            return _action_result(action_name, ref, result, started)

        if action_name == "assert_visible":
            if not _snapshot_contains_ref(observation, ref):
                raise AssertionError(f"Element ref is not visible in snapshot: {ref}")

            return _action_result(action_name, ref, "Element ref found in snapshot.", started)

        raise PlaywrightMCPError(f"Unsupported browser action: {action_name}")

    def get_stream_session_id(self) -> str | None:
        return None

    def close(self) -> None:
        if self._client is None:
            return

        try:
            if "browser_close" in self._client.tool_schemas:
                self._client.call_tool("browser_close", {})
        except Exception:
            pass
        finally:
            self._client.close()
            self._client = None

    def _call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        if self._client is None:
            raise PlaywrightMCPError("Playwright MCP browser tool was not started.")

        return self._client.call_tool(name, arguments)

    def _call_ref_tool(self, tool_name: str, ref: str, **extra: Any) -> Any:
        schema = self._tool_schema(tool_name)
        args = {_ref_argument_name(schema): ref}
        args.update(_filter_tool_args(schema, extra))
        return self._call_tool(tool_name, args)

    def _call_wait(self, action: dict[str, Any]) -> Any:
        text = action.get("assertion") or action.get("value")
        seconds = _parse_wait_seconds(text)
        schema = self._tool_schema("browser_wait_for")

        if text and not str(text).replace(".", "", 1).isdigit():
            args = {"text": str(text)}
        elif "time" in _schema_properties(schema):
            args = {"time": seconds}
        else:
            args = {"time": seconds}

        return self._call_tool("browser_wait_for", args)

    def _tool_schema(self, name: str) -> dict[str, Any]:
        if self._client is None:
            return {}

        return self._client.tool_schemas.get(name, {})


def build_browser_authoring_tool(browser: str) -> BrowserAuthoringTool:
    return PlaywrightMCPBrowserAuthoringTool(browser=browser)


def _tool_input_schema(tool: Any) -> dict[str, Any]:
    schema = getattr(tool, "inputSchema", None) or getattr(tool, "input_schema", None) or {}
    return schema if isinstance(schema, dict) else {}


def _schema_properties(schema: dict[str, Any]) -> dict[str, Any]:
    properties = schema.get("properties") if isinstance(schema, dict) else None
    return properties if isinstance(properties, dict) else {}


def _filter_tool_args(schema: dict[str, Any], values: dict[str, Any]) -> dict[str, Any]:
    properties = _schema_properties(schema)

    if not properties:
        return {key: value for key, value in values.items() if value is not None}

    return {
        key: value
        for key, value in values.items()
        if value is not None and key in properties
    }


def _ref_argument_name(schema: dict[str, Any]) -> str:
    properties = _schema_properties(schema)

    if "ref" in properties or "target" not in properties:
        return "ref"

    return "target"


def _resolve_element_ref(action: dict[str, Any], observation: dict[str, Any]) -> str:
    raw_candidates = [
        action.get("element_ref"),
        action.get("ref"),
        action.get("element_id"),
        action.get("selector"),
        action.get("target"),
    ]

    elements = [
        element
        for element in observation.get("interactive_elements", [])
        if isinstance(element, dict)
    ]

    refs = {
        str(element.get("ref") or element.get("id")): element
        for element in elements
        if element.get("ref") or element.get("id")
    }

    for candidate in raw_candidates:
        if not candidate:
            continue

        candidate_text = str(candidate).strip()
        if candidate_text in refs:
            return candidate_text

    normalized_candidates = [
        _normalize_ref_lookup(str(candidate))
        for candidate in raw_candidates
        if candidate
    ]

    for element in elements:
        haystack = _normalize_ref_lookup(
            " ".join(
                str(element.get(key) or "")
                for key in ("name", "role", "line", "selector", "id", "ref")
            )
        )

        if any(candidate and candidate in haystack for candidate in normalized_candidates):
            return str(element.get("ref") or element.get("id"))

    raise PlaywrightMCPError("Browser action requires an element_ref from the latest MCP snapshot.")


def _normalize_ref_lookup(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _snapshot_contains_ref(observation: dict[str, Any], ref: str) -> bool:
    return ref in {
        str(element.get("ref") or element.get("id"))
        for element in observation.get("interactive_elements", [])
        if isinstance(element, dict)
    }


def _mcp_text(result: Any) -> str:
    if isinstance(result, str):
        return result

    if isinstance(result, dict):
        content = result.get("content", [])
    else:
        content = getattr(result, "content", [])

    chunks: list[str] = []

    for item in content or []:
        if isinstance(item, dict):
            text = item.get("text")
        else:
            text = getattr(item, "text", None)

        if text:
            chunks.append(str(text))

    if chunks:
        return "\n".join(chunks)

    return str(result or "")


def _extract_interactive_elements(snapshot: str) -> list[dict[str, str]]:
    elements: list[dict[str, str]] = []

    for line in snapshot.splitlines():
        ref_match = re.search(r"\[ref=([^\]]+)\]", line)
        if not ref_match:
            continue

        stripped = line.strip()
        role_match = re.match(r"-\s*([a-zA-Z_ -]+)", stripped)
        name_match = re.search(r'"([^"]+)"', stripped)
        ref = ref_match.group(1)

        elements.append(
            {
                "id": ref,
                "ref": ref,
                "role": (role_match.group(1).strip() if role_match else ""),
                "name": (name_match.group(1).strip() if name_match else ""),
                "line": stripped,
            }
        )

    return elements[:80]


def _extract_snapshot_value(snapshot: str, label: str) -> str:
    pattern = re.compile(rf"{re.escape(label)}:\s*(.+)", re.IGNORECASE)

    for line in snapshot.splitlines():
        match = pattern.search(line)
        if match:
            return match.group(1).strip()

    return ""


def _compact_snapshot_text(snapshot: str) -> str:
    return "\n".join(line.strip() for line in snapshot.splitlines() if line.strip())[:4000]


def _parse_wait_seconds(value: Any) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = 1.0

    return min(max(parsed, 0.1), 5.0)


def _action_result(action_name: str, target: Any, result: Any, started: float) -> dict[str, Any]:
    return {
        "status": "passed",
        "action": action_name,
        "target": str(target or ""),
        "mcp_result": _mcp_text(result)[:4000],
        "duration_ms": int((time.monotonic() - started) * 1000),
    }
