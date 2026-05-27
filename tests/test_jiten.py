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
from anki_vn_sorter.yomitan_frequency import YomitanLoadError, YomitanLoadResult


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

    def test_prefers_configured_yomitan_frequency_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            user_dir = Path(temp_dir)
            calls: list[tuple[str, Path, int, int, bool]] = []

            def fake_load_yomitan_frequency_lookup(
                index_url: str,
                passed_user_dir: Path,
                timeout_seconds: int,
                cache_ttl_hours: int,
                opener=None,
                *,
                force_refresh: bool = False,
            ) -> YomitanLoadResult:
                calls.append(
                    (
                        index_url,
                        passed_user_dir,
                        timeout_seconds,
                        cache_ttl_hours,
                        force_refresh,
                    )
                )
                return YomitanLoadResult(
                    ranks={"既読": 2.0},
                    title="Bee's Frequency Dictionary",
                    source_url=index_url,
                    download_url="https://example.test/frequency.zip",
                    revision="001",
                    warnings=("from loader",),
                    source_kind="remote",
                )

            original_ensure_user_files_dir = jiten.ensure_user_files_dir
            original_load_yomitan_frequency_lookup = jiten.load_yomitan_frequency_lookup
            jiten.ensure_user_files_dir = lambda: user_dir
            jiten.load_yomitan_frequency_lookup = fake_load_yomitan_frequency_lookup
            try:
                lookup = load_frequency_lookup(
                    AddonConfig(
                        yomitan_frequency_index_url=" https://example.test/index.json ",
                        jiten_request_timeout_seconds=7,
                        jiten_cache_ttl_hours=11,
                    ),
                    opener=lambda url, timeout: self.fail("Jiten CSV should not be fetched"),
                )
            finally:
                jiten.ensure_user_files_dir = original_ensure_user_files_dir
                jiten.load_yomitan_frequency_lookup = original_load_yomitan_frequency_lookup

            self.assertEqual(lookup.rank_for("既読"), 2.0)
            self.assertEqual(lookup.source_url, "https://example.test/index.json")
            self.assertEqual(lookup.source_kind, "yomitan")
            self.assertEqual(lookup.warnings, ("from loader",))
            self.assertEqual(
                calls,
                [("https://example.test/index.json", user_dir, 7, 11, False)],
            )

    def test_refresh_forwards_force_refresh_to_yomitan_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            user_dir = Path(temp_dir)
            force_refresh_values: list[bool] = []

            def fake_load_yomitan_frequency_lookup(
                index_url: str,
                passed_user_dir: Path,
                timeout_seconds: int,
                cache_ttl_hours: int,
                opener=None,
                *,
                force_refresh: bool = False,
            ) -> YomitanLoadResult:
                force_refresh_values.append(force_refresh)
                return YomitanLoadResult(
                    ranks={"更新": 1.0},
                    title=None,
                    source_url=index_url,
                    download_url=index_url,
                    revision=None,
                    warnings=tuple(),
                    source_kind="cache",
                )

            original_ensure_user_files_dir = jiten.ensure_user_files_dir
            original_load_yomitan_frequency_lookup = jiten.load_yomitan_frequency_lookup
            jiten.ensure_user_files_dir = lambda: user_dir
            jiten.load_yomitan_frequency_lookup = fake_load_yomitan_frequency_lookup
            try:
                lookup = refresh_frequency_lookup(
                    AddonConfig(
                        yomitan_frequency_index_url="https://example.test/index.json"
                    )
                )
            finally:
                jiten.ensure_user_files_dir = original_ensure_user_files_dir
                jiten.load_yomitan_frequency_lookup = original_load_yomitan_frequency_lookup

            self.assertEqual(lookup.rank_for("更新"), 1.0)
            self.assertEqual(lookup.source_kind, "yomitan_cache")
            self.assertEqual(force_refresh_values, [True])

    def test_yomitan_failure_falls_back_to_jiten_cache_with_warning(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            user_dir = Path(temp_dir)
            cache_path = user_dir / "jiten_frequency_global.csv"
            cache_path.write_text("expression,rank\n退避,5\n", encoding="utf-8")
            os.utime(cache_path, (1, 1))

            def fake_load_yomitan_frequency_lookup(*args, **kwargs) -> YomitanLoadResult:
                raise YomitanLoadError("boom")

            original_ensure_user_files_dir = jiten.ensure_user_files_dir
            original_load_yomitan_frequency_lookup = jiten.load_yomitan_frequency_lookup
            jiten.ensure_user_files_dir = lambda: user_dir
            jiten.load_yomitan_frequency_lookup = fake_load_yomitan_frequency_lookup
            try:
                lookup = load_frequency_lookup(
                    AddonConfig(
                        yomitan_frequency_index_url="https://example.test/index.json",
                        jiten_vn_csv_url="https://example.invalid/visual-novel.csv",
                        jiten_cache_ttl_hours=24,
                    ),
                    opener=lambda url, timeout: "<html>error</html>",
                )
            finally:
                jiten.ensure_user_files_dir = original_ensure_user_files_dir
                jiten.load_yomitan_frequency_lookup = original_load_yomitan_frequency_lookup

            self.assertEqual(lookup.rank_for("退避"), 5.0)
            self.assertEqual(lookup.source_kind, "cache")
            self.assertTrue(
                any(
                    "Could not load the configured Yomitan frequency dictionary" in warning
                    for warning in lookup.warnings
                )
            )

    def test_blank_yomitan_url_preserves_jiten_lookup_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            user_dir = Path(temp_dir)
            original_ensure_user_files_dir = jiten.ensure_user_files_dir
            jiten.ensure_user_files_dir = lambda: user_dir
            try:
                lookup = load_frequency_lookup(
                    AddonConfig(
                        yomitan_frequency_index_url="  ",
                        jiten_vn_csv_url="https://example.invalid/visual-novel.csv",
                    ),
                    opener=lambda url, timeout: "expression,rank\n既読,3\n",
                )
            finally:
                jiten.ensure_user_files_dir = original_ensure_user_files_dir

            self.assertEqual(lookup.rank_for("既読"), 3.0)
            self.assertEqual(lookup.source_kind, "remote")


if __name__ == "__main__":
    unittest.main()
