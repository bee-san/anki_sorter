from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .jiten_lists import (
    DEFAULT_JITEN_FREQUENCY_LIST_ID,
    LEGACY_DEFAULT_VN_CSV_URL,
    frequency_list_ids,
)

DEFAULT_MODEL_NAMES = ("Kiku",)
DEFAULT_SCOPE_QUERY = "note:Kiku is:new -is:suspended"
LEGACY_DEFAULT_MATURE_QUERY = "note:Kiku prop:ivl>=21 -is:suspended"
DEFAULT_MATURE_QUERY = ""
DEFAULT_MATURE_DAYS = 21
DEFAULT_HTTP_PORT = 8767
STRATEGY_FREQUENCY_FIRST_SOFT_V1 = "frequency_first_soft_v1"
STRATEGY_EASY_FIRST_TIERED_V1 = "easy_first_tiered_v1"
STRATEGY_BALANCED_EASE_V1 = "balanced_ease_v1"
DEFAULT_STRATEGY = STRATEGY_FREQUENCY_FIRST_SOFT_V1
AUTO_SORT_MODE_MANUAL_ONLY = "manual_only"
AUTO_SORT_MODE_AFTER_SYNC = "after_sync"
AUTO_SORT_MODE_PROFILE_OPEN = "profile_open"
DEFAULT_AUTO_SORT_MODE = AUTO_SORT_MODE_AFTER_SYNC
DEFAULT_JITEN_DISCOVERY_URL = "https://jiten.moe/other"
DEFAULT_JITEN_FREQUENCY_LIST = DEFAULT_JITEN_FREQUENCY_LIST_ID
DEFAULT_JITEN_VN_CSV_URL = ""
DEFAULT_JITEN_CACHE_TTL_HOURS = 24
DEFAULT_JITEN_REQUEST_TIMEOUT_SECONDS = 20
DEFAULT_EXPRESSION_FIELD = "Expression"
DEFAULT_READING_FIELD = "ExpressionReading"
DEFAULT_FREQSORT_FIELD = "FreqSort"
TIER_KANA_ONLY = "kana_only"
TIER_ALL_KANJI_KNOWN = "all_kanji_known"
TIER_ONE_UNKNOWN_KANJI = "one_unknown_kanji"
TIER_TWO_UNKNOWN_KANJI = "two_unknown_kanji"
TIER_THREE_PLUS_UNKNOWN_KANJI = "three_plus_unknown_kanji"
LEGACY_DEFAULT_TIER_ORDER = (
    TIER_KANA_ONLY,
    TIER_ALL_KANJI_KNOWN,
    TIER_ONE_UNKNOWN_KANJI,
    TIER_TWO_UNKNOWN_KANJI,
    TIER_THREE_PLUS_UNKNOWN_KANJI,
)
DEFAULT_TIER_ORDER = (
    TIER_ALL_KANJI_KNOWN,
    TIER_KANA_ONLY,
    TIER_ONE_UNKNOWN_KANJI,
    TIER_TWO_UNKNOWN_KANJI,
    TIER_THREE_PLUS_UNKNOWN_KANJI,
)
VALID_TIER_LABELS = set(DEFAULT_TIER_ORDER)
DEFAULT_PREFER_SHORTER_EXPRESSIONS = True
DEFAULT_FREQSORT_WEIGHT = 0.7
DEFAULT_KANA_ONLY_MULTIPLIER = 0.92
DEFAULT_UNKNOWN_KANJI_PENALTY_STEP = 0.18
DEFAULT_UNKNOWN_KANJI_PENALTY_CAP = 0.54
DEFAULT_PARTIAL_KNOWN_COVERAGE_BONUS = 0.04
VALID_STRATEGIES = {
    STRATEGY_FREQUENCY_FIRST_SOFT_V1,
    STRATEGY_EASY_FIRST_TIERED_V1,
    STRATEGY_BALANCED_EASE_V1,
}
VALID_AUTO_SORT_MODES = {
    AUTO_SORT_MODE_MANUAL_ONLY,
    AUTO_SORT_MODE_AFTER_SYNC,
    AUTO_SORT_MODE_PROFILE_OPEN,
}


