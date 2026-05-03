from __future__ import annotations

import csv
import io
import json
import re
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from .config import AddonConfig
from .jiten_lists import get_frequency_list_definition
from .normalization import normalize_lookup_text
from .state import addon_dir, ensure_user_files_dir

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
    source_kind: str = "none"

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
    *,
    force_refresh: bool = False,
) -> FrequencyLookup:
    opener = opener or _default_fetch_text
    frequency_list = get_frequency_list_definition(config.jiten_frequency_list_id)
    user_dir = ensure_user_files_dir()
    cache_path = _cache_path(user_dir, frequency_list.id)
    meta_path = _meta_path(user_dir, frequency_list.id)
    _migrate_legacy_visual_novel_cache(user_dir, frequency_list.id, cache_path, meta_path)
    warnings: list[str] = []

    meta = _read_json(meta_path)
    cache_is_fresh = _is_fresh(cache_path, config.jiten_cache_ttl_hours)
    skip_cache_fallback = False

    if cache_is_fresh and not force_refresh:
        try:
            return FrequencyLookup(
                ranks=parse_frequency_csv(cache_path.read_text(encoding="utf-8")),
                source_url=_meta_source_url(meta),
                warnings=tuple(),
                source_kind="cache",
            )
        except (OSError, UnicodeDecodeError, FrequencyParseError) as error:
            warnings.append(f"Ignoring an invalid cached Jiten frequency list: {error}")
            skip_cache_fallback = True

    lookup = _refresh_from_remote_sources(
        config,
        frequency_list.label,
        warnings,
        meta_path,
        cache_path,
        meta,
        opener,
    )
    if lookup is not None:
        return lookup

    if cache_path.exists() and not skip_cache_fallback:
        try:
            if cache_is_fresh:
                warnings.append(
                    f"Using the cached Jiten {frequency_list.label} CSV."
                )
            else:
                warnings.append(
                    f"Using a stale cached Jiten {frequency_list.label} CSV."
                )
            return FrequencyLookup(
                ranks=parse_frequency_csv(cache_path.read_text(encoding="utf-8")),
                source_url=_meta_source_url(meta),
                warnings=tuple(warnings),
                source_kind="cache",
            )
        except (OSError, UnicodeDecodeError, FrequencyParseError) as error:
            warnings.append(f"Could not read stale Jiten cache: {error}")

    bundled_lookup = _load_bundled_snapshot(frequency_list.id, frequency_list.label, warnings)
    if bundled_lookup is not None:
        return bundled_lookup

    warnings.append(
        f"Jiten {frequency_list.label} CSV is unavailable; "
        "falling back to Kiku FreqSort only."
    )
    return FrequencyLookup(
        ranks={},
        source_url=None,
        warnings=tuple(warnings),
        source_kind="none",
    )


def refresh_frequency_lookup(
    config: AddonConfig,
    opener: Callable[[str, int], str] | None = None,
) -> FrequencyLookup:
    return load_frequency_lookup(config, opener=opener, force_refresh=True)


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


def bundled_frequency_path(list_id: str) -> Path | None:
    frequency_list = get_frequency_list_definition(list_id)
    if not frequency_list.bundled_snapshot_name:
        return None
    return addon_dir() / "data" / frequency_list.bundled_snapshot_name


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


def _refresh_from_remote_sources(
    config: AddonConfig,
    frequency_list_label: str,
    warnings: list[str],
    meta_path: Path,
    cache_path: Path,
    meta: dict[str, object] | None,
    opener: Callable[[str, int], str],
) -> FrequencyLookup | None:
    urls = _configured_csv_urls(config, meta)
    attempted_urls: set[str] = set()

    for csv_url in urls:
        attempted_urls.add(csv_url)
        lookup = _fetch_remote_lookup(
            csv_url,
            config,
            frequency_list_label,
            warnings,
            meta_path,
            cache_path,
            opener,
        )
        if lookup is not None:
            return lookup

    return None


def _configured_csv_urls(
    config: AddonConfig,
    meta: dict[str, object] | None,
) -> list[str]:
    urls: list[str] = []
    selected_list = get_frequency_list_definition(config.jiten_frequency_list_id)
    for candidate in (
        config.jiten_vn_csv_url,
        selected_list.csv_url,
        _meta_source_url(meta),
    ):
        cleaned = candidate.strip() if isinstance(candidate, str) else ""
        if cleaned and cleaned not in urls:
            urls.append(cleaned)
    return urls


def _fetch_remote_lookup(
    csv_url: str,
    config: AddonConfig,
    frequency_list_label: str,
    warnings: list[str],
    meta_path: Path,
    cache_path: Path,
    opener: Callable[[str, int], str],
) -> FrequencyLookup | None:
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
            source_kind="remote",
        )
    except Exception as error:  # pragma: no cover - best effort network path
        warnings.append(
            f"Could not refresh the Jiten {frequency_list_label} CSV "
            f"from {csv_url}: {error}"
        )
        return None


def _load_bundled_snapshot(
    list_id: str,
    frequency_list_label: str,
    warnings: list[str],
) -> FrequencyLookup | None:
    snapshot_path = bundled_frequency_path(list_id)
    if snapshot_path is None or not snapshot_path.exists():
        return None
    try:
        warnings.append(
            f"Using the bundled Jiten {frequency_list_label} CSV snapshot."
        )
        return FrequencyLookup(
            ranks=parse_frequency_csv(snapshot_path.read_text(encoding="utf-8")),
            source_url=f"bundled://{snapshot_path.name}",
            warnings=tuple(warnings),
            source_kind="bundled",
        )
    except (OSError, UnicodeDecodeError, FrequencyParseError) as error:
        warnings.append(f"Could not read the bundled Jiten snapshot: {error}")
        return None


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


def _cache_path(user_dir: Path, list_id: str) -> Path:
    return user_dir / f"jiten_frequency_{list_id}.csv"


def _meta_path(user_dir: Path, list_id: str) -> Path:
    return user_dir / f"jiten_frequency_{list_id}_meta.json"


def _migrate_legacy_visual_novel_cache(
    user_dir: Path,
    list_id: str,
    cache_path: Path,
    meta_path: Path,
) -> None:
    if list_id != "visual_novel":
        return

    legacy_cache_path = user_dir / "jiten_vn_frequency.csv"
    legacy_meta_path = user_dir / "jiten_vn_frequency_meta.json"

    if not cache_path.exists() and legacy_cache_path.exists():
        try:
            shutil.copy2(legacy_cache_path, cache_path)
        except OSError:
            pass

    if not meta_path.exists() and legacy_meta_path.exists():
        try:
            shutil.copy2(legacy_meta_path, meta_path)
        except OSError:
            pass


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
