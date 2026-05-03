from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "addon"))

from anki_vn_sorter.config import (
    AUTO_SORT_MODE_AFTER_SYNC,
    AUTO_SORT_MODE_PROFILE_OPEN,
    DEFAULT_JITEN_VN_CSV_URL,
    DEFAULT_KANA_ONLY_MULTIPLIER,
    DEFAULT_PARTIAL_KNOWN_COVERAGE_BONUS,
    DEFAULT_TIER_ORDER,
    DEFAULT_UNKNOWN_KANJI_PENALTY_CAP,
    DEFAULT_UNKNOWN_KANJI_PENALTY_STEP,
    LEGACY_DEFAULT_TIER_ORDER,
    STRATEGY_BALANCED_EASE_V1,
    STRATEGY_EASY_FIRST_TIERED_V1,
    STRATEGY_FREQUENCY_FIRST_SOFT_V1,
    TIER_ALL_KANJI_KNOWN,
    TIER_KANA_ONLY,
    build_default_mature_query,
    parse_config,
)
from anki_vn_sorter.jiten_lists import (
    DEFAULT_JITEN_FREQUENCY_LIST_ID,
    LEGACY_DEFAULT_VN_CSV_URL,
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
                "strategy": STRATEGY_FREQUENCY_FIRST_SOFT_V1,
                "tierOrder": [
                    TIER_ALL_KANJI_KNOWN,
                    TIER_KANA_ONLY,
                    "one_unknown_kanji",
                    "two_unknown_kanji",
                    "three_plus_unknown_kanji",
                ],
                "preferShorterExpressions": False,
                "freqSortWeight": 0.5,
                "kanaOnlyMultiplier": 0.88,
                "unknownKanjiPenaltyStep": 0.2,
                "unknownKanjiPenaltyCap": 0.5,
                "partialKnownCoverageBonus": 0.06,
            }
        )
        self.assertEqual(config.strategy, STRATEGY_FREQUENCY_FIRST_SOFT_V1)
        self.assertEqual(config.tier_order[:2], (TIER_ALL_KANJI_KNOWN, TIER_KANA_ONLY))
        self.assertFalse(config.prefer_shorter_expressions)
        self.assertEqual(config.freqsort_weight, 0.5)
        self.assertEqual(config.kana_only_multiplier, 0.88)
        self.assertEqual(config.unknown_kanji_penalty_step, 0.2)
        self.assertEqual(config.unknown_kanji_penalty_cap, 0.5)
        self.assertEqual(config.partial_known_coverage_bonus, 0.06)

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

    def test_default_jiten_frequency_list_is_global(self) -> None:
        config = parse_config({})
        self.assertEqual(
            config.jiten_frequency_list_id,
            DEFAULT_JITEN_FREQUENCY_LIST_ID,
        )

    def test_blank_jiten_url_remains_an_optional_override(self) -> None:
        config = parse_config({"jitenVnCsvUrl": ""})
        self.assertEqual(config.jiten_vn_csv_url, DEFAULT_JITEN_VN_CSV_URL)

    def test_legacy_visual_novel_url_is_treated_as_no_override(self) -> None:
        config = parse_config({"jitenVnCsvUrl": LEGACY_DEFAULT_VN_CSV_URL})
        self.assertEqual(config.jiten_vn_csv_url, "")

    def test_default_strategy_is_frequency_first_soft(self) -> None:
        config = parse_config({})
        self.assertEqual(config.strategy, STRATEGY_FREQUENCY_FIRST_SOFT_V1)
        self.assertEqual(config.tier_order[:2], DEFAULT_TIER_ORDER[:2])
        self.assertEqual(config.tier_order[:2], (TIER_ALL_KANJI_KNOWN, TIER_KANA_ONLY))
        self.assertEqual(config.kana_only_multiplier, DEFAULT_KANA_ONLY_MULTIPLIER)
        self.assertEqual(
            config.unknown_kanji_penalty_step,
            DEFAULT_UNKNOWN_KANJI_PENALTY_STEP,
        )
        self.assertEqual(
            config.unknown_kanji_penalty_cap,
            DEFAULT_UNKNOWN_KANJI_PENALTY_CAP,
        )
        self.assertEqual(
            config.partial_known_coverage_bonus,
            DEFAULT_PARTIAL_KNOWN_COVERAGE_BONUS,
        )

    def test_legacy_default_tiered_strategy_migrates_to_soft_default(self) -> None:
        config = parse_config(
            {
                "strategy": STRATEGY_EASY_FIRST_TIERED_V1,
                "tierOrder": list(DEFAULT_TIER_ORDER),
                "preferShorterExpressions": True,
                "freqSortWeight": 0.7,
            }
        )
        self.assertEqual(config.strategy, STRATEGY_FREQUENCY_FIRST_SOFT_V1)

    def test_explicit_kana_first_order_is_honored(self) -> None:
        config = parse_config(
            {
                "strategy": STRATEGY_EASY_FIRST_TIERED_V1,
                "tierOrder": list(LEGACY_DEFAULT_TIER_ORDER),
            }
        )
        self.assertEqual(config.tier_order, LEGACY_DEFAULT_TIER_ORDER)
        self.assertEqual(config.strategy, STRATEGY_EASY_FIRST_TIERED_V1)

    def test_explicit_balanced_strategy_is_preserved(self) -> None:
        config = parse_config({"strategy": STRATEGY_BALANCED_EASE_V1})
        self.assertEqual(config.strategy, STRATEGY_BALANCED_EASE_V1)


if __name__ == "__main__":
    unittest.main()