class ConfigValidationError(ValueError):
    def __init__(self, messages: list[str]) -> None:
        super().__init__("\n".join(messages))
        self.messages = messages


@dataclass(frozen=True)
class AddonConfig:
    model_names: tuple[str, ...] = DEFAULT_MODEL_NAMES
    scope_query: str = DEFAULT_SCOPE_QUERY
    mature_query: str = DEFAULT_MATURE_QUERY
    mature_days: int = DEFAULT_MATURE_DAYS
    http_port: int = DEFAULT_HTTP_PORT
    strategy: str = DEFAULT_STRATEGY
    auto_sort_mode: str = DEFAULT_AUTO_SORT_MODE
    jiten_discovery_url: str = DEFAULT_JITEN_DISCOVERY_URL
    jiten_frequency_list_id: str = DEFAULT_JITEN_FREQUENCY_LIST
    jiten_vn_csv_url: str = DEFAULT_JITEN_VN_CSV_URL
    jiten_cache_ttl_hours: int = DEFAULT_JITEN_CACHE_TTL_HOURS
    jiten_request_timeout_seconds: int = DEFAULT_JITEN_REQUEST_TIMEOUT_SECONDS
    expression_field: str = DEFAULT_EXPRESSION_FIELD
    reading_field: str = DEFAULT_READING_FIELD
    freqsort_field: str = DEFAULT_FREQSORT_FIELD
    tier_order: tuple[str, ...] = DEFAULT_TIER_ORDER
    prefer_shorter_expressions: bool = DEFAULT_PREFER_SHORTER_EXPRESSIONS
    freqsort_weight: float = DEFAULT_FREQSORT_WEIGHT
    kana_only_multiplier: float = DEFAULT_KANA_ONLY_MULTIPLIER
    unknown_kanji_penalty_step: float = DEFAULT_UNKNOWN_KANJI_PENALTY_STEP
    unknown_kanji_penalty_cap: float = DEFAULT_UNKNOWN_KANJI_PENALTY_CAP
    partial_known_coverage_bonus: float = DEFAULT_PARTIAL_KNOWN_COVERAGE_BONUS

    def to_dict(self) -> dict[str, Any]:
        return {
            "modelNames": list(self.model_names),
            "scopeQuery": self.scope_query,
            "matureQuery": self.mature_query,
            "matureDays": self.mature_days,
            "httpPort": self.http_port,
            "strategy": self.strategy,
            "autoSortMode": self.auto_sort_mode,
            "jitenDiscoveryUrl": self.jiten_discovery_url,
            "jitenFrequencyListId": self.jiten_frequency_list_id,
            "jitenVnCsvUrl": self.jiten_vn_csv_url,
            "jitenCacheTtlHours": self.jiten_cache_ttl_hours,
            "jitenRequestTimeoutSeconds": self.jiten_request_timeout_seconds,
            "expressionField": self.expression_field,
            "readingField": self.reading_field,
            "freqSortField": self.freqsort_field,
            "tierOrder": list(self.tier_order),
            "preferShorterExpressions": self.prefer_shorter_expressions,
            "freqSortWeight": self.freqsort_weight,
            "kanaOnlyMultiplier": self.kana_only_multiplier,
            "unknownKanjiPenaltyStep": self.unknown_kanji_penalty_step,
            "unknownKanjiPenaltyCap": self.unknown_kanji_penalty_cap,
            "partialKnownCoverageBonus": self.partial_known_coverage_bonus,
        }

    @property
    def effective_mature_query(self) -> str:
        if self.mature_query:
            return self.mature_query
        return build_default_mature_query(self.model_names, self.mature_days)


def addon_module_name() -> str:
    return __name__.split(".")[0]


