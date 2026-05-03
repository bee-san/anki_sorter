from __future__ import annotations

import math
import re
from dataclasses import dataclass

from .config import (
    DEFAULT_FREQSORT_WEIGHT,
    DEFAULT_KANA_ONLY_MULTIPLIER,
    DEFAULT_PARTIAL_KNOWN_COVERAGE_BONUS,
    DEFAULT_PREFER_SHORTER_EXPRESSIONS,
    DEFAULT_TIER_ORDER,
    DEFAULT_UNKNOWN_KANJI_PENALTY_CAP,
    DEFAULT_UNKNOWN_KANJI_PENALTY_STEP,
    STRATEGY_BALANCED_EASE_V1,
    STRATEGY_EASY_FIRST_TIERED_V1,
    STRATEGY_FREQUENCY_FIRST_SOFT_V1,
    TIER_ALL_KANJI_KNOWN,
    TIER_KANA_ONLY,
    TIER_ONE_UNKNOWN_KANJI,
    TIER_THREE_PLUS_UNKNOWN_KANJI,
    TIER_TWO_UNKNOWN_KANJI,
)


@dataclass(frozen=True)
class CardInput:
    card_id: int
    note_id: int
    due: int
    card_ord: int
    expression: str
    known_kanji_count: int
    total_kanji_count: int
    raw_rank: float | None
    rank_source: str | None

    @property
    def unknown_kanji_count(self) -> int:
        return max(0, self.total_kanji_count - self.known_kanji_count)

    @property
    def coverage_score(self) -> float:
        if self.total_kanji_count <= 0:
            return 1.0
        return self.known_kanji_count / self.total_kanji_count


@dataclass(frozen=True)
class ScoredCard:
    card: CardInput
    ease_score: float
    frequency_score: float
    coverage_score: float
    unknown_penalty: float
    priority_tier: int
    priority_label: str
    readability_multiplier: float
    coverage_bonus: float


def parse_freqsort(value: str) -> float | None:
    match = re.search(r"[0-9]+(?:\.[0-9]+)?", value or "")
    if not match:
        return None
    parsed = float(match.group(0))
    if parsed <= 0:
        return None
    return parsed


def score_cards(
    cards: list[CardInput],
    strategy: str = STRATEGY_FREQUENCY_FIRST_SOFT_V1,
    tier_order: tuple[str, ...] = DEFAULT_TIER_ORDER,
    prefer_shorter_expressions: bool = DEFAULT_PREFER_SHORTER_EXPRESSIONS,
    freqsort_weight: float = DEFAULT_FREQSORT_WEIGHT,
    kana_only_multiplier: float = DEFAULT_KANA_ONLY_MULTIPLIER,
    unknown_kanji_penalty_step: float = DEFAULT_UNKNOWN_KANJI_PENALTY_STEP,
    unknown_kanji_penalty_cap: float = DEFAULT_UNKNOWN_KANJI_PENALTY_CAP,
    partial_known_coverage_bonus: float = DEFAULT_PARTIAL_KNOWN_COVERAGE_BONUS,
) -> list[ScoredCard]:
    if strategy == STRATEGY_FREQUENCY_FIRST_SOFT_V1:
        return _score_cards_frequency_first_soft(
            cards,
            tier_order=tier_order,
            prefer_shorter_expressions=prefer_shorter_expressions,
            freqsort_weight=freqsort_weight,
            kana_only_multiplier=kana_only_multiplier,
            unknown_kanji_penalty_step=unknown_kanji_penalty_step,
            unknown_kanji_penalty_cap=unknown_kanji_penalty_cap,
            partial_known_coverage_bonus=partial_known_coverage_bonus,
        )
    if strategy == STRATEGY_EASY_FIRST_TIERED_V1:
        return _score_cards_easy_first_tiered(
            cards,
            tier_order=tier_order,
            prefer_shorter_expressions=prefer_shorter_expressions,
            freqsort_weight=freqsort_weight,
        )
    if strategy == STRATEGY_BALANCED_EASE_V1:
        return _score_cards_balanced(
            cards,
            tier_order=tier_order,
            freqsort_weight=freqsort_weight,
        )
    raise ValueError(f"Unsupported ranking strategy: {strategy}")


