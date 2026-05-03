from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "addon"))

from anki_vn_sorter.config import (
    AUTO_SORT_MODE_AFTER_SYNC,
    AUTO_SORT_MODE_PROFILE_OPEN,
    AddonConfig,
    DEFAULT_TIER_ORDER,
    TIER_ALL_KANJI_KNOWN,
    TIER_KANA_ONLY,
    build_default_mature_query,
    parse_config,
)


class ConfigTests(unittest.TestCase):
    def test_blank_mature_query_uses_mature_days(self) -> None:
        config = parse_config(
            {
                "modelNames": ["Kiku"],
                "matureQuery": "",
                "matureDays": 30,
            }
        )
        self.assertEqual(
            config.effective_mature_query,
            '(note:"Kiku") prop:ivl>=30 -is:suspended',
        )

    def test_legacy_default_mature_query_falls_back_to_generated_query(self) -> None:
        config = parse_config(
            {
                "modelNames": ["Kiku"],
                "matureQuery": "note:Kiku prop:ivl>=21 -is:suspended",
                "matureDays": 45,
            }
        )
        self.assertEqual(
            config.effective_mature_query,
            '(note:"Kiku") prop:ivl>=45 -is:suspended',
        )

    def test_custom_settings_round_trip(self) -> None:
        config = parse_config(
            {
                "tierOrder": [
                    TIER_ALL_KANJI_KNOWN,
                    TIER_KANA_ONLY,
                    "one_unknown_kanji",
                    "two_unknown_kanji",
                    "three_plus_unknown_kanji",
                ],
                "preferShorterExpressions": False,
                "freqSortWeight": 0.5,
            }
        )
        self.assertEqual(config.tier_order[:2], (TIER_ALL_KANJI_KNOWN, TIER_KANA_ONLY))
        self.assertFalse(config.prefer_shorter_expressions)
        self.assertEqual(config.freqsort_weight, 0.5)

    def test_build_default_mature_query_handles_multiple_models(self) -> None:
        query = build_default_mature_query(("Kiku", "Kiku Alt"), 21)
        self.assertEqual(
            query,
            '(note:"Kiku" or note:"Kiku Alt") prop:ivl>=21 -is:suspended',
        )

    def test_auto_sort_mode_round_trip(self) -> None:
        config = parse_config(
            {
                "autoSortMode": AUTO_SORT_MODE_PROFILE_OPEN,
            }
        )
        self.assertEqual(config.auto_sort_mode, AUTO_SORT_MODE_PROFILE_OPEN)

    def test_default_auto_sort_mode_is_after_sync(self) -> None:
        config = parse_config({})
        self.assertEqual(config.auto_sort_mode, AUTO_SORT_MODE_AFTER_SYNC)


if __name__ == "__main__":
    unittest.main()
