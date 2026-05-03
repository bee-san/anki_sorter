from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from .config import AddonConfig
from .jiten import load_frequency_lookup
from .normalization import extract_kanji_chars, strip_html_text
from .ranking import CardInput, parse_freqsort, score_cards
from .state import ProfileState, load_state, save_state


@dataclass(frozen=True)
class SortSummary:
    applied: bool
    already_sorted: bool
    skipped_for_today: bool
    candidate_count: int
    repositioned_count: int
    strategy: str
    warnings: tuple[str, ...]
    top_preview: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "applied": self.applied,
            "alreadySorted": self.already_sorted,
            "skippedForToday": self.skipped_for_today,
            "candidateCount": self.candidate_count,
            "repositionedCount": self.repositioned_count,
            "strategy": self.strategy,
            "warnings": list(self.warnings),
            "topPreview": list(self.top_preview),
        }


def build_health_snapshot(col: Any, config: AddonConfig) -> dict[str, Any]:
    card_ids = list(map(int, col.find_cards(config.scope_query)))
    deck_warnings = _deck_option_warnings(col, card_ids)
    return {
        "eligibleCardCount": len(card_ids),
        "matureCardCount": len(list(map(int, col.find_cards(config.effective_mature_query)))),
        "warnings": deck_warnings,
    }


def run_sort_on_collection(
    col: Any,
    config: AddonConfig,
    profile_name: str | None,
    *,
    force: bool = False,
) -> dict[str, Any]:
    today = date.today().isoformat()
    state = load_state()
    profile_state = state.for_profile(profile_name)
    previous_summary = profile_state.last_summary if isinstance(profile_state.last_summary, dict) else {}
    if not force and profile_state.last_success_ymd == today:
        summary = SortSummary(
            applied=False,
            already_sorted=True,
            skipped_for_today=True,
            candidate_count=_int_from_summary(previous_summary, "candidateCount"),
            repositioned_count=0,
            strategy=config.strategy,
            warnings=("Anki VN Sorter already completed a run for this profile today.",),
            top_preview=tuple(_top_preview_from_summary(previous_summary)),
        )
        return summary.to_dict()

    warnings: list[str] = []
    lookup = load_frequency_lookup(config)
    warnings.extend(lookup.warnings)

    known_kanji = _build_known_kanji_set(col, config)
    card_ids = list(map(int, col.find_cards(config.scope_query)))
    candidates: list[CardInput] = []
    missing_expression_count = 0

    for card_id in card_ids:
        card = col.get_card(card_id)
        if int(card.type) != 0:
            continue

        model_name = _safe_model_name(card)
        if config.model_names and model_name not in config.model_names:
            continue

        note = card.note()
        expression = _get_note_field(note, config.expression_field)
        if not expression:
            missing_expression_count += 1
            continue

        normalized_expression = strip_html_text(expression).strip()
        kanji_chars = extract_kanji_chars(normalized_expression)
        known_count = sum(1 for char in kanji_chars if char in known_kanji)
        freqsort_rank = parse_freqsort(_get_note_field(note, config.freqsort_field))
        jiten_rank = lookup.rank_for(normalized_expression)
        raw_rank = jiten_rank if jiten_rank is not None else freqsort_rank
        rank_source = "jiten" if jiten_rank is not None else "freqsort" if freqsort_rank is not None else None

        candidates.append(
            CardInput(
                card_id=int(card.id),
                note_id=int(card.nid),
                due=int(card.due),
                card_ord=int(card.ord),
                expression=normalized_expression,
                known_kanji_count=known_count,
                total_kanji_count=len(kanji_chars),
                raw_rank=raw_rank,
                rank_source=rank_source,
            )
        )

    if missing_expression_count:
        warnings.append(
            f"Skipped {missing_expression_count} new cards because the Expression field was empty."
        )

    warnings.extend(_deck_option_warnings(col, [candidate.card_id for candidate in candidates]))

    if not candidates:
        summary = SortSummary(
            applied=False,
            already_sorted=True,
            skipped_for_today=False,
            candidate_count=0,
            repositioned_count=0,
            strategy=config.strategy,
            warnings=tuple(dict.fromkeys(warnings)),
            top_preview=tuple(),
        )
        _persist_summary(profile_name, today, summary)
        return summary.to_dict()

    scored_cards = score_cards(
        candidates,
        strategy=config.strategy,
        tier_order=config.tier_order,
        prefer_shorter_expressions=config.prefer_shorter_expressions,
        freqsort_weight=config.freqsort_weight,
        kana_only_multiplier=config.kana_only_multiplier,
        unknown_kanji_penalty_step=config.unknown_kanji_penalty_step,
        unknown_kanji_penalty_cap=config.unknown_kanji_penalty_cap,
        partial_known_coverage_bonus=config.partial_known_coverage_bonus,
    )
    sorted_card_ids = [scored.card.card_id for scored in scored_cards]
    current_order = [
        candidate.card_id
        for candidate in sorted(candidates, key=lambda card: (card.due, card.card_ord, card.card_id))
    ]
    already_sorted = sorted_card_ids == current_order
    repositioned_count = 0

    if not already_sorted:
        starting_from = min(candidate.due for candidate in candidates)
        result = col.sched.reposition_new_cards(
            card_ids=sorted_card_ids,
            starting_from=starting_from,
            step_size=1,
            randomize=False,
            shift_existing=True,
        )
        repositioned_count = int(getattr(result, "count", len(sorted_card_ids)))

    preview = []
    for scored in scored_cards[:10]:
        preview.append(
            {
                "cardId": scored.card.card_id,
                "noteId": scored.card.note_id,
                "expression": scored.card.expression,
                "easeScore": round(scored.ease_score, 4),
                "coverageScore": round(scored.coverage_score, 4),
                "frequencyScore": round(scored.frequency_score, 4),
                "priorityTier": scored.priority_tier,
                "priorityLabel": scored.priority_label,
                "readabilityMultiplier": round(scored.readability_multiplier, 4),
                "coverageBonus": round(scored.coverage_bonus, 4),
                "unknownPenalty": round(scored.unknown_penalty, 4),
                "unknownKanjiCount": scored.card.unknown_kanji_count,
                "rankSource": scored.card.rank_source,
                "rank": scored.card.raw_rank,
            }
        )

    summary = SortSummary(
        applied=not already_sorted,
        already_sorted=already_sorted,
        skipped_for_today=False,
        candidate_count=len(candidates),
        repositioned_count=repositioned_count,
        strategy=config.strategy,
        warnings=tuple(dict.fromkeys(warnings)),
        top_preview=tuple(preview),
    )
    _persist_summary(profile_name, today, summary)
    return summary.to_dict()