def _score_cards_balanced(
    cards: list[CardInput],
    *,
    tier_order: tuple[str, ...],
    freqsort_weight: float,
) -> list[ScoredCard]:
    ranks = [card.raw_rank for card in cards if card.raw_rank is not None]
    max_rank = max(ranks) if ranks else None

    scored: list[ScoredCard] = []
    for card in cards:
        coverage_score = card.coverage_score
        unknown_penalty = min(card.unknown_kanji_count, 3) / 3.0
        rank_score = _normalize_rank(card.raw_rank, max_rank)
        rank_multiplier = (
            1.0
            if card.rank_source == "jiten"
            else freqsort_weight
            if card.rank_source == "freqsort"
            else 0.0
        )
        frequency_score = rank_score * rank_multiplier
        kana_bonus = 0.05 if card.total_kanji_count == 0 else 0.0
        ease_score = (
            0.50 * coverage_score
            + 0.45 * frequency_score
            + kana_bonus
            - 0.10 * unknown_penalty
        )
        scored.append(
            ScoredCard(
                card=card,
                ease_score=ease_score,
                frequency_score=frequency_score,
                coverage_score=coverage_score,
                unknown_penalty=unknown_penalty,
                priority_tier=_priority_tier_index(card, tier_order),
                priority_label=_priority_label(card),
                readability_multiplier=1.0,
                coverage_bonus=0.0,
            )
        )

    return sorted(
        scored,
        key=lambda scored_card: (
            -scored_card.ease_score,
            scored_card.card.unknown_kanji_count,
            scored_card.card.raw_rank
            if scored_card.card.raw_rank is not None
            else math.inf,
            scored_card.card.due,
            scored_card.card.card_ord,
            scored_card.card.card_id,
        ),
    )


def _score_cards_easy_first_tiered(
    cards: list[CardInput],
    *,
    tier_order: tuple[str, ...],
    prefer_shorter_expressions: bool,
    freqsort_weight: float,
) -> list[ScoredCard]:
    scored: list[ScoredCard] = []
    for card in cards:
        priority_tier = _priority_tier_index(card, tier_order)
        frequency_score = _absolute_frequency_score(
            card.raw_rank,
            card.rank_source,
            freqsort_weight,
        )
        coverage_score = card.coverage_score
        unknown_penalty = min(card.unknown_kanji_count, 3) / 3.0
        ease_score = _tier_ease_score(priority_tier, frequency_score)
        scored.append(
            ScoredCard(
                card=card,
                ease_score=ease_score,
                frequency_score=frequency_score,
                coverage_score=coverage_score,
                unknown_penalty=unknown_penalty,
                priority_tier=priority_tier,
                priority_label=_priority_label(card),
                readability_multiplier=1.0,
                coverage_bonus=0.0,
            )
        )

    return sorted(
        scored,
        key=lambda scored_card: (
            scored_card.priority_tier,
            scored_card.card.raw_rank
            if scored_card.card.raw_rank is not None
            else math.inf,
            _expression_length(scored_card.card.expression)
            if prefer_shorter_expressions
            else 0,
            scored_card.card.due,
            scored_card.card.card_ord,
            scored_card.card.card_id,
        ),
    )


