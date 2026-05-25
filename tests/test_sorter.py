from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "addon"))

import anki_vn_sorter.sorter as sorter
from anki_vn_sorter.config import AddonConfig
from anki_vn_sorter.jiten import FrequencyLookup
from anki_vn_sorter.sorter import _deck_option_warnings
from anki_vn_sorter.state import SorterState


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
    def __init__(self, card_id: int, note_id: int, due: int, expression: str, freqsort: str = "") -> None:
        self.id = card_id
        self.nid = note_id
        self.due = due
        self.ord = 0
        self.type = 0
        self.did = 100
        self._note = _FakeNote({"Expression": expression, "FreqSort": freqsort})

    def note(self) -> _FakeNote:
        return self._note

    def note_type(self) -> dict[str, str]:
        return {"name": "Kiku"}


class _FakeScheduler:
    def __init__(self) -> None:
        self.repositioned_card_ids: list[int] | None = None

    def reposition_new_cards(self, *, card_ids: list[int], **_kwargs: object) -> object:
        self.repositioned_card_ids = card_ids
        return type("Result", (), {"count": len(card_ids)})()


class _FakeSortCollection:
    def __init__(self, cards: list[_FakeSortCard]) -> None:
        self._cards = {card.id: card for card in cards}
        self.decks = _FakeDeckManager(
            {100: {"new": {"order": 0}, "newSortOrder": 1, "newGatherPriority": 1}},
            {100: {"name": "Kiku"}},
        )
        self.sched = _FakeScheduler()

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


if __name__ == "__main__":
    unittest.main()
