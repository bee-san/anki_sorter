from __future__ import annotations

import gzip
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "addon"))

from anki_sorter.reading_exposure import (
    MANIFEST_FILE,
    WORDS_FILE,
    ReadingExposureStats,
    load_reading_exposure_index,
)


class ReadingExposureTests(unittest.TestCase):
    def test_missing_media_is_quietly_empty(self) -> None:
        media_dir = Path(tempfile.mkdtemp())

        index = load_reading_exposure_index(media_dir)

        self.assertEqual({}, index.stats_by_expression)
        self.assertEqual((), index.warnings)

    def test_loads_generic_word_media_from_manifest(self) -> None:
        media_dir = Path(tempfile.mkdtemp())
        (media_dir / MANIFEST_FILE).write_text(
            json.dumps(
                {
                    "contract": "reading-exposure-v1",
                    "wordFile": WORDS_FILE,
                }
            ),
            encoding="utf-8",
        )
        write_gzip_json(
            media_dir / WORDS_FILE,
            {
                "schemaVersion": 1,
                "words": [
                    {
                        "word": " 読む ",
                        "totalCount": 12,
                        "last7DaysCount": 4,
                        "last14DaysCount": 8,
                        "last31DaysCount": 10,
                        "lastSeenAtMillis": 1234,
                    }
                ],
            },
        )

        index = load_reading_exposure_index(media_dir)

        stats = index.stat_for("読む")
        self.assertIsNotNone(stats)
        self.assertEqual(12, stats.total_count)
        self.assertEqual(4, stats.last_7_days_count)
        self.assertGreater(stats.score, 0.0)
        self.assertEqual((), index.warnings)

    def test_malformed_existing_media_is_reported_as_warning(self) -> None:
        media_dir = Path(tempfile.mkdtemp())
        (media_dir / WORDS_FILE).write_text("not json", encoding="utf-8")

        index = load_reading_exposure_index(media_dir)

        self.assertEqual({}, index.stats_by_expression)
        self.assertEqual(1, len(index.warnings))
        self.assertIn("Could not load reading exposure media", index.warnings[0])

    def test_manifest_missing_word_file_is_reported_as_warning(self) -> None:
        media_dir = Path(tempfile.mkdtemp())
        (media_dir / MANIFEST_FILE).write_text(
            json.dumps(
                {
                    "contract": "reading-exposure-v1",
                    "wordFile": WORDS_FILE,
                }
            ),
            encoding="utf-8",
        )

        index = load_reading_exposure_index(media_dir)

        self.assertEqual({}, index.stats_by_expression)
        self.assertEqual(1, len(index.warnings))
        self.assertIn("Reading exposure word file is missing", index.warnings[0])

    def test_manifest_word_file_must_use_generic_media_name(self) -> None:
        media_dir = Path(tempfile.mkdtemp())
        (media_dir / MANIFEST_FILE).write_text(
            json.dumps(
                {
                    "contract": "reading-exposure-v1",
                    "wordFile": "../outside.json.gz",
                }
            ),
            encoding="utf-8",
        )

        index = load_reading_exposure_index(media_dir)

        self.assertEqual({}, index.stats_by_expression)
        self.assertEqual(1, len(index.warnings))
        self.assertIn("custom paths are not supported", index.warnings[0])

    def test_recent_count_scores_higher_than_old_lifetime_count(self) -> None:
        recent = ReadingExposureStats(total_count=3, last_7_days_count=3, last_14_days_count=3, last_31_days_count=3)
        old = ReadingExposureStats(total_count=20, last_7_days_count=0, last_14_days_count=0, last_31_days_count=0)

        self.assertGreater(recent.score, old.score)


def write_gzip_json(path: Path, payload: dict) -> None:
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        json.dump(payload, handle)


if __name__ == "__main__":
    unittest.main()
