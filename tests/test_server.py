from __future__ import annotations

import http.client
import importlib
import json
import sys
import threading
import types
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "addon"))


class ServerRequestTests(unittest.TestCase):
    def setUp(self) -> None:
        package = types.ModuleType("anki_sorter")
        package.__path__ = [str(ROOT / "addon" / "anki_sorter")]  # type: ignore[attr-defined]
        sys.modules["anki_sorter"] = package

        aqt = types.ModuleType("aqt")
        setattr(aqt, "gui_hooks", types.SimpleNamespace(profile_did_open=[]))
        setattr(aqt, "mw", types.SimpleNamespace())
        sys.modules["aqt"] = aqt

        utils = types.ModuleType("aqt.utils")
        setattr(utils, "showWarning", lambda *args, **kwargs: None)
        sys.modules["aqt.utils"] = utils

        sys.modules.pop("anki_sorter.server", None)
        self.server_module = importlib.import_module("anki_sorter.server")

    def tearDown(self) -> None:
        if hasattr(self, "server"):
            self.server.shutdown()
            self.server.server_close()
        if hasattr(self, "thread"):
            self.thread.join(timeout=1.0)

    def start_server(self, manager: Any) -> int:
        self.server = self.server_module.SorterHTTPServer(manager, 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return int(self.server.server_address[1])

    def post_sort(self, port: int, body: bytes) -> tuple[int, dict[str, Any]]:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        try:
            conn.request(
                "POST",
                "/sort",
                body=body,
                headers={"Content-Type": "application/json"},
            )
            response = conn.getresponse()
            payload = json.loads(response.read().decode("utf-8"))
            return int(response.status), payload
        finally:
            conn.close()

    def test_sort_requires_explicit_all_devices_synced_acknowledgement(self) -> None:
        acknowledgements: list[bool] = []

        class Manager:
            def run_sort(self, acknowledged: bool = False) -> dict[str, Any]:
                acknowledgements.append(acknowledged)
                return {"summary": {"acknowledged": acknowledged}}

        port = self.start_server(Manager())

        status, payload = self.post_sort(port, b'{"acknowledgedAllDevicesSynced": true}')

        self.assertEqual(status, 200)
        self.assertEqual(payload["summary"], {"acknowledged": True})
        self.assertEqual(acknowledgements, [True])

    def test_sort_does_not_treat_legacy_acknowledged_field_as_confirmation(self) -> None:
        acknowledgements: list[bool] = []

        class Manager:
            def run_sort(self, acknowledged: bool = False) -> dict[str, Any]:
                acknowledgements.append(acknowledged)
                return {"summary": {"acknowledged": acknowledged}}

        port = self.start_server(Manager())

        status, payload = self.post_sort(port, b'{"acknowledged": true}')

        self.assertEqual(status, 200)
        self.assertEqual(payload["summary"], {"acknowledged": False})
        self.assertEqual(acknowledgements, [False])

    def test_invalid_sort_json_returns_clean_400(self) -> None:
        class Manager:
            def run_sort(self, acknowledged: bool = False) -> dict[str, Any]:
                raise AssertionError("run_sort should not be called for invalid JSON")

        port = self.start_server(Manager())

        status, payload = self.post_sort(port, b'{not valid json')

        self.assertEqual(status, 400)
        self.assertFalse(payload["ready"])
        self.assertIn("Invalid JSON", payload["error"])


if __name__ == "__main__":
    unittest.main()
