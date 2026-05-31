from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "addon"))

from anki_sorter.yomitan_frequency import (  # noqa: E402
    YomitanFrequencyParseError,
    YomitanLoadError,
    load_yomitan_frequency_lookup,
    parse_yomitan_frequency_zip,
    parse_yomitan_index_json,
)


def _frequency_zip(index: dict[str, object] | None, rows: list[object]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        if index is not None:
            archive.writestr("index.json", json.dumps(index))
        archive.writestr("term_meta_bank_1.json", json.dumps(rows))
    return buffer.getvalue()


class ParseYomitanIndexJsonTests(unittest.TestCase):
    def test_parses_index_metadata(self) -> None:
        parsed = parse_yomitan_index_json(
            json.dumps(
                {
                    "title": "Bee's Frequency Dictionary",
                    "downloadUrl": "/api/frequency.zip",
                    "indexUrl": "https://characterdictionary.tokyo/api/index",
                    "revision": "001",
                    "frequencyMode": "occurrence-based",
                }
            ),
            "https://characterdictionary.tokyo/api/index",
        )

        self.assertEqual(parsed.title, "Bee's Frequency Dictionary")
        self.assertEqual(parsed.download_url, "/api/frequency.zip")
        self.assertEqual(parsed.index_url, "https://characterdictionary.tokyo/api/index")
        self.assertEqual(parsed.revision, "001")
        self.assertEqual(parsed.frequency_mode, "occurrence-based")


class ParseYomitanFrequencyZipTests(unittest.TestCase):
    def test_character_dictionary_rank_mode_uses_display_rank_not_occurrence_value(self) -> None:
        parsed = parse_yomitan_frequency_zip(
            _frequency_zip(
                {"title": "CD", "frequencyMode": "occurrence-based", "revision": "r1"},
                [
                    ["の", "freq", {"displayValue": "#1 (avg)", "value": 17001}],
                    ["は", "freq", {"displayValue": "#2 (avg)", "value": 12472}],
                ],
            ),
            source_url="https://characterdictionary.tokyo/api/yomitan-frequency-index?display_mode=rank",
        )

        self.assertEqual(parsed.ranks["の"], 1.0)
        self.assertEqual(parsed.ranks["は"], 2.0)
        self.assertEqual(parsed.title, "CD")
        self.assertEqual(parsed.revision, "r1")
        self.assertEqual(parsed.frequency_mode, "occurrence-based")
        self.assertEqual(parsed.value_kind, "display_rank")

    def test_display_rank_accepts_thousands_separators(self) -> None:
        parsed = parse_yomitan_frequency_zip(
            _frequency_zip(
                {"frequencyMode": "occurrence-based"},
                [["千", "freq", {"displayValue": "#1,234 (avg)", "value": 999999}]],
            ),
            source_url="https://characterdictionary.tokyo/api/yomitan-frequency-index?display_mode=rank",
        )

        self.assertEqual(parsed.ranks["千"], 1234.0)
        self.assertEqual(parsed.value_kind, "display_rank")

    def test_numeric_values_accept_thousands_separators(self) -> None:
        parsed = parse_yomitan_frequency_zip(
            _frequency_zip(
                {"frequencyMode": "rank-based"},
                [["千", "freq", {"value": "1,234"}]],
            )
        )

        self.assertEqual(parsed.ranks["千"], 1234.0)
        self.assertEqual(parsed.value_kind, "rank_value")

    def test_nested_frequency_object_display_rank_works(self) -> None:
        parsed = parse_yomitan_frequency_zip(
            _frequency_zip(
                {"frequencyMode": "occurrence-based"},
                [
                    [
                        "事",
                        "freq",
                        {"frequency": {"displayValue": "#9 (avg)", "value": 2473}, "reading": "こと"},
                    ]
                ],
            ),
            source_url="https://characterdictionary.tokyo/api/yomitan-frequency-index?display_mode=rank",
        )

        self.assertEqual(parsed.ranks["事"], 9.0)
        self.assertEqual(parsed.value_kind, "display_rank")

    def test_character_dictionary_occurrence_mode_converts_values_descending(self) -> None:
        parsed = parse_yomitan_frequency_zip(
            _frequency_zip(
                {"frequencyMode": "occurrence-based"},
                [["多い", "freq", {"value": 500}], ["少ない", "freq", {"value": 10}]],
            ),
            source_url="https://characterdictionary.tokyo/api/yomitan-frequency-index?display_mode=occurrence",
        )

        self.assertEqual(parsed.ranks["多い"], 1.0)
        self.assertEqual(parsed.ranks["少ない"], 2.0)
        self.assertEqual(parsed.value_kind, "occurrence_value_converted")

    def test_generic_rank_based_values_are_preserved(self) -> None:
        parsed = parse_yomitan_frequency_zip(
            _frequency_zip(
                {"frequencyMode": "rank-based"},
                [["一位", "freq", {"value": 1}], ["十位", "freq", {"value": 10}]],
            )
        )

        self.assertEqual(parsed.ranks["一位"], 1.0)
        self.assertEqual(parsed.ranks["十位"], 10.0)
        self.assertEqual(parsed.value_kind, "rank_value")

    def test_duplicate_terms_keep_best_rank_after_occurrence_conversion(self) -> None:
        parsed = parse_yomitan_frequency_zip(
            _frequency_zip(
                {"frequencyMode": "occurrence-based"},
                [
                    ["重複", "freq", {"value": 50}],
                    ["別", "freq", {"value": 100}],
                    ["重複", "freq", {"value": 200}],
                ],
            )
        )

        self.assertEqual(parsed.ranks["重複"], 1.0)
        self.assertEqual(parsed.ranks["別"], 2.0)

    def test_duplicate_occurrence_rows_do_not_create_rank_gaps(self) -> None:
        parsed = parse_yomitan_frequency_zip(
            _frequency_zip(
                {"frequencyMode": "occurrence-based"},
                [
                    ["重複", "freq", {"value": 200}],
                    ["重複", "freq", {"value": 150}],
                    ["別", "freq", {"value": 100}],
                ],
            )
        )

        self.assertEqual(parsed.ranks["重複"], 1.0)
        self.assertEqual(parsed.ranks["別"], 2.0)

    def test_duplicate_terms_keep_best_explicit_rank(self) -> None:
        parsed = parse_yomitan_frequency_zip(
            _frequency_zip(
                {"frequencyMode": "rank-based"},
                [
                    ["重複", "freq", {"displayValue": "#8", "value": 8}],
                    ["重複", "freq", {"displayValue": "#3", "value": 3}],
                ],
            )
        )

        self.assertEqual(parsed.ranks["重複"], 3.0)

    def test_invalid_zip_raises_clear_error(self) -> None:
        with self.assertRaisesRegex(YomitanFrequencyParseError, "valid Yomitan zip"):
            parse_yomitan_frequency_zip(b"not a zip")

    def test_no_usable_banks_raises_clear_error(self) -> None:
        with self.assertRaisesRegex(YomitanFrequencyParseError, "No usable frequency rows"):
            parse_yomitan_frequency_zip(_frequency_zip({"frequencyMode": "rank-based"}, []))


class LoadYomitanFrequencyLookupTests(unittest.TestCase):
    INDEX_URL = "https://example.test/yomitan/index.json"
    CACHE_STEM = "yomitan_frequency_e38162be1e16"

    def test_fresh_cache_bypasses_opener(self) -> None:
        zip_bytes = _frequency_zip({"title": "Cached", "revision": "r1"}, [["語", "freq", {"value": 100}]])
        with tempfile.TemporaryDirectory() as tmp:
            user_dir = Path(tmp)
            cache_path = user_dir / f"{self.CACHE_STEM}.zip"
            cache_path.write_bytes(zip_bytes)
            (user_dir / f"{self.CACHE_STEM}_meta.json").write_text(
                json.dumps(
                    {
                        "indexUrl": self.INDEX_URL,
                        "downloadUrl": "https://example.test/yomitan/frequency.zip",
                        "title": "Cached",
                        "revision": "r1",
                        "frequencyMode": "occurrence-based",
                        "fetchedAt": 123.0,
                        "entryCount": 1,
                    }
                ),
                encoding="utf-8",
            )

            def opener(_url: str, _timeout: int) -> bytes:
                self.fail("fresh cache should bypass network")

            loaded = load_yomitan_frequency_lookup(self.INDEX_URL, user_dir, 5, 24, opener=opener)

        self.assertEqual(loaded.ranks["語"], 1.0)
        self.assertEqual(loaded.title, "Cached")
        self.assertEqual(loaded.source_kind, "cache")
        self.assertEqual(loaded.source_url, self.INDEX_URL)
        self.assertEqual(loaded.download_url, "https://example.test/yomitan/frequency.zip")
        self.assertEqual(loaded.warnings, tuple())

    def test_force_refresh_bypasses_fresh_cache(self) -> None:
        zip_bytes = _frequency_zip({"title": "Remote", "revision": "r2"}, [["新", "freq", {"value": 200}]])
        calls: list[str] = []

        def opener(url: str, _timeout: int) -> bytes:
            calls.append(url)
            if url == self.INDEX_URL:
                return json.dumps({"downloadUrl": "/yomitan/frequency.zip", "title": "Index", "revision": "r2"}).encode()
            return zip_bytes

        with tempfile.TemporaryDirectory() as tmp:
            user_dir = Path(tmp)
            stale_zip = _frequency_zip({"title": "Cached"}, [["古", "freq", {"value": 1}]])
            (user_dir / f"{self.CACHE_STEM}.zip").write_bytes(stale_zip)
            loaded = load_yomitan_frequency_lookup(
                self.INDEX_URL,
                user_dir,
                5,
                24,
                opener=opener,
                force_refresh=True,
            )

        self.assertEqual(calls, [self.INDEX_URL, "https://example.test/yomitan/frequency.zip"])
        self.assertIn("新", loaded.ranks)
        self.assertNotIn("古", loaded.ranks)
        self.assertEqual(loaded.source_kind, "remote")
        self.assertEqual(loaded.download_url, "https://example.test/yomitan/frequency.zip")

    def test_outer_index_frequency_mode_is_used_when_zip_index_omits_it(self) -> None:
        zip_bytes = _frequency_zip(
            {"title": "Remote"},
            [["一位", "freq", {"value": 1}], ["十位", "freq", {"value": 10}]],
        )

        def opener(url: str, _timeout: int) -> bytes:
            if url == self.INDEX_URL:
                return json.dumps(
                    {
                        "downloadUrl": "/yomitan/frequency.zip",
                        "frequencyMode": "rank-based",
                    }
                ).encode()
            return zip_bytes

        with tempfile.TemporaryDirectory() as tmp:
            user_dir = Path(tmp)
            loaded = load_yomitan_frequency_lookup(self.INDEX_URL, user_dir, 5, 24, opener=opener)

            def fail_opener(_url: str, _timeout: int) -> bytes:
                self.fail("fresh cache should bypass network")

            cached = load_yomitan_frequency_lookup(self.INDEX_URL, user_dir, 5, 24, opener=fail_opener)

        self.assertEqual(loaded.ranks["一位"], 1.0)
        self.assertEqual(loaded.ranks["十位"], 10.0)
        self.assertEqual(loaded.source_kind, "remote")
        self.assertEqual(cached.ranks["一位"], 1.0)
        self.assertEqual(cached.ranks["十位"], 10.0)
        self.assertEqual(cached.source_kind, "cache")

    def test_invalid_fresh_cache_refreshes_from_remote(self) -> None:
        zip_bytes = _frequency_zip({"title": "Remote", "revision": "r2"}, [["新", "freq", {"value": 200}]])
        calls: list[str] = []

        def opener(url: str, _timeout: int) -> bytes:
            calls.append(url)
            if url == self.INDEX_URL:
                return json.dumps({"downloadUrl": "/yomitan/frequency.zip", "title": "Index", "revision": "r2"}).encode()
            return zip_bytes

        with tempfile.TemporaryDirectory() as tmp:
            user_dir = Path(tmp)
            cache_path = user_dir / f"{self.CACHE_STEM}.zip"
            cache_path.write_bytes(b"not a zip")
            loaded = load_yomitan_frequency_lookup(
                self.INDEX_URL,
                user_dir,
                5,
                24,
                opener=opener,
            )

        self.assertEqual(calls, [self.INDEX_URL, "https://example.test/yomitan/frequency.zip"])
        self.assertEqual(loaded.ranks["新"], 1.0)
        self.assertEqual(loaded.source_kind, "remote")
        self.assertTrue(
            any("Ignoring an invalid cached Yomitan" in warning for warning in loaded.warnings)
        )

    def test_bad_remote_does_not_overwrite_valid_stale_cache(self) -> None:
        cached_zip = _frequency_zip({"title": "Stale", "revision": "old"}, [["古", "freq", {"value": 10}]])

        def opener(_url: str, _timeout: int) -> bytes:
            raise OSError("network down")

        with tempfile.TemporaryDirectory() as tmp:
            user_dir = Path(tmp)
            cache_path = user_dir / f"{self.CACHE_STEM}.zip"
            cache_path.write_bytes(cached_zip)
            old_bytes = cache_path.read_bytes()
            loaded = load_yomitan_frequency_lookup(self.INDEX_URL, user_dir, 5, 0, opener=opener)
            self.assertEqual(cache_path.read_bytes(), old_bytes)

        self.assertEqual(loaded.ranks["古"], 1.0)
        self.assertEqual(loaded.source_kind, "cache")
        self.assertTrue(any("stale cached Yomitan" in warning for warning in loaded.warnings))

    def test_bad_remote_uses_bundled_snapshot_when_no_cache_exists(self) -> None:
        bundled_zip = _frequency_zip(
            {"title": "Bee's Frequency Dictionary", "revision": "seed"},
            [["蜂", "freq", {"value": 100}]],
        )

        def opener(_url: str, _timeout: int) -> bytes:
            raise OSError("network down")

        with tempfile.TemporaryDirectory() as tmp:
            user_dir = Path(tmp)
            bundled_path = user_dir / "bee_frequency.zip"
            bundled_path.write_bytes(bundled_zip)
            loaded = load_yomitan_frequency_lookup(
                self.INDEX_URL,
                user_dir,
                5,
                168,
                opener=opener,
                bundled_zip_path=bundled_path,
            )

        self.assertEqual(loaded.ranks["蜂"], 1.0)
        self.assertEqual(loaded.title, "Bee's Frequency Dictionary")
        self.assertEqual(loaded.source_kind, "bundled")
        self.assertTrue(any("bundled Bee Yomitan" in warning for warning in loaded.warnings))

    def test_relative_download_url_is_resolved_against_index_url(self) -> None:
        index_url = "https://example.test/api/yomitan/index.json?x=1"
        zip_bytes = _frequency_zip({"title": "Remote"}, [["語", "freq", {"value": 100}]])
        calls: list[str] = []

        def opener(url: str, _timeout: int) -> bytes:
            calls.append(url)
            if url == index_url:
                return json.dumps({"downloadUrl": "../downloads/frequency.zip"}).encode()
            return zip_bytes

        with tempfile.TemporaryDirectory() as tmp:
            loaded = load_yomitan_frequency_lookup(index_url, Path(tmp), 5, 24, opener=opener)

        self.assertEqual(calls[1], "https://example.test/api/downloads/frequency.zip")
        self.assertEqual(loaded.download_url, "https://example.test/api/downloads/frequency.zip")

    def test_direct_zip_url_works(self) -> None:
        index_url = "https://example.test/yomitan/frequency.zip"
        zip_bytes = _frequency_zip({"title": "Direct", "revision": "zip"}, [["直", "freq", {"value": 5}]])

        def opener(url: str, _timeout: int) -> bytes:
            self.assertEqual(url, index_url)
            return zip_bytes

        with tempfile.TemporaryDirectory() as tmp:
            loaded = load_yomitan_frequency_lookup(index_url, Path(tmp), 5, 24, opener=opener)

        self.assertEqual(loaded.ranks["直"], 1.0)
        self.assertEqual(loaded.title, "Direct")
        self.assertEqual(loaded.download_url, index_url)
        self.assertEqual(loaded.source_kind, "remote")

    def test_unsupported_url_scheme_rejected_before_fetch(self) -> None:
        def opener(_url: str, _timeout: int) -> bytes:
            self.fail("unsupported scheme should be rejected before fetch")

        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(YomitanLoadError, "Only http and https"):
                load_yomitan_frequency_lookup("file:///tmp/frequency.zip", Path(tmp), 5, 24, opener=opener)


if __name__ == "__main__":
    unittest.main()
