from unittest import mock

from django.test import SimpleTestCase, override_settings

from apps.automation.services.browser_sessions import (
    build_selenoid_vnc_websocket_url,
    get_webdriver_url,
    get_browser_ws_url_by_ids,
)
from apps.automation.consumers import _browser_stream_origin


class BrowserSessionBackendTests(SimpleTestCase):
    @override_settings(
        SELENOID_HUB_URL="http://localhost:4444/wd/hub",
        SELENOID_RUNNER_HUB_URL="http://selenoid:4444/wd/hub",
    )
    def test_selenoid_webdriver_urls_are_separate_for_host_and_runner(self):
        self.assertEqual(get_webdriver_url(), "http://localhost:4444/wd/hub")
        self.assertEqual(
            get_webdriver_url(for_runner=True),
            "http://selenoid:4444/wd/hub",
        )

    @override_settings(
        SELENOID_HUB_URL="http://selenoid:4444/wd/hub",
        SELENOID_PUBLIC_URL="https://selenoid.example.test",
    )
    def test_selenoid_resolves_vnc_websocket_url(self):
        with mock.patch(
            "apps.automation.services.browser_sessions._get_cached_browser_ws_url",
            return_value=None,
        ):
            self.assertEqual(
                get_browser_ws_url_by_ids("exec-1", "session-1"),
                "wss://selenoid.example.test/vnc/session-1",
            )

    def test_selenoid_websocket_url_builder_uses_vnc_session_path(self):
        self.assertEqual(
            build_selenoid_vnc_websocket_url(
                "http://localhost:4444/wd/hub",
                "abc123",
            ),
            "ws://localhost:4444/vnc/abc123",
        )

    @override_settings(SELENOID_PUBLIC_URL="http://localhost:4444/wd/hub")
    def test_browser_stream_origin_strips_webdriver_path(self):
        self.assertEqual(_browser_stream_origin(), "http://localhost:4444")
