from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "addon"))

from anki_vn_sorter.jiten_lists import (
    DEFAULT_JITEN_FREQUENCY_LIST_ID,
    dropdown_options,
    get_frequency_list_definition,
)


class JitenListTests(unittest.TestCase):
    def test_default_list_is_global(self) -> None:
        definition = get_frequency_list_definition(DEFAULT_JITEN_FREQUENCY_LIST_ID)
        self.assertEqual(definition.label, "Global")
        self.assertEqual(
            definition.csv_url,
            "https://api.jiten.moe/api/frequency-list/download?downloadType=csv",
        )

    def test_visual_novel_list_uses_media_type_7(self) -> None:
        definition = get_frequency_list_definition("visual_novel")
        self.assertEqual(
            definition.csv_url,
            "https://api.jiten.moe/api/frequency-list/download?downloadType=csv&mediaType=7",
        )

    def test_dropdown_puts_global_and_kanji_first(self) -> None:
        options = dropdown_options()
        self.assertEqual(options[:2], (("global", "Global"), ("kanji", "Kanji")))
        self.assertIn(("visual_novel", "Visual Novel (media)"), options)


if __name__ == "__main__":
    unittest.main()
