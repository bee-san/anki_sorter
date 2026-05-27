from __future__ import annotations

import io
import json
import hashlib
import re
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qs, urljoin, urlparse
from urllib.request import Request, urlopen

from .normalization import normalize_lookup_text

TERM_META_BANK_RE = re.compile(r"^term_meta_bank_\d+\.json$")
DISPLAY_RANK_RE = re.compile(r"#\s*([0-9][0-9,]*(?:\.[0-9]+)?)")
NUMBER_RE = re.compile(r"[-+]?[0-9][0-9,]*(?:\.[0-9]+)?")
MAX_ZIP_BYTES = 50 * 1024 * 1024
MAX_DECOMPRESSED_JSON_BYTES = 250 * 1024 * 1024


@dataclass(frozen=True)
class YomitanFrequencyIndex:
    title: str | None
    download_url: str | None
    index_url: str | None
    revision: str | None
    frequency_mode: str | None


@dataclass(frozen=True)
class ParsedYomitanFrequency:
    ranks: dict[str, float]
    title: str | None
    revision: str | None
    frequency_mode: str | None
    value_kind: str


@dataclass(frozen=True)
class YomitanLoadResult:
    ranks: dict[str, float]
    title: str | None
    source_url: str | None
    download_url: str | None
    revision: str | None
    warnings: tuple[str, ...]
    source_kind: str


class YomitanFrequencyParseError(ValueError):
    pass


class YomitanLoadError(ValueError):
    pass


def load_yomitan_frequency_lookup(
    index_url: str,
    user_dir: Path,
    timeout_seconds: int,
    cache_ttl_hours: int,
    opener: Callable[[str, int], bytes] | None = None,
    bundled_zip_path: Path | None = None,
    *,
    force_refresh: bool = False,
) -> YomitanLoadResult:
    index_url = index_url.strip()
    _validate_http_url(index_url)
    opener = opener or _default_fetch_bytes
    user_dir.mkdir(parents=True, exist_ok=True)
    cache_path, meta_path = _cache_paths(user_dir, index_url)
    meta = _read_json(meta_path)
    warnings: list[str] = []

    if cache_path.exists() and _is_fresh(cache_path, cache_ttl_hours) and not force_refresh:
        try:
            return _load_cached_yomitan(cache_path, meta, index_url, warnings=tuple())
        except Exception as cache_error:
            warnings.append(
                "Ignoring an invalid cached Yomitan frequency dictionary: "
                f"{cache_error}"
            )

    try:
        fetched = opener(index_url, timeout_seconds)
        _enforce_zip_download_limit(fetched)
        zip_bytes, index = _resolve_yomitan_zip_bytes(
            fetched,
            index_url=index_url,
            timeout_seconds=timeout_seconds,
            opener=opener,
        )
        parsed = parse_yomitan_frequency_zip(
            zip_bytes,
            source_url=index_url,
            frequency_mode=index.frequency_mode,
        )
        _write_bytes_atomic(cache_path, zip_bytes)
        resolved_download_url = index.download_url or index_url
        _write_json(
            meta_path,
            {
                "indexUrl": index_url,
                "downloadUrl": resolved_download_url,
                "title": index.title or parsed.title,
                "revision": index.revision or parsed.revision,
                "frequencyMode": index.frequency_mode or parsed.frequency_mode,
                "fetchedAt": time.time(),
                "entryCount": len(parsed.ranks),
            },
        )
        return YomitanLoadResult(
            ranks=parsed.ranks,
            title=index.title or parsed.title,
            source_url=index_url,
            download_url=resolved_download_url,
            revision=index.revision or parsed.revision,
            warnings=tuple(warnings),
            source_kind="remote",
        )
    except Exception as error:
        cache_error: Exception | None = None
        if cache_path.exists():
            try:
                return _load_cached_yomitan(
                    cache_path,
                    meta,
                    index_url,
                    warnings=tuple(
                        [
                            *warnings,
                            f"Using stale cached Yomitan frequency dictionary after refresh failed: {error}",
                        ]
                    ),
                )
            except Exception as error_from_cache:
                cache_error = error_from_cache
                warnings.append(
                    "Ignoring an invalid stale cached Yomitan frequency dictionary: "
                    f"{cache_error}"
                )
        if bundled_zip_path is not None and bundled_zip_path.exists():
            try:
                return _load_bundled_yomitan(
                    bundled_zip_path,
                    index_url,
                    warnings=tuple(
                        [
                            *warnings,
                            "Using the bundled Bee Yomitan frequency dictionary "
                            f"after refresh failed: {error}",
                        ]
                    ),
                )
            except Exception as bundled_error:
                warnings.append(
                    "Could not load the bundled Bee Yomitan frequency dictionary: "
                    f"{bundled_error}"
                )
        if isinstance(error, YomitanLoadError):
            raise
        if cache_error is not None:
            raise YomitanLoadError(
                f"Could not refresh Yomitan frequency dictionary ({error}); "
                f"stale cache was invalid ({cache_error})."
            ) from cache_error
        raise YomitanLoadError(f"Could not load Yomitan frequency dictionary: {error}") from error


