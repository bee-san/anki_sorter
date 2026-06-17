from __future__ import annotations

import gzip
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "addon"))

import anki_sorter.sorter as sorter
from anki_sorter.config import (
    AUTO_SORT_MODE_AFTER_SYNC,
    SYNC_SAFETY_MODE_DESKTOP_ONLY_ALLOW_AUTO,
    AddonConfig,
)
from anki_sorter.jiten import FrequencyLookup
from anki_sorter.safety import SORT_TRIGGER_AFTER_SYNC, SORT_TRIGGER_API, SORT_TRIGGER_MANUAL
from anki_sorter.sorter import _deck_option_warnings
from anki_sorter.state import SorterState


class _FakeCard:
    def __init__(self, deck_id: int) -> None:
        self.did = deck_id


class _FakeDeckManager:
    def __init__(self, configs: dict[int, dict], decks: dict[int, dict]) -> None:
        self._configs = configs
        self._decks = decks

    def get(self, deck_id: int) -> dict:
        return self._decks[deck_id]

    def config_dict_for_deck_id(self, deck_id: int) -> dict:
        return self._configs[deck_id]


class _FakeCollection:
    def __init__(self, cards: dict[int, _FakeCard], configs: dict[int, dict], decks: dict[int, dict]) -> None:
        self._cards = cards
        self.decks = _FakeDeckManager(configs, decks)

    def get_card(self, card_id: int) -> _FakeCard:
        return self._cards[card_id]


class SorterWarningTests(unittest.TestCase):
    def make_collection(self, config: dict) -> _FakeCollection:
        cards = {1: _FakeCard(100)}
        decks = {100: {"name": "Kiku"}}
        configs = {100: config}
        return _FakeCollection(cards, configs, decks)

    def test_sequential_lowest_position_and_order_gathered_are_accepted(self) -> None:
        col = self.make_collection(
            {
                "new": {"order": 0},
                "newSortOrder": 1,
                "newGatherPriority": 1,
            }
        )
        self.assertEqual(_deck_option_warnings(col, [1]), [])

    def test_random_insertion_is_warned(self) -> None:
        col = self.make_collection(
            {
                "new": {"order": 1},
                "newSortOrder": 1,
                "newGatherPriority": 1,
            }
        )
        warnings = _deck_option_warnings(col, [1])
        self.assertEqual(len(warnings), 1)
        self.assertIn("random new-card insertion order", warnings[0])

    def test_non_gathered_sort_order_is_warned(self) -> None:
        col = self.make_collection(
            {
                "new": {"order": 0},
                "newSortOrder": 4,
                "newGatherPriority": 1,
            }
        )
        warnings = _deck_option_warnings(col, [1])
        self.assertEqual(len(warnings), 1)
        self.assertIn('Order Gathered', warnings[0])

    def test_non_lowest_position_gather_is_warned(self) -> None:
        col = self.make_collection(
            {
                "new": {"order": 0},
                "newSortOrder": 1,
                "newGatherPriority": 5,
            }
        )
        warnings = _deck_option_warnings(col, [1])
        self.assertEqual(len(warnings), 1)
        self.assertIn("Lowest Position", warnings[0])


class _FakeNote(dict):
    pass


class _FakeSortCard:
    def __init__(
        self,
        card_id: int,
        note_id: int,
        due: int,
        expression: str,
        freqsort: str = "",
        model_name: str = "Kiku",
    ) -> None:
        self.id = card_id
        self.nid = note_id
        self.due = due
        self.ord = 0
        self.type = 0
        self.did = 100
        self._note = _FakeNote({"Expression": expression, "FreqSort": freqsort})
        self._model_name = model_name

    def note(self) -> _FakeNote:
        return self._note

    def note_type(self) -> dict[str, str]:
        return {"name": self._model_name}


class _FakeScheduler:
    def __init__(self) -> None:
        self.repositioned_card_ids: list[int] | None = None

    def reposition_new_cards(self, *, card_ids: list[int], **_kwargs: object) -> object:
        self.repositioned_card_ids = card_ids
        return type("Result", (), {"count": len(card_ids)})()


