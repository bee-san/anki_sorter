from __future__ import annotations

import csv
import io
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from .config import AddonConfig
from .normalization import normalize_lookup_text
from .state import ensure_user_files_dir

CSV_HREF_RE = re.compile(r'href="([^"]+csv[^"]*)"', re.IGNORECASE)
QUOTED_CSV_RE = re.compile(r'["\']([^"\']+csv[^"\']*)["\']', re.IGNORECASE)

EXPRESSION_HEADERS = (
    "expression",
    "term",
    "surface",
    "word",
    "spelling",
    "text",
    "kanji",
)
RANK_HEADERS = (
    "rank",
    "frequency",
    "frequency_rank",
    "freq",
    "position",
    "score",
    "count",
)


@dataclass(frozen=True)
class FrequencyLookup:
    ranks: dict[str, float]
    source_url: str | None
    warnings: tuple[str, ...]

    def rank_for(self, expression: str) -> float | None:
        key = normalize_lookup_text(expression)
        if not key:
            return None
        return self.ranks.get(key)


class FrequencyParseError(ValueError):
    pass


def load_frequency_lookup(
    config: AddonConfig,
    opener: Callable[[str, int], str] | None = None,
) -> FrequencyLookup:
    opener = opener or _default_fetch_text
    user_dir = ensure_user_files_dir()
    cache_path = user_dir / "jiten_vn_frequency.csv"
    meta_path = user_dir / "jiten_vn_frequency_meta.json"
    warnings: list[str] = []

    meta = _read_json(meta_path)
    cache_is_fresh = _is_fresh(cache_path, config.jiten_cache_ttl_hours)
    skip_cache_fallback = False

    if cache_is_fresh:
        try:
            return FrequencyLookup(
                ranks=parse_frequency_csv(cache_path.read_text(encoding="utf-8")),
                source_url=_meta_source_url(meta),
                warnings=tuple(),
            )
        except (OSError, UnicodeDecodeError, FrequencyParseError) as error:
            warnings.append(f"Ignoring an invalid cached Jiten frequency list: {error}")
            skip_cache_fallback = True

    csv_url = config.jiten_vn_csv_url.strip() or _meta_source_url(meta)
    if not csv_url:
        try:
            page_text = opener(
                config.jiten_discovery_url,
                config.jiten_request_timeout_seconds,
            )
            csv_url = discover_visual_novel_csv_url(
                page_text, config.jiten_discovery_url
            )
            if csv_url:
                warnings.append(
                    "Discovered the Visual Novel CSV URL from the Jiten tools page."
                )
        except Exception as error:  # pragma: no cover - best effort network path
            warnings.append(f"Could not fetch the Jiten tools page: {error}")

    if csv_url:
        try:
            csv_text = opener(csv_url, config.jiten_request_timeout_seconds)
            parsed_ranks = parse_frequency_csv(csv_text)
            cache_path.write_text(csv_text, encoding="utf-8")
            _write_json(
                meta_path,
                {
                    "sourceUrl": csv_url,
                    "fetchedAt": time.time(),
                },
            )
            return FrequencyLookup(
                ranks=parsed_ranks,
                source_url=csv_url,
                warnings=tuple(warnings),
            )
        except Exception as error:  # pragma: no cover - best effort network path
            warnings.append(f"Could not refresh the Jiten Visual Novel CSV: {error}")

    if cache_path.exists() and not skip_cache_fallback:
        try:
            warnings.append("Using a stale cached Jiten Visual Novel CSV.")
            return FrequencyLookup(
                ranks=parse_frequency_csv(cache_path.read_text(encoding="utf-8")),
                source_url=_meta_source_url(meta),
                warnings=tuple(warnings),
            )
        except (OSError, UnicodeDecodeError, FrequencyParseError) as error:
            warnings.append(f"Could not read stale Jiten cache: {error}")

    warnings.append(
        "Jiten Visual Novel CSV is unavailable; falling back to Kiku FreqSort only."
    )
    return FrequencyLookup(ranks={}, source_url=None, warnings=tuple(warnings))


