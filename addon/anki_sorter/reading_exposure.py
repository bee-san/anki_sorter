from __future__ import annotations

import gzip
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .normalization import normalize_lookup_text

MANIFEST_FILE = "_reading_exposure_manifest.json"
WORDS_FILE = "_reading_exposure_words.json.gz"
LEGACY_WORDS_FILE = "_kani_reading_exposure_words.json.gz"
CONTRACT = "reading-exposure-v1"


@dataclass(frozen=True)
class ReadingExposureStats:
    total_count: int = 0
    last_7_days_count: int = 0
    last_14_days_count: int = 0
    last_31_days_count: int = 0
    last_seen_at_millis: int = 0

    @property
    def score(self) -> float:
        recent = math.log1p(max(0, self.last_7_days_count)) * 0.55
        mid = math.log1p(max(0, self.last_14_days_count - self.last_7_days_count)) * 0.25
        month = math.log1p(max(0, self.last_31_days_count - self.last_14_days_count)) * 0.12
        lifetime = math.log1p(max(0, self.total_count)) * 0.08
        return min(1.0, (recent + mid + month + lifetime) / 3.0)


@dataclass(frozen=True)
class ReadingExposureIndex:
    stats_by_expression: dict[str, ReadingExposureStats]
    warnings: tuple[str, ...] = ()
    source_path: str | None = None

    def stat_for(self, expression: str) -> ReadingExposureStats | None:
        return self.stats_by_expression.get(normalize_lookup_text(expression))


def load_reading_exposure_index_from_collection(col: Any) -> ReadingExposureIndex:
    media_dir = collection_media_dir(col)
    if media_dir is None:
        return ReadingExposureIndex({})
    return load_reading_exposure_index(media_dir)


def collection_media_dir(col: Any) -> Path | None:
    media = getattr(col, "media", None)
    if media is None:
        return None
    media_dir = getattr(media, "dir", None)
    if not callable(media_dir):
        return None
    try:
        raw_path = media_dir()
    except Exception:
        return None
    if not raw_path:
        return None
    return Path(str(raw_path))


def load_reading_exposure_index(media_dir: Path | str) -> ReadingExposureIndex:
    base = Path(media_dir)
    candidates, manifest_warnings = word_file_candidates(base)
    if not candidates:
        return ReadingExposureIndex({}, warnings=tuple(manifest_warnings))

    warnings = list(manifest_warnings)
    for path in candidates:
        if not path.is_file():
            continue
        try:
            return ReadingExposureIndex(parse_word_payload(read_json_payload(path)), source_path=str(path))
        except Exception as error:
            warnings.append(f"Could not load reading exposure media from {path.name}: {error}")
    return ReadingExposureIndex({}, warnings=tuple(warnings))


def word_file_candidates(media_dir: Path) -> tuple[list[Path], list[str]]:
    manifest_path = media_dir / MANIFEST_FILE
    warnings = manifest_warnings(manifest_path)

    candidates = [media_dir / WORDS_FILE, media_dir / LEGACY_WORDS_FILE]
    return candidates, warnings


def manifest_warnings(manifest_path: Path) -> list[str]:
    warnings: list[str] = []
    if manifest_path.is_file():
        try:
            manifest = read_json_payload(manifest_path)
        except Exception as error:
            warnings.append(f"Could not read reading exposure manifest: {error}")
        else:
            warnings.extend(validate_manifest(manifest, manifest_path.parent))
    return warnings


def validate_manifest(manifest: dict[str, Any], media_dir: Path) -> list[str]:
    warnings: list[str] = []
    contract = str(manifest.get("contract") or "")
    if contract and contract != CONTRACT:
        warnings.append(f"Reading exposure manifest uses unexpected contract {contract!r}.")

    word_file = str(manifest.get("wordFile") or WORDS_FILE)
    if word_file != WORDS_FILE:
        warnings.append(
            f"Reading exposure manifest wordFile must be {WORDS_FILE}; custom paths are not supported."
        )
    elif not (media_dir / WORDS_FILE).is_file():
        warnings.append(f"Reading exposure word file is missing: {WORDS_FILE}")
    return warnings


def read_json_payload(path: Path) -> dict[str, Any]:
    if path.name.endswith(".gz"):
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            payload = json.load(handle)
    else:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("payload must be a JSON object")
    return payload


def parse_word_payload(payload: dict[str, Any]) -> dict[str, ReadingExposureStats]:
    words = payload.get("words")
    if not isinstance(words, list):
        raise ValueError("payload must contain a words array")

    stats_by_expression: dict[str, ReadingExposureStats] = {}
    for row in words:
        if not isinstance(row, dict):
            continue
        expression = normalize_lookup_text(str(row.get("word") or ""))
        if not expression:
            continue
        stats = ReadingExposureStats(
            total_count=_int_field(row, "totalCount"),
            last_7_days_count=_int_field(row, "last7DaysCount"),
            last_14_days_count=_int_field(row, "last14DaysCount"),
            last_31_days_count=_int_field(row, "last31DaysCount"),
            last_seen_at_millis=_int_field(row, "lastSeenAtMillis"),
        )
        current = stats_by_expression.get(expression)
        if current is None or exposure_sort_key(stats) > exposure_sort_key(current):
            stats_by_expression[expression] = stats
    return stats_by_expression


def exposure_sort_key(stats: ReadingExposureStats) -> tuple[float, int, int, int]:
    return (
        stats.score,
        stats.last_7_days_count,
        stats.total_count,
        stats.last_seen_at_millis,
    )


def _int_field(row: dict[str, Any], key: str) -> int:
    try:
        return max(0, int(row.get(key) or 0))
    except (TypeError, ValueError):
        return 0