def _persist_summary(profile_name: str | None, today: str, summary: SortSummary) -> None:
    state = load_state()
    updated_state = state.with_profile(
        profile_name,
        ProfileState(last_success_ymd=today, last_summary=summary.to_dict()),
    )
    save_state(updated_state)


def _int_from_summary(summary: dict[str, Any], key: str) -> int:
    raw = summary.get(key)
    if isinstance(raw, int):
        return raw
    return 0


def _top_preview_from_summary(summary: dict[str, Any]) -> list[dict[str, Any]]:
    raw = summary.get("topPreview")
    if not isinstance(raw, list):
        return []
    return [entry for entry in raw if isinstance(entry, dict)]


def _build_known_kanji_set(col: Any, config: AddonConfig) -> set[str]:
    known_kanji: set[str] = set()
    card_ids = list(map(int, col.find_cards(config.effective_mature_query)))
    note_ids = sorted({int(col.get_card(card_id).nid) for card_id in card_ids})
    for note_id in note_ids:
        note = col.get_note(note_id)
        expression = _get_note_field(note, config.expression_field)
        for char in extract_kanji_chars(expression):
            known_kanji.add(char)
    return known_kanji


def _deck_option_warnings(col: Any, card_ids: list[int]) -> list[str]:
    warnings: list[str] = []
    seen_deck_ids: set[int] = set()
    for card_id in card_ids:
        card = col.get_card(card_id)
        deck_id = int(card.did)
        if deck_id in seen_deck_ids:
            continue
        seen_deck_ids.add(deck_id)
        deck = col.decks.get(deck_id) or {}
        deck_name = deck.get("name", str(deck_id))
        config_dict = col.decks.config_dict_for_deck_id(deck_id) or {}

        new_insert_order = _read_config_value(config_dict, "new", "order")
        new_sort_order = config_dict.get("newSortOrder")
        new_gather_priority = config_dict.get("newGatherPriority")

        if new_insert_order == 1:
            warnings.append(
                f'Deck "{deck_name}" uses random new-card insertion order; sequential insertion order is safer for manual repositioning.'
            )
        if new_sort_order not in (None, 1):
            warnings.append(
                f'Deck "{deck_name}" does not preserve gathered order for new cards; set New Card Sort Order to "Order Gathered" for best results.'
            )
        if new_gather_priority not in (None, 1):
            warnings.append(
                f'Deck "{deck_name}" does not gather new cards by lowest position first; set New Card Gather Order to "Lowest Position" if you want the sorter order to be honored.'
            )

    return warnings


def _read_config_value(config_dict: dict[str, Any], section: str, key: str) -> Any:
    raw_section = config_dict.get(section)
    if isinstance(raw_section, dict):
        return raw_section.get(key)
    return None


def _get_note_field(note: Any, field_name: str) -> str:
    try:
        return str(note[field_name])
    except KeyError:
        return ""


def _safe_model_name(card: Any) -> str:
    try:
        model = card.note_type()
    except AttributeError:
        return ""
    if isinstance(model, dict):
        name = model.get("name")
        if isinstance(name, str):
            return name
    return ""
