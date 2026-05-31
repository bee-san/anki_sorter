from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "addon"))

from anki_sorter.config import (
    AUTO_SORT_MODE_AFTER_SYNC,
    SYNC_SAFETY_MODE_DESKTOP_ONLY_ALLOW_AUTO,
    parse_config,
)
from anki_sorter.safety import (
    SORT_TRIGGER_AFTER_SYNC,
    SORT_TRIGGER_API,
    SORT_TRIGGER_MANUAL,
    decide_sort_safety,
)


class SafetyTests(unittest.TestCase):
    def test_mobile_guarded_blocks_after_sync_by_default(self) -> None:
        config = parse_config({"autoSortMode": AUTO_SORT_MODE_AFTER_SYNC})

        decision = decide_sort_safety(config, SORT_TRIGGER_AFTER_SYNC)

        self.assertFalse(decision.allowed)
        self.assertIn("mobile_guarded", decision.reason)

    def test_acknowledged_manual_sort_is_allowed(self) -> None:
        decision = decide_sort_safety(
            parse_config({}),
            SORT_TRIGGER_MANUAL,
            acknowledged=True,
        )

        self.assertTrue(decision.allowed)

    def test_acknowledged_api_sort_is_allowed(self) -> None:
        decision = decide_sort_safety(
            parse_config({}),
            SORT_TRIGGER_API,
            acknowledged=True,
        )

        self.assertTrue(decision.allowed)

    def test_desktop_only_opt_in_allows_after_sync_automation(self) -> None:
        config = parse_config(
            {
                "autoSortMode": AUTO_SORT_MODE_AFTER_SYNC,
                "syncSafetyMode": SYNC_SAFETY_MODE_DESKTOP_ONLY_ALLOW_AUTO,
            }
        )

        decision = decide_sort_safety(config, SORT_TRIGGER_AFTER_SYNC)

        self.assertTrue(decision.allowed)


if __name__ == "__main__":
    unittest.main()