def discover_visual_novel_csv_url(page_text: str, base_url: str) -> str | None:
    text = page_text or ""
    normalized = text.lower()

    for match in CSV_HREF_RE.finditer(text):
        candidate = match.group(1)
        start = max(0, match.start() - 700)
        end = min(len(text), match.end() + 700)
        window = normalized[start:end]
        if "visual novel" in window:
            return urljoin(base_url, candidate)

    for match in QUOTED_CSV_RE.finditer(text):
        candidate = match.group(1)
        if "visual" in candidate.lower():
            return urljoin(base_url, candidate)

    return None


def parse_frequency_csv(csv_text: str) -> dict[str, float]:
    text = csv_text.lstrip("\ufeff")
    if not text.strip():
        raise FrequencyParseError("The frequency CSV was empty.")
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample)
    except csv.Error:
        dialect = csv.excel

    rows = list(csv.reader(io.StringIO(text), dialect))
    if not rows:
        return {}

    has_header = csv.Sniffer().has_header(sample) if len(rows) > 1 else False
    expression_index = 0
    rank_index = 1 if rows and len(rows[0]) > 1 else 0
    start_row = 0

    if has_header:
        header = [_normalize_header(cell) for cell in rows[0]]
        expression_index = _find_header_index(header, EXPRESSION_HEADERS, default=0)
        rank_index = _find_header_index(
            header,
            RANK_HEADERS,
            default=_find_numeric_candidate_index(rows[1:], skip=expression_index),
        )
        start_row = 1
    else:
        rank_index = _find_numeric_candidate_index(rows, skip=expression_index)

    ranks: dict[str, float] = {}
    for row in rows[start_row:]:
        if expression_index >= len(row) or rank_index >= len(row):
            continue
        expression = normalize_lookup_text(row[expression_index])
        if not expression:
            continue
        rank = _parse_positive_number(row[rank_index])
        if rank is None:
            continue
        previous = ranks.get(expression)
        if previous is None or rank < previous:
            ranks[expression] = rank

    if not ranks:
        raise FrequencyParseError("No usable frequency rows were found in the downloaded CSV.")

    return ranks


def _default_fetch_text(url: str, timeout_seconds: int) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": "anki-vn-sorter/1.0",
            "Accept": "text/plain,text/csv,text/html,*/*",
        },
    )
    with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
        return response.read().decode("utf-8")


def _normalize_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def _find_header_index(
    header: list[str],
    accepted_names: tuple[str, ...],
    default: int,
) -> int:
    for accepted in accepted_names:
        try:
            return header.index(accepted)
        except ValueError:
            continue
    return default


def _find_numeric_candidate_index(rows: list[list[str]], skip: int) -> int:
    if not rows:
        return 1 if skip == 0 else 0
    widest = max(len(row) for row in rows)
    candidates = [index for index in range(widest) if index != skip]
    for index in candidates:
        values = [row[index] for row in rows if index < len(row)]
        numeric_values = [value for value in values if _parse_positive_number(value) is not None]
        if numeric_values:
            return index
    return 1 if skip == 0 else 0


def _parse_positive_number(value: str) -> float | None:
    match = re.search(r"[0-9]+(?:\.[0-9]+)?", value or "")
    if not match:
        return None
    parsed = float(match.group(0))
    if parsed <= 0:
        return None
    return parsed


def _is_fresh(path: Path, ttl_hours: int) -> bool:
    if not path.exists():
        return False
    max_age_seconds = ttl_hours * 3600
    age = time.time() - path.stat().st_mtime
    return age <= max_age_seconds


def _meta_source_url(meta: dict[str, object] | None) -> str | None:
    if not meta:
        return None
    raw = meta.get("sourceUrl")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return None


def _read_json(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return None
    if isinstance(data, dict):
        return data
    return None


def _write_json(path: Path, payload: dict[str, object]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=True, indent=2, sort_keys=True)