def load_raw_config() -> dict[str, Any]:
    from aqt import mw

    raw = mw.addonManager.getConfig(addon_module_name())
    if isinstance(raw, dict):
        return dict(raw)
    return {}


def load_config() -> AddonConfig:
    return parse_config(load_raw_config())


def parse_config(raw: Mapping[str, Any] | None) -> AddonConfig:
    raw = raw or {}
    errors: list[str] = []

    model_names = _coerce_model_names(raw.get("modelNames"), errors)
    scope_query = _clean_string(raw.get("scopeQuery"), DEFAULT_SCOPE_QUERY)
    mature_query = _coerce_mature_query(raw.get("matureQuery"), model_names)
    strategy = _coerce_strategy(raw)
    auto_sort_mode = _clean_string(raw.get("autoSortMode"), DEFAULT_AUTO_SORT_MODE)
    jiten_discovery_url = _clean_string(
        raw.get("jitenDiscoveryUrl"), DEFAULT_JITEN_DISCOVERY_URL
    )
    jiten_frequency_list_id = _coerce_jiten_frequency_list_id(
        raw.get("jitenFrequencyListId")
    )
    jiten_vn_csv_url = _coerce_jiten_vn_csv_url(raw.get("jitenVnCsvUrl"))
    expression_field = _clean_string(
        raw.get("expressionField"), DEFAULT_EXPRESSION_FIELD
    )
    reading_field = _clean_string(raw.get("readingField"), DEFAULT_READING_FIELD)
    freqsort_field = _clean_string(raw.get("freqSortField"), DEFAULT_FREQSORT_FIELD)
    tier_order = _coerce_tier_order(raw.get("tierOrder"), errors)
    prefer_shorter_expressions = _coerce_bool(
        raw.get("preferShorterExpressions"),
        DEFAULT_PREFER_SHORTER_EXPRESSIONS,
        "preferShorterExpressions",
        errors,
    )

    mature_days = _coerce_positive_int(
        raw.get("matureDays"), DEFAULT_MATURE_DAYS, "matureDays", errors
    )
    http_port = _coerce_positive_int(
        raw.get("httpPort"), DEFAULT_HTTP_PORT, "httpPort", errors
    )
    cache_ttl_hours = _coerce_positive_int(
        raw.get("jitenCacheTtlHours"),
        DEFAULT_JITEN_CACHE_TTL_HOURS,
        "jitenCacheTtlHours",
        errors,
    )
    request_timeout_seconds = _coerce_positive_int(
        raw.get("jitenRequestTimeoutSeconds"),
        DEFAULT_JITEN_REQUEST_TIMEOUT_SECONDS,
        "jitenRequestTimeoutSeconds",
        errors,
    )
    freqsort_weight = _coerce_float_in_range(
        raw.get("freqSortWeight"),
        DEFAULT_FREQSORT_WEIGHT,
        "freqSortWeight",
        minimum=0.0,
        maximum=1.0,
        errors=errors,
    )
    kana_only_multiplier = _coerce_float_in_range(
        raw.get("kanaOnlyMultiplier"),
        DEFAULT_KANA_ONLY_MULTIPLIER,
        "kanaOnlyMultiplier",
        minimum=0.0,
        maximum=1.0,
        errors=errors,
    )
    unknown_kanji_penalty_step = _coerce_float_in_range(
        raw.get("unknownKanjiPenaltyStep"),
        DEFAULT_UNKNOWN_KANJI_PENALTY_STEP,
        "unknownKanjiPenaltyStep",
        minimum=0.0,
        maximum=1.0,
        errors=errors,
    )
    unknown_kanji_penalty_cap = _coerce_float_in_range(
        raw.get("unknownKanjiPenaltyCap"),
        DEFAULT_UNKNOWN_KANJI_PENALTY_CAP,
        "unknownKanjiPenaltyCap",
        minimum=0.0,
        maximum=1.0,
        errors=errors,
    )
    partial_known_coverage_bonus = _coerce_float_in_range(
        raw.get("partialKnownCoverageBonus"),
        DEFAULT_PARTIAL_KNOWN_COVERAGE_BONUS,
        "partialKnownCoverageBonus",
        minimum=0.0,
        maximum=1.0,
        errors=errors,
    )

    if http_port > 65535:
        errors.append("httpPort must be between 1 and 65535.")
    if not scope_query:
        errors.append("scopeQuery must be a non-empty string.")
    if strategy not in VALID_STRATEGIES:
        errors.append(
            f"strategy must be one of: {', '.join(sorted(VALID_STRATEGIES))}."
        )
    if auto_sort_mode not in VALID_AUTO_SORT_MODES:
        errors.append(
            "autoSortMode must be one of: "
            + ", ".join(sorted(VALID_AUTO_SORT_MODES))
            + "."
        )
    if not expression_field:
        errors.append("expressionField must be a non-empty string.")
    if not reading_field:
        errors.append("readingField must be a non-empty string.")
    if not freqsort_field:
        errors.append("freqSortField must be a non-empty string.")

    if errors:
        raise ConfigValidationError(errors)

    return AddonConfig(
        model_names=model_names,
        scope_query=scope_query,
        mature_query=mature_query,
        mature_days=mature_days,
        http_port=http_port,
        strategy=strategy,
        auto_sort_mode=auto_sort_mode,
        jiten_discovery_url=jiten_discovery_url,
        jiten_frequency_list_id=jiten_frequency_list_id,
        jiten_vn_csv_url=jiten_vn_csv_url,
        jiten_cache_ttl_hours=cache_ttl_hours,
        jiten_request_timeout_seconds=request_timeout_seconds,
        expression_field=expression_field,
        reading_field=reading_field,
        freqsort_field=freqsort_field,
        tier_order=tier_order,
        prefer_shorter_expressions=prefer_shorter_expressions,
        freqsort_weight=freqsort_weight,
        kana_only_multiplier=kana_only_multiplier,
        unknown_kanji_penalty_step=unknown_kanji_penalty_step,
        unknown_kanji_penalty_cap=unknown_kanji_penalty_cap,
        partial_known_coverage_bonus=partial_known_coverage_bonus,
    )