class _FakeMediaManager:
    def __init__(self, media_dir: Path) -> None:
        self._media_dir = media_dir

    def dir(self) -> str:
        return str(self._media_dir)


class _FakeSortCollection:
    def __init__(self, cards: list[_FakeSortCard], media_dir: Path | None = None) -> None:
        self._cards = {card.id: card for card in cards}
        self.decks = _FakeDeckManager(
            {100: {"new": {"order": 0}, "newSortOrder": 1, "newGatherPriority": 1}},
            {100: {"name": "Kiku"}},
        )
        self.sched = _FakeScheduler()
        if media_dir is not None:
            self.media = _FakeMediaManager(media_dir)

    def find_cards(self, query: str) -> list[int]:
        if query == "is:review":
            return []
        return list(self._cards)

    def get_card(self, card_id: int) -> _FakeSortCard:
        return self._cards[card_id]

    def get_note(self, note_id: int) -> _FakeNote:
        for card in self._cards.values():
            if card.nid == note_id:
                return card.note()
        raise KeyError(note_id)


class SorterRankSourceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._original_load_frequency_lookup = sorter.load_frequency_lookup
        self._original_load_state = sorter.load_state
        self._original_save_state = sorter.save_state
        sorter.load_state = lambda: SorterState()
        sorter.save_state = lambda _state: None

    def tearDown(self) -> None:
        sorter.load_frequency_lookup = self._original_load_frequency_lookup
        sorter.load_state = self._original_load_state
        sorter.save_state = self._original_save_state

    def run_sort_with_lookup(self, lookup: FrequencyLookup, expression: str = "漢字", freqsort: str = "99") -> dict:
        sorter.load_frequency_lookup = lambda _config: lookup
        col = _FakeSortCollection([_FakeSortCard(1, 10, 1, expression, freqsort)])
        return sorter.run_sort_on_collection(col, AddonConfig(), "test", force=True)

    def test_yomitan_lookup_rank_is_marked_as_yomitan_in_preview(self) -> None:
        summary = self.run_sort_with_lookup(
            FrequencyLookup(
                ranks={"漢字": 1.0},
                source_url="https://example.test/index.json",
                warnings=(),
                source_kind="yomitan",
            )
        )

        self.assertEqual(summary["topPreview"][0]["rankSource"], "yomitan")
        self.assertEqual(summary["topPreview"][0]["rank"], 1.0)

    def test_yomitan_cache_lookup_rank_is_marked_as_yomitan_in_preview(self) -> None:
        summary = self.run_sort_with_lookup(
            FrequencyLookup(
                ranks={"漢字": 2.0},
                source_url="https://example.test/index.json",
                warnings=(),
                source_kind="yomitan_cache",
            )
        )

        self.assertEqual(summary["topPreview"][0]["rankSource"], "yomitan")
        self.assertEqual(summary["topPreview"][0]["rank"], 2.0)

    def test_jiten_lookup_rank_source_stays_jiten_in_preview(self) -> None:
        for source_kind in ("remote", "cache", "bundled"):
            with self.subTest(source_kind=source_kind):
                summary = self.run_sort_with_lookup(
                    FrequencyLookup(
                        ranks={"漢字": 3.0},
                        source_url="https://example.test/frequency.csv",
                        warnings=(),
                        source_kind=source_kind,
                    )
                )

                self.assertEqual(summary["topPreview"][0]["rankSource"], "jiten")
                self.assertEqual(summary["topPreview"][0]["rank"], 3.0)

    def test_freqsort_fallback_source_stays_freqsort_in_preview(self) -> None:
        summary = self.run_sort_with_lookup(
            FrequencyLookup(ranks={}, source_url=None, warnings=(), source_kind="none"),
            freqsort="42",
        )

        self.assertEqual(summary["topPreview"][0]["rankSource"], "freqsort")
        self.assertEqual(summary["topPreview"][0]["rank"], 42)

    def test_reading_exposure_media_boosts_matching_cards(self) -> None:
        sorter.load_frequency_lookup = lambda _config: FrequencyLookup(
            ranks={},
            source_url=None,
            warnings=(),
            source_kind="none",
        )
        media_dir = Path(tempfile.mkdtemp())
        write_gzip_json(
            media_dir / "_reading_exposure_words.json.gz",
            {
                "schemaVersion": 1,
                "words": [
                    {
                        "word": "読む",
                        "totalCount": 30,
                        "last7DaysCount": 10,
                        "last14DaysCount": 15,
                        "last31DaysCount": 20,
                        "lastSeenAtMillis": 999,
                    }
                ],
            },
        )
        col = _FakeSortCollection(
            [
                _FakeSortCard(1, 10, 1, "既読", ""),
                _FakeSortCard(2, 20, 2, "読む", ""),
            ],
            media_dir=media_dir,
        )

        summary = sorter.run_sort_on_collection(col, AddonConfig(reading_exposure_weight=0.5), "test", force=True)

        self.assertEqual([2, 1], col.sched.repositioned_card_ids)
        self.assertEqual("読む", summary["topPreview"][0]["expression"])
        self.assertGreater(summary["topPreview"][0]["readingExposureScore"], 0.0)
        self.assertEqual(30, summary["topPreview"][0]["readingExposureTotalCount"])
        self.assertEqual(10, summary["topPreview"][0]["readingExposureLast7DaysCount"])
        self.assertEqual(15, summary["topPreview"][0]["readingExposureLast14DaysCount"])
        self.assertEqual(20, summary["topPreview"][0]["readingExposureLast31DaysCount"])

    def test_default_config_accepts_lapis_cards(self) -> None:
        sorter.load_frequency_lookup = lambda _config: FrequencyLookup(
            ranks={"漢字": 1.0},
            source_url="https://example.test/index.json",
            warnings=(),
            source_kind="yomitan",
        )
        col = _FakeSortCollection(
            [_FakeSortCard(1, 10, 1, "漢字", "99", model_name="Lapis")]
        )

        summary = sorter.run_sort_on_collection(col, AddonConfig(), "test", force=True)

        self.assertEqual(summary["candidateCount"], 1)
        self.assertEqual(summary["topPreview"][0]["rankSource"], "yomitan")

    def test_review_cards_are_still_excluded_from_sort_candidates(self) -> None:
        sorter.load_frequency_lookup = lambda _config: FrequencyLookup(
            ranks={"漢字": 1.0},
            source_url="https://example.test/index.json",
            warnings=(),
            source_kind="yomitan",
        )
        review_card = _FakeSortCard(1, 10, 1, "漢字", "99")
        review_card.type = 2
        col = _FakeSortCollection([review_card])

        summary = sorter.run_sort_on_collection(col, AddonConfig(), "test", force=True)

        self.assertEqual(summary["candidateCount"], 0)
        self.assertIsNone(col.sched.repositioned_card_ids)