def parse_yomitan_index_json(text: str, source_url: str) -> YomitanFrequencyIndex:
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as error:
        raise YomitanFrequencyParseError(f"Invalid Yomitan index JSON: {error}") from error
    if not isinstance(raw, dict):
        raise YomitanFrequencyParseError("Yomitan index JSON must be an object.")
    return _parse_index_object(raw, source_url=source_url)


def parse_yomitan_frequency_zip(
    zip_bytes: bytes,
    *,
    source_url: str = "",
    frequency_mode: str | None = None,
) -> ParsedYomitanFrequency:
    _enforce_zip_download_limit(zip_bytes)
    try:
        archive = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile as error:
        raise YomitanFrequencyParseError("Expected a valid Yomitan zip file.") from error

    with archive:
        _enforce_archive_json_limit(archive)
        index = _read_zip_index(archive, source_url=source_url)
        candidates: list[_FrequencyCandidate] = []
        for name in archive.namelist():
            if "/" in name or not TERM_META_BANK_RE.fullmatch(name):
                continue
            candidates.extend(_read_bank_candidates(archive, name))

    if not candidates:
        raise YomitanFrequencyParseError("No usable frequency rows were found in the Yomitan zip.")

    effective_frequency_mode = index.frequency_mode or frequency_mode
    ranks, value_kind = _candidates_to_ranks(
        candidates,
        frequency_mode=effective_frequency_mode,
        source_url=source_url or index.index_url or "",
    )
    if not ranks:
        raise YomitanFrequencyParseError("No usable frequency rows were found in the Yomitan zip.")

    return ParsedYomitanFrequency(
        ranks=ranks,
        title=index.title,
        revision=index.revision,
        frequency_mode=effective_frequency_mode,
        value_kind=value_kind,
    )


def _default_fetch_bytes(url: str, timeout_seconds: int) -> bytes:
    _validate_http_url(url)
    request = Request(
        url,
        headers={
            "User-Agent": "anki-vn-sorter/1.0",
            "Accept": "application/json,application/zip,*/*",
        },
    )
    with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
        return response.read(MAX_ZIP_BYTES + 1)


def _resolve_yomitan_zip_bytes(
    fetched: bytes,
    *,
    index_url: str,
    timeout_seconds: int,
    opener: Callable[[str, int], bytes],
) -> tuple[bytes, YomitanFrequencyIndex]:
    if _looks_like_zip(fetched):
        return fetched, YomitanFrequencyIndex(
            title=None,
            download_url=index_url,
            index_url=index_url,
            revision=None,
            frequency_mode=None,
        )

    try:
        text = fetched.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise YomitanLoadError("Yomitan response was neither zip bytes nor UTF-8 index JSON.") from error

    index = parse_yomitan_index_json(text, index_url)
    if not index.download_url:
        raise YomitanLoadError("Yomitan index JSON did not include downloadUrl.")
    download_url = urljoin(index_url, index.download_url)
    _validate_http_url(download_url)
    zip_bytes = opener(download_url, timeout_seconds)
    _enforce_zip_download_limit(zip_bytes)
    if not _looks_like_zip(zip_bytes):
        raise YomitanLoadError("Yomitan downloadUrl did not return zip bytes.")
    return zip_bytes, YomitanFrequencyIndex(
        title=index.title,
        download_url=download_url,
        index_url=index.index_url,
        revision=index.revision,
        frequency_mode=index.frequency_mode,
    )


def _load_cached_yomitan(
    cache_path: Path,
    meta: dict[str, object] | None,
    index_url: str,
    *,
    warnings: tuple[str, ...],
) -> YomitanLoadResult:
    parsed = parse_yomitan_frequency_zip(
        cache_path.read_bytes(),
        source_url=index_url,
        frequency_mode=_meta_string(meta, "frequencyMode"),
    )
    return YomitanLoadResult(
        ranks=parsed.ranks,
        title=_meta_string(meta, "title") or parsed.title,
        source_url=_meta_string(meta, "indexUrl") or index_url,
        download_url=_meta_string(meta, "downloadUrl") or index_url,
        revision=_meta_string(meta, "revision") or parsed.revision,
        warnings=warnings,
        source_kind="cache",
    )


def _load_bundled_yomitan(
    bundled_zip_path: Path,
    index_url: str,
    *,
    warnings: tuple[str, ...],
) -> YomitanLoadResult:
    parsed = parse_yomitan_frequency_zip(
        bundled_zip_path.read_bytes(),
        source_url=index_url,
    )
    return YomitanLoadResult(
        ranks=parsed.ranks,
        title=parsed.title,
        source_url=index_url,
        download_url=None,
        revision=parsed.revision,
        warnings=warnings,
        source_kind="bundled",
    )