def build_default_mature_query(
    model_names: tuple[str, ...],
    mature_days: int,
) -> str:
    model_query = _build_model_query(model_names)
    base_query = f"prop:ivl>={mature_days} -is:suspended"
    if not model_query:
        return base_query
    return f"({model_query}) {base_query}"


def _coerce_model_names(value: Any, errors: list[str]) -> tuple[str, ...]:
    if value in (None, ""):
        return DEFAULT_MODEL_NAMES
    if not isinstance(value, (list, tuple)):
        errors.append("modelNames must be a list of note type names.")
        return DEFAULT_MODEL_NAMES

    names: list[str] = []
    for entry in value:
        cleaned = _clean_string(entry)
        if cleaned:
            names.append(cleaned)

    if not names:
        errors.append("modelNames must include at least one note type name.")
        return DEFAULT_MODEL_NAMES
    return tuple(names)


def _coerce_mature_query(value: Any, model_names: tuple[str, ...]) -> str:
    cleaned = _clean_string(value, DEFAULT_MATURE_QUERY)
    if not cleaned:
        return ""
    if cleaned == LEGACY_DEFAULT_MATURE_QUERY:
        return ""
    if cleaned == build_default_mature_query(model_names, DEFAULT_MATURE_DAYS):
        return ""
    return cleaned


