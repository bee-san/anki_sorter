from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import request_sort
from scripts.request_sort import (
    build_sort_request_body,
    load_last_success,
    parse_args,
    profile_name_from_health,
    save_last_success,
)


class RequestSortStateTests(unittest.TestCase):
    def test_profile_name_defaults_to_unknown(self) -> None:
        self.assertEqual(profile_name_from_health({}), "__unknown__")
        self.assertEqual(profile_name_from_health({"profile": "  "}), "__unknown__")
        self.assertEqual(profile_name_from_health({"profile": "Main"}), "Main")

    def test_last_success_is_tracked_per_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = Path(temp_dir) / "requester_state.json"
            save_last_success(state_path, "Profile A", "2026-05-03")
            save_last_success(state_path, "Profile B", "2026-05-04")

            self.assertEqual(
                load_last_success(state_path, "Profile A"),
                "2026-05-03",
            )
            self.assertEqual(
                load_last_success(state_path, "Profile B"),
                "2026-05-04",
            )
            self.assertIsNone(load_last_success(state_path, "Missing"))

            payload = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(
            payload,
            {
                "profiles": {
                    "Profile A": {"lastSuccessYmd": "2026-05-03"},
                    "Profile B": {"lastSuccessYmd": "2026-05-04"},
                }
            },
        )

    def test_api_sort_request_body_acknowledges_sync_risk_only_with_explicit_flag(self) -> None:
        self.assertEqual(build_sort_request_body(assume_all_devices_synced=False), {})
        self.assertEqual(
            build_sort_request_body(assume_all_devices_synced=True),
            {"acknowledgedAllDevicesSynced": True},
        )

    def test_force_alone_does_not_acknowledge_sync_risk(self) -> None:
        original_argv = sys.argv
        try:
            sys.argv = ["request_sort.py", "--force"]
            args = parse_args()
        finally:
            sys.argv = original_argv

        self.assertTrue(args.force)
        self.assertFalse(args.assume_all_devices_synced)
        self.assertEqual(build_sort_request_body(args.assume_all_devices_synced), {})

    def test_safety_skip_does_not_save_last_success(self) -> None:
        calls: list[tuple[str, object]] = []

        def fake_request_json(url: str, method: str = "GET", body: dict[str, object] | None = None) -> dict[str, object]:
            calls.append((url, body))
            if url.endswith("/health"):
                return {"ready": True, "profile": "Main"}
            return {
                "summary": {
                    "skippedForSyncSafety": True,
                    "skipReason": "manual/API sort request requires acknowledgement",
                }
            }

        def fail_save(*_args: object) -> None:
            raise AssertionError("save_last_success should not be called for safety skips")

        original_request_json = request_sort.request_json
        original_save_last_success = request_sort.save_last_success
        original_argv = sys.argv
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                request_sort.request_json = fake_request_json
                request_sort.save_last_success = fail_save
                sys.argv = ["request_sort.py", "--state-dir", temp_dir, "--force"]

                with contextlib.redirect_stdout(io.StringIO()):
                    exit_code = request_sort.main()
            finally:
                request_sort.request_json = original_request_json
                request_sort.save_last_success = original_save_last_success
                sys.argv = original_argv

        self.assertEqual(exit_code, 0)
        self.assertEqual(calls[-1][1], {})


if __name__ == "__main__":
    unittest.main()
