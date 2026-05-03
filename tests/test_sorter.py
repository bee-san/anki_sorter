from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "addon"))

from anki_vn_sorter.sorter import _deck_option_warnings


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


if __name__ == "__main__":
    unittest.main()
