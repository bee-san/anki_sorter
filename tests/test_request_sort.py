from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.request_sort import load_last_success, profile_name_from_health, save_last_success


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


if __name__ == "__main__":
    unittest.main()
