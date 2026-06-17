from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "addon"))

from anki_sorter.config import (
    AUTO_SORT_MODE_MANUAL_ONLY,
    AUTO_SORT_MODE_PROFILE_OPEN,
    ConfigValidationError,
    SYNC_SAFETY_MODE_DESKTOP_ONLY_ALLOW_AUTO,
    SYNC_SAFETY_MODE_MOBILE_GUARDED,
    DEFAULT_JITEN_VN_CSV_URL,
    DEFAULT_KANA_ONLY_MULTIPLIER,
    DEFAULT_MODEL_NAMES,
    DEFAULT_PARTIAL_KNOWN_COVERAGE_BONUS,
    DEFAULT_READING_EXPOSURE_WEIGHT,
    DEFAULT_SCOPE_QUERY,
    DEFAULT_TIER_ORDER,
    DEFAULT_UNKNOWN_KANJI_PENALTY_CAP,
    DEFAULT_UNKNOWN_KANJI_PENALTY_STEP,
    DEFAULT_YOMITAN_CACHE_TTL_HOURS,
    DEFAULT_YOMITAN_FREQUENCY_INDEX_URL,
    LEGACY_DEFAULT_TIER_ORDER,
    STRATEGY_BALANCED_EASE_V1,
    STRATEGY_EASY_FIRST_TIERED_V1,
    STRATEGY_FREQUENCY_FIRST_SOFT_V1,
    TIER_ALL_KANJI_KNOWN,
    TIER_KANA_ONLY,
    build_default_mature_query,
    parse_config,
)
from anki_sorter.jiten_lists import (
    DEFAULT_JITEN_FREQUENCY_LIST_ID,
    LEGACY_DEFAULT_VN_CSV_URL,
)


class ConfigTests(unittest.TestCase):
    def test_defaults_support_kiku_and_lapis_sentence_cards(self) -> None:
        config = parse_config({})
        self.assertEqual(config.model_names, DEFAULT_MODEL_NAMES)
        self.assertEqual(config.model_names, ("Kiku", "Lapis"))
        self.assertEqual(config.scope_query, DEFAULT_SCOPE_QUERY)
        self.assertEqual(
            config.scope_query,
            '(note:"Kiku" or note:"Lapis") is:new -is:suspended',
        )
        self.assertEqual(
            config.effective_mature_query,
            '(note:"Kiku" or note:"Lapis") prop:ivl>=21 -is:suspended',
        )

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
                "readingExposureWeight": 0.25,
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
        self.assertEqual(config.reading_exposure_weight, 0.25)

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

    def test_default_auto_sort_mode_is_manual_only(self) -> None:
        config = parse_config({})
        self.assertEqual(config.auto_sort_mode, AUTO_SORT_MODE_MANUAL_ONLY)
        self.assertEqual(config.to_dict()["autoSortMode"], AUTO_SORT_MODE_MANUAL_ONLY)

    def test_default_sync_safety_mode_is_mobile_guarded(self) -> None:
        config = parse_config({})
        self.assertEqual(config.sync_safety_mode, SYNC_SAFETY_MODE_MOBILE_GUARDED)
        self.assertEqual(config.to_dict()["syncSafetyMode"], SYNC_SAFETY_MODE_MOBILE_GUARDED)

    def test_desktop_only_sync_safety_mode_round_trip(self) -> None:
        config = parse_config(
            {"syncSafetyMode": SYNC_SAFETY_MODE_DESKTOP_ONLY_ALLOW_AUTO}
        )
        self.assertEqual(
            config.sync_safety_mode,
            SYNC_SAFETY_MODE_DESKTOP_ONLY_ALLOW_AUTO,
        )
        self.assertEqual(
            config.to_dict()["syncSafetyMode"],
            SYNC_SAFETY_MODE_DESKTOP_ONLY_ALLOW_AUTO,
        )

    def test_invalid_sync_safety_mode_is_rejected(self) -> None:
        with self.assertRaises(ConfigValidationError):
            parse_config({"syncSafetyMode": "reckless"})

    def test_default_jiten_frequency_list_is_global(self) -> None:
        config = parse_config({})
        self.assertEqual(
            config.jiten_frequency_list_id,
            DEFAULT_JITEN_FREQUENCY_LIST_ID,
        )

    def test_blank_jiten_url_remains_an_optional_override(self) -> None:
        config = parse_config({"jitenVnCsvUrl": ""})
        self.assertEqual(config.jiten_vn_csv_url, DEFAULT_JITEN_VN_CSV_URL)

    def test_yomitan_frequency_index_url_round_trip(self) -> None:
        url = "https://characterdictionary.tokyo/api/yomitan-frequency-index?entries=%5B%5D"
        config = parse_config({"yomitanFrequencyIndexUrl": url})
        self.assertEqual(config.yomitan_frequency_index_url, url)
        self.assertEqual(config.to_dict()["yomitanFrequencyIndexUrl"], url)

    def test_default_yomitan_frequency_source_is_bee_dictionary(self) -> None:
        config = parse_config({})
        self.assertEqual(
            config.yomitan_frequency_index_url,
            DEFAULT_YOMITAN_FREQUENCY_INDEX_URL,
        )
        self.assertEqual(config.yomitan_cache_ttl_hours, DEFAULT_YOMITAN_CACHE_TTL_HOURS)
        self.assertEqual(config.to_dict()["yomitanCacheTtlHours"], 168)

    def test_yomitan_cache_ttl_round_trip(self) -> None:
        config = parse_config({"yomitanCacheTtlHours": 336})
        self.assertEqual(config.yomitan_cache_ttl_hours, 336)
        self.assertEqual(config.to_dict()["yomitanCacheTtlHours"], 336)

    def test_yomitan_frequency_index_url_rejects_file_url(self) -> None:
        with self.assertRaises(ConfigValidationError):
            parse_config({"yomitanFrequencyIndexUrl": "file:///tmp/freq.zip"})

    def test_yomitan_frequency_index_url_rejects_missing_host(self) -> None:
        with self.assertRaises(ConfigValidationError):
            parse_config({"yomitanFrequencyIndexUrl": "https://"})

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
        self.assertEqual(config.reading_exposure_weight, DEFAULT_READING_EXPOSURE_WEIGHT)

    def test_reading_exposure_weight_must_be_between_zero_and_one(self) -> None:
        with self.assertRaises(ConfigValidationError):
            parse_config({"readingExposureWeight": 1.1})

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