def _cache_paths(user_dir: Path, index_url: str) -> tuple[Path, Path]:
    digest = hashlib.sha256(index_url.encode("utf-8")).hexdigest()[:12]
    stem = f"yomitan_frequency_{digest}"
    return user_dir / f"{stem}.zip", user_dir / f"{stem}_meta.json"


def _validate_http_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise YomitanLoadError("Only http and https Yomitan URLs are supported.")
    if not parsed.netloc:
        raise YomitanLoadError("Yomitan URL must include a host.")


def _looks_like_zip(data: bytes) -> bool:
    return data.startswith(b"PK")


def _enforce_zip_download_limit(data: bytes) -> None:
    if len(data) > MAX_ZIP_BYTES:
        raise YomitanLoadError("Yomitan zip exceeded the 50 MB download limit.")


def _enforce_archive_json_limit(archive: zipfile.ZipFile) -> None:
    total = 0
    for info in archive.infolist():
        if info.filename == "index.json" or TERM_META_BANK_RE.fullmatch(info.filename):
            total += info.file_size
    if total > MAX_DECOMPRESSED_JSON_BYTES:
        raise YomitanFrequencyParseError("Yomitan frequency JSON exceeded the 250 MB decompressed limit.")


def _read_json(path: Path) -> dict[str, object] | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def _write_bytes_atomic(path: Path, data: bytes) -> None:
    temp_path = path.with_name(f".{path.name}.tmp")
    temp_path.write_bytes(data)
    temp_path.replace(path)


def _write_json(path: Path, data: dict[str, object]) -> None:
    payload = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)
    temp_path = path.with_name(f".{path.name}.tmp")
    temp_path.write_text(payload, encoding="utf-8")
    temp_path.replace(path)


def _is_fresh(path: Path, ttl_hours: int) -> bool:
    if not path.exists():
        return False
    max_age_seconds = ttl_hours * 3600
    age = time.time() - path.stat().st_mtime
    return age <= max_age_seconds


def _meta_string(meta: dict[str, object] | None, key: str) -> str | None:
    if not meta:
        return None
    value = meta.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


@dataclass(frozen=True)
class _FrequencyCandidate:
    term: str
    display_rank: float | None
    numeric_value: float | None


def _parse_index_object(raw: dict[str, object], *, source_url: str) -> YomitanFrequencyIndex:
    return YomitanFrequencyIndex(
        title=_optional_string(raw.get("title")),
        download_url=_optional_string(raw.get("downloadUrl")),
        index_url=_optional_string(raw.get("indexUrl")) or (source_url or None),
        revision=_optional_string(raw.get("revision")),
        frequency_mode=_optional_string(raw.get("frequencyMode")),
    )


def _read_zip_index(archive: zipfile.ZipFile, *, source_url: str) -> YomitanFrequencyIndex:
    try:
        raw = json.loads(archive.read("index.json").decode("utf-8-sig"))
    except KeyError:
        raw = {}
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise YomitanFrequencyParseError(f"Invalid Yomitan index.json: {error}") from error
    if not isinstance(raw, dict):
        raise YomitanFrequencyParseError("Yomitan index.json must be an object.")
    return _parse_index_object(raw, source_url=source_url)