def write_gzip_json(path: Path, payload: dict) -> None:
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        json.dump(payload, handle)


class SorterSyncSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self._original_load_frequency_lookup = sorter.load_frequency_lookup
        self._original_load_state = sorter.load_state
        self._original_save_state = sorter.save_state
        sorter.load_state = lambda: SorterState()
        self.saved_states: list[SorterState] = []
        sorter.save_state = self.saved_states.append

    def tearDown(self) -> None:
        sorter.load_frequency_lookup = self._original_load_frequency_lookup
        sorter.load_state = self._original_load_state
        sorter.save_state = self._original_save_state

    def _sorting_collection(self) -> _FakeSortCollection:
        return _FakeSortCollection(
            [
                _FakeSortCard(1, 10, 1, "低頻度", "99"),
                _FakeSortCard(2, 20, 2, "高頻度", "1"),
            ]
        )

    def _lookup_that_reorders(self) -> FrequencyLookup:
        return FrequencyLookup(
            ranks={"高頻度": 1.0, "低頻度": 99.0},
            source_url="https://example.test/index.json",
            warnings=(),
            source_kind="yomitan",
        )

    def test_mobile_guarded_after_sync_skips_before_lookup_reposition_and_state_write(self) -> None:
        def fail_if_called(_config: AddonConfig) -> FrequencyLookup:
            raise AssertionError("load_frequency_lookup should not be called for guarded after_sync")

        sorter.load_frequency_lookup = fail_if_called
        col = self._sorting_collection()

        summary = sorter.run_sort_on_collection(
            col,
            AddonConfig(auto_sort_mode=AUTO_SORT_MODE_AFTER_SYNC),
            "test",
            trigger=SORT_TRIGGER_AFTER_SYNC,
        )

        self.assertFalse(summary["applied"])
        self.assertTrue(summary["skippedForSyncSafety"])
        self.assertEqual(summary["skipReason"], "mobile_guarded blocks automatic sorting after sync/profile open")
        self.assertEqual(summary["trigger"], SORT_TRIGGER_AFTER_SYNC)
        self.assertIsNone(col.sched.repositioned_card_ids)
        self.assertEqual(self.saved_states, [])

    def test_unacknowledged_api_skips_before_lookup_reposition_and_state_write(self) -> None:
        def fail_if_called(_config: AddonConfig) -> FrequencyLookup:
            raise AssertionError("load_frequency_lookup should not be called for unacknowledged API")

        sorter.load_frequency_lookup = fail_if_called
        col = self._sorting_collection()

        summary = sorter.run_sort_on_collection(
            col,
            AddonConfig(),
            "test",
            trigger=SORT_TRIGGER_API,
            acknowledged=False,
        )

        self.assertFalse(summary["applied"])
        self.assertTrue(summary["skippedForSyncSafety"])
        self.assertEqual(summary["skipReason"], "manual/API sort request requires acknowledgement")
        self.assertEqual(summary["trigger"], SORT_TRIGGER_API)
        self.assertIsNone(col.sched.repositioned_card_ids)
        self.assertEqual(self.saved_states, [])

    def test_acknowledged_manual_trigger_still_sorts_and_persists(self) -> None:
        sorter.load_frequency_lookup = lambda _config: self._lookup_that_reorders()
        col = self._sorting_collection()

        summary = sorter.run_sort_on_collection(
            col,
            AddonConfig(),
            "test",
            force=True,
            trigger=SORT_TRIGGER_MANUAL,
            acknowledged=True,
        )

        self.assertTrue(summary["applied"])
        self.assertFalse(summary["skippedForSyncSafety"])
        self.assertEqual(summary["trigger"], SORT_TRIGGER_MANUAL)
        self.assertEqual(col.sched.repositioned_card_ids, [2, 1])
        self.assertEqual(len(self.saved_states), 1)

    def test_acknowledged_api_trigger_still_sorts(self) -> None:
        sorter.load_frequency_lookup = lambda _config: self._lookup_that_reorders()
        col = self._sorting_collection()

        summary = sorter.run_sort_on_collection(
            col,
            AddonConfig(),
            "test",
            force=True,
            trigger=SORT_TRIGGER_API,
            acknowledged=True,
        )

        self.assertTrue(summary["applied"])
        self.assertFalse(summary["skippedForSyncSafety"])
        self.assertEqual(summary["trigger"], SORT_TRIGGER_API)
        self.assertEqual(col.sched.repositioned_card_ids, [2, 1])

    def test_desktop_only_allow_auto_after_sync_still_sorts(self) -> None:
        sorter.load_frequency_lookup = lambda _config: self._lookup_that_reorders()
        col = self._sorting_collection()

        summary = sorter.run_sort_on_collection(
            col,
            AddonConfig(
                auto_sort_mode=AUTO_SORT_MODE_AFTER_SYNC,
                sync_safety_mode=SYNC_SAFETY_MODE_DESKTOP_ONLY_ALLOW_AUTO,
            ),
            "test",
            trigger=SORT_TRIGGER_AFTER_SYNC,
        )

        self.assertTrue(summary["applied"])
        self.assertFalse(summary["skippedForSyncSafety"])
        self.assertEqual(summary["trigger"], SORT_TRIGGER_AFTER_SYNC)
        self.assertEqual(col.sched.repositioned_card_ids, [2, 1])


if __name__ == "__main__":
    unittest.main()