def _coerce_tier_order(value: Any, errors: list[str]) -> tuple[str, ...]:
    if value in (None, ""):
        return DEFAULT_TIER_ORDER
    if not isinstance(value, (list, tuple)):
        errors.append("tierOrder must be a list of tier labels.")
        return DEFAULT_TIER_ORDER

    cleaned_labels: list[str] = []
    for entry in value:
        cleaned = _clean_string(entry)
        if cleaned:
            cleaned_labels.append(cleaned)

    if set(cleaned_labels) != VALID_TIER_LABELS or len(cleaned_labels) != len(DEFAULT_TIER_ORDER):
        errors.append(
            "tierOrder must contain each tier exactly once: "
            + ", ".join(DEFAULT_TIER_ORDER)
            + "."
        )
        return DEFAULT_TIER_ORDER

    return tuple(cleaned_labels)


def _coerce_strategy(raw: Mapping[str, Any]) -> str:
    cleaned = _clean_string(raw.get("strategy"), DEFAULT_STRATEGY)
    if cleaned == STRATEGY_EASY_FIRST_TIERED_V1 and _should_migrate_default_tiered_strategy(raw):
        return DEFAULT_STRATEGY
    return cleaned


def _should_migrate_default_tiered_strategy(raw: Mapping[str, Any]) -> bool:
    tier_errors: list[str] = []
    tier_order = _coerce_tier_order(raw.get("tierOrder"), tier_errors)
    if tier_errors or tier_order != DEFAULT_TIER_ORDER:
        return False

    prefer_errors: list[str] = []
    prefer_shorter_expressions = _coerce_bool(
        raw.get("preferShorterExpressions"),
        DEFAULT_PREFER_SHORTER_EXPRESSIONS,
        "preferShorterExpressions",
        prefer_errors,
    )
    if prefer_errors or prefer_shorter_expressions != DEFAULT_PREFER_SHORTER_EXPRESSIONS:
        return False

    freqsort_errors: list[str] = []
    freqsort_weight = _coerce_float_in_range(
        raw.get("freqSortWeight"),
        DEFAULT_FREQSORT_WEIGHT,
        "freqSortWeight",
        minimum=0.0,
        maximum=1.0,
        errors=freqsort_errors,
    )
    if freqsort_errors or freqsort_weight != DEFAULT_FREQSORT_WEIGHT:
        return False

    return not any(
        key in raw
        for key in (
            "kanaOnlyMultiplier",
            "unknownKanjiPenaltyStep",
            "unknownKanjiPenaltyCap",
            "partialKnownCoverageBonus",
        )
    )


def _coerce_jiten_frequency_list_id(value: Any) -> str:
    cleaned = _clean_string(value, DEFAULT_JITEN_FREQUENCY_LIST)
    if cleaned in frequency_list_ids():
        return cleaned
    return DEFAULT_JITEN_FREQUENCY_LIST


def _coerce_jiten_vn_csv_url(value: Any) -> str:
    cleaned = _clean_string(value, DEFAULT_JITEN_VN_CSV_URL)
    if cleaned == LEGACY_DEFAULT_VN_CSV_URL:
        return ""
    return cleaned


def _clean_string(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _coerce_positive_int(
    value: Any,
    default: int,
    field_name: str,
    errors: list[str],
) -> int:
    if value in (None, ""):
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        errors.append(f"{field_name} must be a positive integer.")
        return default
    if parsed <= 0:
        errors.append(f"{field_name} must be a positive integer.")
        return default
    return parsed


def _coerce_bool(
    value: Any,
    default: bool,
    field_name: str,
    errors: list[str],
) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    errors.append(f"{field_name} must be true or false.")
    return default


def _coerce_float_in_range(
    value: Any,
    default: float,
    field_name: str,
    minimum: float,
    maximum: float,
    errors: list[str],
) -> float:
    if value in (None, ""):
        return default
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        errors.append(f"{field_name} must be a number between {minimum} and {maximum}.")
        return default
    if parsed < minimum or parsed > maximum:
        errors.append(f"{field_name} must be a number between {minimum} and {maximum}.")
        return default
    return parsed


def _build_model_query(model_names: tuple[str, ...]) -> str:
    parts = [f'note:"{name}"' for name in model_names if name]
    return " or ".join(parts)