def _read_bank_candidates(archive: zipfile.ZipFile, name: str) -> list[_FrequencyCandidate]:
    try:
        raw = json.loads(archive.read(name).decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise YomitanFrequencyParseError(f"Invalid Yomitan bank {name}: {error}") from error
    if not isinstance(raw, list):
        return []

    candidates: list[_FrequencyCandidate] = []
    for row in raw:
        candidate = _row_to_candidate(row)
        if candidate is not None:
            candidates.append(candidate)
    return candidates


def _row_to_candidate(row: object) -> _FrequencyCandidate | None:
    if not isinstance(row, list) or len(row) < 3:
        return None
    if row[1] != "freq":
        return None
    if not isinstance(row[0], str):
        return None
    term = normalize_lookup_text(row[0])
    if not term:
        return None
    payload = row[2]
    display_rank = _extract_display_rank(payload)
    numeric_value = _extract_numeric_value(payload)
    if display_rank is None and numeric_value is None:
        return None
    return _FrequencyCandidate(term, display_rank, numeric_value)


def _candidates_to_ranks(
    candidates: list[_FrequencyCandidate],
    *,
    frequency_mode: str | None,
    source_url: str,
) -> tuple[dict[str, float], str]:
    if _should_prefer_display_rank(candidates, frequency_mode=frequency_mode, source_url=source_url):
        ranks = _display_rank_lookup(candidates)
        if ranks:
            return ranks, "display_rank"

    normalized_mode = (frequency_mode or "").strip().lower()
    if normalized_mode == "rank-based":
        ranks = _numeric_rank_lookup(candidates)
        if ranks:
            return ranks, "rank_value"

    ranks = _occurrence_rank_lookup(candidates)
    if ranks:
        return ranks, "occurrence_value_converted"

    ranks = _display_rank_lookup(candidates)
    if ranks:
        return ranks, "display_rank"

    return {}, "occurrence_value_converted"


def _should_prefer_display_rank(
    candidates: list[_FrequencyCandidate],
    *,
    frequency_mode: str | None,
    source_url: str,
) -> bool:
    display_count = sum(1 for candidate in candidates if candidate.display_rank is not None)
    if display_count == 0:
        return False
    if _is_character_dictionary_rank_url(source_url):
        return True
    numeric_count = sum(1 for candidate in candidates if candidate.numeric_value is not None)
    normalized_mode = (frequency_mode or "").strip().lower()
    return normalized_mode != "rank-based" and display_count >= max(1, numeric_count)


def _is_character_dictionary_rank_url(source_url: str) -> bool:
    parsed = urlparse(source_url or "")
    host = (parsed.netloc or "").lower()
    if "characterdictionary.tokyo" not in host:
        return False
    display_mode = parse_qs(parsed.query).get("display_mode", [""])[0].lower()
    return display_mode == "rank"


def _display_rank_lookup(candidates: list[_FrequencyCandidate]) -> dict[str, float]:
    ranks: dict[str, float] = {}
    for candidate in candidates:
        if candidate.display_rank is None:
            continue
        _set_best_rank(ranks, candidate.term, candidate.display_rank)
    return ranks


def _numeric_rank_lookup(candidates: list[_FrequencyCandidate]) -> dict[str, float]:
    ranks: dict[str, float] = {}
    for candidate in candidates:
        if candidate.numeric_value is None:
            continue
        _set_best_rank(ranks, candidate.term, candidate.numeric_value)
    return ranks


def _occurrence_rank_lookup(candidates: list[_FrequencyCandidate]) -> dict[str, float]:
    best_values_by_term: dict[str, float] = {}
    for candidate in candidates:
        if candidate.numeric_value is None or candidate.numeric_value <= 0:
            continue
        previous = best_values_by_term.get(candidate.term)
        if previous is None or candidate.numeric_value > previous:
            best_values_by_term[candidate.term] = candidate.numeric_value

    scored = sorted(
        best_values_by_term.items(),
        key=lambda item: (-item[1], item[0]),
    )
    return {term: float(index) for index, (term, _value) in enumerate(scored, start=1)}


def _set_best_rank(ranks: dict[str, float], term: str, rank: float) -> None:
    previous = ranks.get(term)
    if previous is None or rank < previous:
        ranks[term] = rank


def _extract_display_rank(payload: object) -> float | None:
    for value in _display_value_candidates(payload):
        match = DISPLAY_RANK_RE.search(value)
        if not match:
            continue
        rank = _parse_positive_number(match.group(1))
        if rank is not None:
            return rank
    return None


def _display_value_candidates(payload: object) -> list[str]:
    candidates: list[str] = []
    if isinstance(payload, str):
        candidates.append(payload)
    if isinstance(payload, dict):
        display_value = payload.get("displayValue")
        if isinstance(display_value, str):
            candidates.append(display_value)
        frequency = payload.get("frequency")
        if isinstance(frequency, str):
            candidates.append(frequency)
        if isinstance(frequency, dict):
            nested_display_value = frequency.get("displayValue")
            if isinstance(nested_display_value, str):
                candidates.append(nested_display_value)
    return candidates


def _extract_numeric_value(payload: object) -> float | None:
    if isinstance(payload, int | float):
        return _positive_float(payload)
    if isinstance(payload, str):
        return _parse_positive_number(payload)
    if not isinstance(payload, dict):
        return None

    value = _value_to_number(payload.get("value"))
    if value is not None:
        return value

    frequency = payload.get("frequency")
    if isinstance(frequency, dict):
        return _value_to_number(frequency.get("value"))
    return _value_to_number(frequency)


def _value_to_number(value: object) -> float | None:
    if isinstance(value, int | float):
        return _positive_float(value)
    if isinstance(value, str):
        return _parse_positive_number(value)
    return None


def _parse_positive_number(text: str) -> float | None:
    match = NUMBER_RE.search(text.replace(",", ""))
    if not match:
        return None
    try:
        return _positive_float(float(match.group(0)))
    except ValueError:
        return None


def _positive_float(value: int | float) -> float | None:
    number = float(value)
    if number <= 0:
        return None
    return number


def _optional_string(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None
