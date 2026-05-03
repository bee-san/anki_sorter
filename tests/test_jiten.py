from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "addon"))

from anki_vn_sorter.config import AddonConfig
import anki_vn_sorter.jiten as jiten
from anki_vn_sorter.jiten import (
    FrequencyParseError,
    discover_visual_novel_csv_url,
    load_frequency_lookup,
    parse_frequency_csv,
    refresh_frequency_lookup,
)


class ParseFrequencyCsvTests(unittest.TestCase):
    def test_parses_headered_csv(self) -> None:
        csv_text = "expression,reading,rank\n学校,がっこう,42\n恋愛,れんあい,7\n"
        ranks = parse_frequency_csv(csv_text)
        self.assertEqual(ranks["学校"], 42.0)
        self.assertEqual(ranks["恋愛"], 7.0)

    def test_parses_alternative_headers(self) -> None:
        csv_text = "term,score\n既読,12\n未読,33\n"
        ranks = parse_frequency_csv(csv_text)
        self.assertEqual(ranks["既読"], 12.0)
        self.assertEqual(ranks["未読"], 33.0)

    def test_discovers_visual_novel_csv_link(self) -> None:
        html = """
        <table>
          <tr>
            <td>Visual Novel</td>
            <td><a href="/downloads/visual-novel.csv">CSV</a></td>
          </tr>
        </table>
        """
        url = discover_visual_novel_csv_url(html, "https://jiten.moe/other")
        self.assertEqual(url, "https://jiten.moe/downloads/visual-novel.csv")

    def test_raises_for_invalid_csv(self) -> None:
        with self.assertRaises(FrequencyParseError):
            parse_frequency_csv("<html>not csv</html>")

    def test_invalid_fetch_does_not_poison_existing_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            user_dir = Path(temp_dir)
            cache_path = user_dir / "jiten_frequency_global.csv"
            cache_path.write_text(
                "expression,rank\n既読,7\n",
                encoding="utf-8",
            )
            os.utime(cache_path, (1, 1))
            original_ensure_user_files_dir = jiten.ensure_user_files_dir
            jiten.ensure_user_files_dir = lambda: user_dir
            try:
                lookup = load_frequency_lookup(
                    AddonConfig(
                        jiten_vn_csv_url="https://example.invalid/visual-novel.csv",
                        jiten_cache_ttl_hours=24,
                    ),
                    opener=lambda url, timeout: "<html>error</html>",
                )
            finally:
                jiten.ensure_user_files_dir = original_ensure_user_files_dir

            self.assertEqual(lookup.rank_for("既読"), 7.0)
            self.assertTrue(
                any(
                    "Could not refresh the Jiten Global CSV" in warning
                    for warning in lookup.warnings
                )
            )
            self.assertEqual(
                cache_path.read_text(encoding="utf-8"),
                "expression,rank\n既読,7\n",
            )

    def test_uses_bundled_snapshot_when_live_source_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            user_dir = Path(temp_dir)
            bundled_path = user_dir / "bundled.csv"
            bundled_path.write_text("expression,rank\n未読,11\n", encoding="utf-8")

            original_ensure_user_files_dir = jiten.ensure_user_files_dir
            original_bundled_frequency_path = jiten.bundled_frequency_path
            jiten.ensure_user_files_dir = lambda: user_dir
            jiten.bundled_frequency_path = lambda list_id: bundled_path
            try:
                lookup = load_frequency_lookup(
                    AddonConfig(
                        jiten_vn_csv_url="https://example.invalid/visual-novel.csv",
                    ),
                    opener=lambda url, timeout: "<html>error</html>",
                )
            finally:
                jiten.ensure_user_files_dir = original_ensure_user_files_dir
                jiten.bundled_frequency_path = original_bundled_frequency_path

            self.assertEqual(lookup.rank_for("未読"), 11.0)
            self.assertEqual(lookup.source_kind, "bundled")
            self.assertIn("Using the bundled Jiten Global CSV snapshot.", lookup.warnings)

    def test_refresh_bypasses_fresh_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            user_dir = Path(temp_dir)
            cache_path = user_dir / "jiten_frequency_global.csv"
            cache_path.write_text("expression,rank\n既読,7\n", encoding="utf-8")

            original_ensure_user_files_dir = jiten.ensure_user_files_dir
            jiten.ensure_user_files_dir = lambda: user_dir
            try:
                lookup = refresh_frequency_lookup(
                    AddonConfig(
                        jiten_vn_csv_url="https://example.invalid/visual-novel.csv",
                    ),
                    opener=lambda url, timeout: "expression,rank\n既読,3\n",
                )
            finally:
                jiten.ensure_user_files_dir = original_ensure_user_files_dir

            self.assertEqual(lookup.rank_for("既読"), 3.0)
            self.assertEqual(lookup.source_kind, "remote")
            self.assertEqual(
                cache_path.read_text(encoding="utf-8"),
                "expression,rank\n既読,3\n",
            )

    def test_visual_novel_falls_back_to_legacy_cache_filename(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            user_dir = Path(temp_dir)
            legacy_cache_path = user_dir / "jiten_vn_frequency.csv"
            legacy_cache_path.write_text("expression,rank\n既読,9\n", encoding="utf-8")
            os.utime(legacy_cache_path, (1, 1))

            original_ensure_user_files_dir = jiten.ensure_user_files_dir
            jiten.ensure_user_files_dir = lambda: user_dir
            try:
                lookup = load_frequency_lookup(
                    AddonConfig(
                        jiten_frequency_list_id="visual_novel",
                        jiten_vn_csv_url="https://example.invalid/visual-novel.csv",
                        jiten_cache_ttl_hours=24,
                    ),
                    opener=lambda url, timeout: "<html>error</html>",
                )
            finally:
                jiten.ensure_user_files_dir = original_ensure_user_files_dir

            migrated_cache_path = user_dir / "jiten_frequency_visual_novel.csv"
            self.assertEqual(lookup.rank_for("既読"), 9.0)
            self.assertTrue(migrated_cache_path.exists())
            self.assertEqual(
                migrated_cache_path.read_text(encoding="utf-8"),
                "expression,rank\n既読,9\n",
            )
            self.assertTrue(
                any(
                    "Using a stale cached Jiten Visual Novel CSV." in warning
                    for warning in lookup.warnings
                )
            )


if __name__ == "__main__":
    unittest.main()