def _score_cards_frequency_first_soft(
    cards: list[CardInput],
    *,
    tier_order: tuple[str, ...],
    prefer_shorter_expressions: bool,
    freqsort_weight: float,
    kana_only_multiplier: float,
    unknown_kanji_penalty_step: float,
    unknown_kanji_penalty_cap: float,
    partial_known_coverage_bonus: float,
) -> list[ScoredCard]:
    scored: list[ScoredCard] = []
    for card in cards:
        priority_tier = _priority_tier_index(card, tier_order)
        priority_label = _priority_label(card)
        frequency_score = _absolute_frequency_score(
            card.raw_rank,
            card.rank_source,
            freqsort_weight,
        )
        coverage_score = card.coverage_score
        unknown_penalty = _unknown_kanji_penalty(
            card.unknown_kanji_count,
            unknown_kanji_penalty_step,
            unknown_kanji_penalty_cap,
        )
        readability_multiplier = _readability_multiplier(
            card,
            kana_only_multiplier,
            unknown_penalty,
        )
        coverage_bonus = (
            partial_known_coverage_bonus * coverage_score
            if card.unknown_kanji_count > 0
            else 0.0
        )
        ease_score = (frequency_score * readability_multiplier) + coverage_bonus
        scored.append(
            ScoredCard(
                card=card,
                ease_score=ease_score,
                frequency_score=frequency_score,
                coverage_score=coverage_score,
                unknown_penalty=unknown_penalty,
                priority_tier=priority_tier,
                priority_label=priority_label,
                readability_multiplier=readability_multiplier,
                coverage_bonus=coverage_bonus,
            )
        )

    return sorted(
        scored,
        key=lambda scored_card: (
            -scored_card.ease_score,
            scored_card.card.raw_rank
            if scored_card.card.raw_rank is not None
            else math.inf,
            _expression_length(scored_card.card.expression)
            if prefer_shorter_expressions
            else 0,
            scored_card.card.due,
            scored_card.card.card_ord,
            scored_card.card.card_id,
        ),
    )


def _normalize_rank(rank: float | None, max_rank: float | None) -> float:
    if rank is None:
        return 0.0
    if max_rank is None or max_rank <= 1:
        return 1.0
    numerator = math.log1p(max(rank - 1.0, 0.0))
    denominator = math.log1p(max_rank)
    if denominator <= 0:
        return 1.0
    return max(0.0, 1.0 - (numerator / denominator))


def _absolute_frequency_score(
    rank: float | None,
    rank_source: str | None,
    freqsort_weight: float,
) -> float:
    if rank is None:
        return 0.0
    score = 1.0 / (1.0 + math.log10(max(rank, 1.0)))
    if rank_source == "freqsort":
        return score * freqsort_weight
    if rank_source == "jiten":
        return score
    return 0.0


def _unknown_kanji_penalty(
    unknown_kanji_count: int,
    step: float,
    cap: float,
) -> float:
    if unknown_kanji_count <= 0:
        return 0.0
    return min(step * unknown_kanji_count, cap)


def _readability_multiplier(
    card: CardInput,
    kana_only_multiplier: float,
    unknown_penalty: float,
) -> float:
    if card.total_kanji_count <= 0:
        return kana_only_multiplier
    if card.unknown_kanji_count <= 0:
        return 1.0
    return max(0.0, 1.0 - unknown_penalty)


def _priority_label(card: CardInput) -> str:
    if card.total_kanji_count == 0:
        return TIER_KANA_ONLY
    if card.unknown_kanji_count <= 0:
        return TIER_ALL_KANJI_KNOWN
    if card.unknown_kanji_count == 1:
        return TIER_ONE_UNKNOWN_KANJI
    if card.unknown_kanji_count == 2:
        return TIER_TWO_UNKNOWN_KANJI
    return TIER_THREE_PLUS_UNKNOWN_KANJI


def _priority_tier_index(card: CardInput, tier_order: tuple[str, ...]) -> int:
    return tier_order.index(_priority_label(card))


def _tier_ease_score(priority_tier: int, frequency_score: float) -> float:
    tier_base_score = max(0.0, 1.0 - (0.2 * priority_tier))
    return tier_base_score + (0.01 * frequency_score)


def _expression_length(expression: str) -> int:
    return len(expression.strip())
