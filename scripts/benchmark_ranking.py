#!/usr/bin/env python3
"""Benchmark Anki VN Sorter ranking strategies.

The benchmark is intentionally deterministic and local-only. It does not touch an
Anki collection. It imports the real ranking code, evaluates preference cases
that describe the desired queue behavior, measures a synthetic VN-like card set,
and emits an objective score that an optimization loop can compare.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "addon"))

from anki_vn_sorter.config import (  # noqa: E402
    STRATEGY_BALANCED_EASE_V1,
    STRATEGY_EASY_FIRST_TIERED_V1,
    STRATEGY_FREQUENCY_FIRST_SOFT_V1,
)
from anki_vn_sorter.ranking import CardInput, score_cards  # noqa: E402

STRATEGIES = (
    STRATEGY_FREQUENCY_FIRST_SOFT_V1,
    STRATEGY_EASY_FIRST_TIERED_V1,
    STRATEGY_BALANCED_EASE_V1,
)


@dataclass(frozen=True)
class PreferenceCase:
    name: str
    preferred: CardInput
    other: CardInput
    weight: float
    rationale: str


def make_card(
    card_id: int,
    expression: str,
    known_kanji_count: int,
    total_kanji_count: int,
    raw_rank: float | None,
    rank_source: str | None = "jiten",
    due: int | None = None,
    card_ord: int = 0,
) -> CardInput:
    return CardInput(
        card_id=card_id,
        note_id=card_id + 100_000,
        due=card_id if due is None else due,
        card_ord=card_ord,
        expression=expression,
        known_kanji_count=known_kanji_count,
        total_kanji_count=total_kanji_count,
        raw_rank=raw_rank,
        rank_source=rank_source,
    )


def preference_cases() -> list[PreferenceCase]:
    """High-signal behavioral constraints for a useful Kiku VN queue."""

    return [
        PreferenceCase(
            name="known_beats_similarly_common_kana",
            preferred=make_card(1, "既読", 2, 2, 100),
            other=make_card(2, "ありがとう", 0, 0, 90),
            weight=1.25,
            rationale="When frequency is close, readable known-kanji cards should feel easier than kana-only cards.",
        ),
        PreferenceCase(
            name="very_common_kana_can_break_in",
            preferred=make_card(3, "ありがとう", 0, 0, 10),
            other=make_card(4, "既読", 2, 2, 200),
            weight=1.0,
            rationale="Extremely common kana-only words should not be buried behind much rarer known-kanji words.",
        ),
        PreferenceCase(
            name="very_common_one_unknown_can_break_in",
            preferred=make_card(5, "恋愛", 1, 2, 10),
            other=make_card(6, "既読", 2, 2, 400),
            weight=1.0,
            rationale="A super-common partially-known one-unknown card can be worth seeing before a weaker easy card.",
        ),
        PreferenceCase(
            name="partial_known_bonus_matters",
            preferred=make_card(7, "恋愛", 1, 2, 100),
            other=make_card(8, "謎", 0, 1, 100),
            weight=1.0,
            rationale="For equal rank, one known kanji out of two should beat zero known kanji out of one.",
        ),
        PreferenceCase(
            name="two_unknown_penalized_when_close",
            preferred=make_card(9, "既読", 2, 2, 80),
            other=make_card(10, "積極", 0, 2, 50),
            weight=1.25,
            rationale="Two unknown kanji should not jump ahead solely on a modest frequency edge.",
        ),
        PreferenceCase(
            name="three_unknown_not_too_aggressive",
            preferred=make_card(11, "日常", 2, 2, 600),
            other=make_card(12, "鬱蒼林", 0, 3, 12),
            weight=0.75,
            rationale="A three-unknown card should need an overwhelming reason to appear very early.",
        ),
        PreferenceCase(
            name="ranked_cards_beat_unranked_cards",
            preferred=make_card(13, "ところ", 0, 0, 150),
            other=make_card(14, "既読", 2, 2, None, None),
            weight=1.0,
            rationale="Known readability alone should not lift unranked cards above useful ranked cards.",
        ),
        PreferenceCase(
            name="jiten_rank_beats_same_freqsort_rank",
            preferred=make_card(15, "学校", 2, 2, 100, "jiten"),
            other=make_card(16, "校庭", 2, 2, 100, "freqsort"),
            weight=0.75,
            rationale="Jiten is the preferred frequency signal; FreqSort is a fallback.",
        ),
    ]


def expression_for(card_id: int, total_kanji: int) -> str:
    if total_kanji <= 0:
        return f"かな{card_id}"
    # A short deterministic pseudo-expression. The counts used by CardInput are
    # supplied directly, so these characters are only for tie-breaking length.
    chars = "日月火水木金土学校恋愛読語街夢心道時"
    return "".join(chars[(card_id + offset) % len(chars)] for offset in range(total_kanji))


def synthetic_cards(size: int, seed: int) -> list[CardInput]:
    rng = random.Random(seed)
    cards: list[CardInput] = []
    total_choices = (0, 1, 2, 3, 4)
    total_weights = (0.24, 0.21, 0.27, 0.18, 0.10)

    for index in range(size):
        card_id = 10_000 + index
        total_kanji = rng.choices(total_choices, weights=total_weights, k=1)[0]
        known_kanji = rng.randint(0, total_kanji) if total_kanji else 0
        source_roll = rng.random()
        if source_roll < 0.06:
            raw_rank = None
            rank_source = None
        else:
            # Log-uniform ranks approximate the long tail of VN/Japanese vocab.
            raw_rank = round(10 ** rng.uniform(0.0, math.log10(50_000)), 3)
            rank_source = "freqsort" if source_roll < 0.16 else "jiten"
        cards.append(
            make_card(
                card_id=card_id,
                expression=expression_for(card_id, total_kanji),
                known_kanji_count=known_kanji,
                total_kanji_count=total_kanji,
                raw_rank=raw_rank,
                rank_source=rank_source,
                due=index,
            )
        )
    return cards


def frequency_signal(card: CardInput) -> float:
    if card.raw_rank is None:
        return 0.0
    base = 1.0 / (1.0 + math.log10(max(card.raw_rank, 1.0)))
    if card.rank_source == "freqsort":
        return 0.70 * base
    if card.rank_source in {"jiten", "yomitan"}:
        return base
    return 0.0


def latent_utility(card: CardInput) -> float:
    """Proxy utility independent from score_cards implementation.

    It encodes the product goal: maximize useful frequency while avoiding a top
    queue that feels too kanji-painful. This is not a truth metric; it is a
    stable comparator for agent variants.
    """

    unknown = card.unknown_kanji_count
    coverage = card.coverage_score
    if card.total_kanji_count <= 0:
        readability = 0.90
    elif unknown <= 0:
        readability = 1.00
    elif unknown == 1:
        readability = 0.74 + (0.16 * coverage)
    elif unknown == 2:
        readability = 0.55 + (0.14 * coverage)
    else:
        readability = 0.36 + (0.12 * coverage)

    length_penalty = min(len(card.expression.strip()), 12) * 0.0025
    partial_known_bonus = 0.035 * coverage if unknown > 0 else 0.0
    no_rank_penalty = 0.03 if card.raw_rank is None else 0.0
    return max(0.0, (frequency_signal(card) * readability) + partial_known_bonus - length_penalty - no_rank_penalty)


def dcg(values: list[float]) -> float:
    return sum(value / math.log2(index + 2) for index, value in enumerate(values))


def ndcg(sorted_cards: list[CardInput], ideal_cards: list[CardInput], k: int) -> float:
    actual = [latent_utility(card) for card in sorted_cards[:k]]
    ideal = [latent_utility(card) for card in ideal_cards[:k]]
    ideal_dcg = dcg(ideal)
    if ideal_dcg <= 0:
        return 1.0
    return dcg(actual) / ideal_dcg


def evaluate_preferences(strategy: str) -> dict[str, Any]:
    cases = preference_cases()
    total_weight = sum(case.weight for case in cases)
    passed_weight = 0.0
    failed: list[dict[str, Any]] = []

    for case in cases:
        ordered = score_cards([case.preferred, case.other], strategy=strategy)
        winner = ordered[0].card.card_id
        passed = winner == case.preferred.card_id
        if passed:
            passed_weight += case.weight
        else:
            failed.append(
                {
                    "name": case.name,
                    "weight": case.weight,
                    "wanted": case.preferred.expression,
                    "got": ordered[0].card.expression,
                    "rationale": case.rationale,
                }
            )

    return {
        "passedWeight": round(passed_weight, 4),
        "totalWeight": round(total_weight, 4),
        "score": round(passed_weight / total_weight if total_weight else 1.0, 6),
        "failed": failed,
    }


def evaluate_synthetic(strategy: str, size: int, seed: int) -> dict[str, Any]:
    cards = synthetic_cards(size, seed)
    scored = score_cards(cards, strategy=strategy)
    ordered = [entry.card for entry in scored]
    ideal = sorted(cards, key=latent_utility, reverse=True)
    top_30 = ordered[: min(30, len(ordered))]
    top_100 = ordered[: min(100, len(ordered))]

    painful_top_rate = sum(
        1
        for card in top_30
        if card.unknown_kanji_count >= 2 and (card.raw_rank is None or card.raw_rank > 25)
    ) / max(1, len(top_30))
    no_rank_top_rate = sum(1 for card in top_100 if card.raw_rank is None) / max(1, len(top_100))
    top_50_ranks = [card.raw_rank for card in ordered[:50] if card.raw_rank is not None]
    mean_top_50_rank = statistics.fmean(top_50_ranks) if top_50_ranks else None

    return {
        "size": size,
        "seed": seed,
        "ndcgAt30": round(ndcg(ordered, ideal, 30), 6),
        "ndcgAt100": round(ndcg(ordered, ideal, 100), 6),
        "painfulTop30Rate": round(painful_top_rate, 6),
        "noRankTop100Rate": round(no_rank_top_rate, 6),
        "meanTop50Rank": None if mean_top_50_rank is None else round(mean_top_50_rank, 3),
        "top10": [
            {
                "expression": card.expression,
                "rank": card.raw_rank,
                "source": card.rank_source,
                "known": card.known_kanji_count,
                "total": card.total_kanji_count,
                "latentUtility": round(latent_utility(card), 6),
            }
            for card in ordered[:10]
        ],
    }


def measure_runtime(strategy: str, cards: list[CardInput], repeat: int) -> dict[str, Any]:
    start = time.perf_counter()
    for _ in range(repeat):
        score_cards(cards, strategy=strategy)
    elapsed = time.perf_counter() - start
    cards_scored = len(cards) * repeat
    return {
        "repeat": repeat,
        "cardsPerRun": len(cards),
        "seconds": round(elapsed, 6),
        "microsecondsPerCard": round((elapsed / max(1, cards_scored)) * 1_000_000, 4),
    }


def evaluate_strategy(strategy: str, size: int, seed: int, repeat: int) -> dict[str, Any]:
    preference = evaluate_preferences(strategy)
    synthetic = evaluate_synthetic(strategy, size, seed)
    runtime_cards = synthetic_cards(size, seed + 1)
    performance = measure_runtime(strategy, runtime_cards, repeat)

    objective = (
        (preference["score"] * 1000.0)
        + (synthetic["ndcgAt30"] * 250.0)
        + (synthetic["ndcgAt100"] * 150.0)
        - (synthetic["painfulTop30Rate"] * 180.0)
        - (synthetic["noRankTop100Rate"] * 90.0)
        - min(performance["microsecondsPerCard"], 250.0) * 0.05
    )

    return {
        "strategy": strategy,
        "objective": round(objective, 6),
        "preference": preference,
        "synthetic": synthetic,
        "performance": performance,
    }


def render_human(result: dict[str, Any]) -> str:
    if "results" in result:
        lines = ["Anki VN Sorter ranking benchmark", ""]
        for entry in result["results"]:
            lines.append(render_human(entry))
            lines.append("")
        lines.append(f"Winner: {result['winner']['strategy']} ({result['winner']['objective']})")
        return "\n".join(lines).rstrip()

    preference = result["preference"]
    synthetic = result["synthetic"]
    performance = result["performance"]
    lines = [
        f"Strategy: {result['strategy']}",
        f"Objective: {result['objective']}",
        f"Preference score: {preference['score']} ({preference['passedWeight']}/{preference['totalWeight']})",
        f"Synthetic NDCG@30/@100: {synthetic['ndcgAt30']} / {synthetic['ndcgAt100']}",
        f"Painful top-30 rate: {synthetic['painfulTop30Rate']}",
        f"No-rank top-100 rate: {synthetic['noRankTop100Rate']}",
        f"Runtime: {performance['microsecondsPerCard']} us/card",
    ]
    if preference["failed"]:
        lines.append("Failed preferences:")
        for failed in preference["failed"]:
            lines.append(f"- {failed['name']}: wanted {failed['wanted']}, got {failed['got']}")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark Anki VN Sorter ranking behavior.")
    parser.add_argument(
        "--strategy",
        choices=STRATEGIES,
        default=STRATEGY_FREQUENCY_FIRST_SOFT_V1,
        help="Ranking strategy to benchmark.",
    )
    parser.add_argument(
        "--all-strategies",
        action="store_true",
        help="Benchmark all built-in strategies and report the highest objective.",
    )
    parser.add_argument("--synthetic-size", type=int, default=500)
    parser.add_argument("--seed", type=int, default=1337)
    parser.add_argument("--repeat", type=int, default=50, help="Microbenchmark repeats.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of human text.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.synthetic_size <= 0:
        raise SystemExit("--synthetic-size must be positive")
    if args.repeat <= 0:
        raise SystemExit("--repeat must be positive")

    if args.all_strategies:
        results = [
            evaluate_strategy(strategy, args.synthetic_size, args.seed, args.repeat)
            for strategy in STRATEGIES
        ]
        winner = max(results, key=lambda item: item["objective"])
        payload: dict[str, Any] = {"results": results, "winner": winner}
    else:
        payload = evaluate_strategy(args.strategy, args.synthetic_size, args.seed, args.repeat)

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(render_human(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
