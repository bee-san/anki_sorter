from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "addon"))

from anki_vn_sorter.config import (
    DEFAULT_TIER_ORDER,
    STRATEGY_BALANCED_EASE_V1,
    STRATEGY_EASY_FIRST_TIERED_V1,
    STRATEGY_FREQUENCY_FIRST_SOFT_V1,
    TIER_ALL_KANJI_KNOWN,
    TIER_KANA_ONLY,
)
from anki_vn_sorter.ranking import CardInput, parse_freqsort, score_cards


class RankingTests(unittest.TestCase):
    def make_card(
        self,
        *,
        card_id: int,
        expression: str,
        known_kanji_count: int,
        total_kanji_count: int,
        raw_rank: float | None,
        rank_source: str | None,
        due: int | None = None,
        card_ord: int = 0,
    ) -> CardInput:
        return CardInput(
            card_id=card_id,
            note_id=card_id + 100,
            due=due if due is not None else card_id,
            card_ord=card_ord,
            expression=expression,
            known_kanji_count=known_kanji_count,
            total_kanji_count=total_kanji_count,
            raw_rank=raw_rank,
            rank_source=rank_source,
        )

    def test_parse_freqsort(self) -> None:
        self.assertEqual(parse_freqsort("123"), 123.0)
        self.assertEqual(parse_freqsort("rank=45.5"), 45.5)
        self.assertIsNone(parse_freqsort(""))

    def test_balanced_strategy_known_common_beats_rare_known(self) -> None:
        cards = [
            self.make_card(
                card_id=1,
                expression="既読",
                known_kanji_count=2,
                total_kanji_count=2,
                raw_rank=8,
                rank_source="jiten",
            ),
            self.make_card(
                card_id=2,
                expression="隘路",
                known_kanji_count=2,
                total_kanji_count=2,
                raw_rank=8000,
                rank_source="jiten",
            ),
        ]
        scored = score_cards(cards, strategy=STRATEGY_BALANCED_EASE_V1)
        self.assertEqual([entry.card.card_id for entry in scored], [1, 2])

    def test_balanced_strategy_common_one_unknown_can_beat_rare_known(self) -> None:
        cards = [
            self.make_card(
                card_id=1,
                expression="既読",
                known_kanji_count=2,
                total_kanji_count=2,
                raw_rank=5000,
                rank_source="jiten",
            ),
            self.make_card(
                card_id=2,
                expression="恋愛",
                known_kanji_count=1,
                total_kanji_count=2,
                raw_rank=5,
                rank_source="jiten",
            ),
        ]
        scored = score_cards(cards, strategy=STRATEGY_BALANCED_EASE_V1)
        self.assertEqual([entry.card.card_id for entry in scored], [2, 1])

    def test_default_soft_strategy_prefers_known_kanji_when_frequency_is_similar(self) -> None:
        cards = [
            self.make_card(
                card_id=1,
                expression="ありがとう",
                known_kanji_count=0,
                total_kanji_count=0,
                raw_rank=90,
                rank_source="jiten",
            ),
            self.make_card(
                card_id=2,
                expression="既読",
                known_kanji_count=2,
                total_kanji_count=2,
                raw_rank=100,
                rank_source="jiten",
            ),
        ]
        scored = score_cards(cards, strategy=STRATEGY_FREQUENCY_FIRST_SOFT_V1)
        self.assertEqual([entry.card.card_id for entry in scored], [2, 1])
        self.assertEqual(scored[0].priority_label, "all_kanji_known")
        self.assertEqual(scored[1].priority_label, "kana_only")

    def test_default_soft_strategy_allows_super_common_kana_to_beat_rare_known(self) -> None:
        cards = [
            self.make_card(
                card_id=1,
                expression="既読",
                known_kanji_count=2,
                total_kanji_count=2,
                raw_rank=200,
                rank_source="jiten",
            ),
            self.make_card(
                card_id=2,
                expression="ありがとう",
                known_kanji_count=0,
                total_kanji_count=0,
                raw_rank=10,
                rank_source="jiten",
            ),
        ]
        scored = score_cards(cards, strategy=STRATEGY_FREQUENCY_FIRST_SOFT_V1)
        self.assertEqual([entry.card.card_id for entry in scored], [2, 1])

    def test_default_soft_strategy_allows_super_common_one_unknown_to_beat_weaker_easy_card(self) -> None:
        cards = [
            self.make_card(
                card_id=1,
                expression="既読",
                known_kanji_count=2,
                total_kanji_count=2,
                raw_rank=400,
                rank_source="jiten",
            ),
            self.make_card(
                card_id=2,
                expression="恋愛",
                known_kanji_count=1,
                total_kanji_count=2,
                raw_rank=10,
                rank_source="jiten",
            ),
        ]
        scored = score_cards(cards, strategy=STRATEGY_FREQUENCY_FIRST_SOFT_V1)
        self.assertEqual([entry.card.card_id for entry in scored], [2, 1])

    def test_default_soft_strategy_uses_partial_known_bonus_for_one_unknown(self) -> None:
        cards = [
            self.make_card(
                card_id=1,
                expression="恋愛",
                known_kanji_count=1,
                total_kanji_count=2,
                raw_rank=100,
                rank_source="jiten",
            ),
            self.make_card(
                card_id=2,
                expression="謎",
                known_kanji_count=0,
                total_kanji_count=1,
                raw_rank=100,
                rank_source="jiten",
            ),
        ]
        scored = score_cards(cards, strategy=STRATEGY_FREQUENCY_FIRST_SOFT_V1)
        self.assertEqual([entry.card.card_id for entry in scored], [1, 2])

    def test_default_soft_strategy_penalizes_two_unknown_when_frequency_is_close(self) -> None:
        cards = [
            self.make_card(
                card_id=1,
                expression="既読",
                known_kanji_count=2,
                total_kanji_count=2,
                raw_rank=80,
                rank_source="jiten",
            ),
            self.make_card(
                card_id=2,
                expression="積極",
                known_kanji_count=0,
                total_kanji_count=2,
                raw_rank=50,
                rank_source="jiten",
            ),
        ]
        scored = score_cards(cards, strategy=STRATEGY_FREQUENCY_FIRST_SOFT_V1)
        self.assertEqual([entry.card.card_id for entry in scored], [1, 2])

    def test_tiered_strategy_keeps_known_kanji_above_one_unknown(self) -> None:
        cards = [
            self.make_card(
                card_id=1,
                expression="既読",
                known_kanji_count=2,
                total_kanji_count=2,
                raw_rank=5000,
                rank_source="jiten",
            ),
            self.make_card(
                card_id=2,
                expression="恋愛",
                known_kanji_count=1,
                total_kanji_count=2,
                raw_rank=5,
                rank_source="jiten",
            ),
        ]
        scored = score_cards(cards, strategy=STRATEGY_EASY_FIRST_TIERED_V1)
        self.assertEqual([entry.card.card_id for entry in scored], [1, 2])
        self.assertEqual(
            [entry.priority_label for entry in scored],
            ["all_kanji_known", "one_unknown_kanji"],
        )

    def test_tiered_strategy_uses_frequency_within_a_tier(self) -> None:
        cards = [
            self.make_card(
                card_id=1,
                expression="恋愛",
                known_kanji_count=1,
                total_kanji_count=2,
                raw_rank=90,
                rank_source="jiten",
            ),
            self.make_card(
                card_id=2,
                expression="遊園",
                known_kanji_count=1,
                total_kanji_count=2,
                raw_rank=12,
                rank_source="jiten",
            ),
        ]
        scored = score_cards(cards, strategy=STRATEGY_EASY_FIRST_TIERED_V1)
        self.assertEqual([entry.card.card_id for entry in scored], [2, 1])

    def test_tiered_strategy_prefers_shorter_expression_on_same_tier_and_rank(self) -> None:
        cards = [
            self.make_card(
                card_id=1,
                expression="ありがとうございます",
                known_kanji_count=0,
                total_kanji_count=0,
                raw_rank=100,
                rank_source="freqsort",
            ),
            self.make_card(
                card_id=2,
                expression="ありがと",
                known_kanji_count=0,
                total_kanji_count=0,
                raw_rank=100,
                rank_source="freqsort",
            ),
        ]
        scored = score_cards(cards, strategy=STRATEGY_EASY_FIRST_TIERED_V1)
        self.assertEqual([entry.card.card_id for entry in scored], [2, 1])

    def test_tiered_strategy_honors_custom_tier_order(self) -> None:
        cards = [
            self.make_card(
                card_id=1,
                expression="ありがとう",
                known_kanji_count=0,
                total_kanji_count=0,
                raw_rank=100,
                rank_source="freqsort",
            ),
            self.make_card(
                card_id=2,
                expression="既読",
                known_kanji_count=2,
                total_kanji_count=2,
                raw_rank=5000,
                rank_source="jiten",
            ),
        ]
        custom_tier_order = (
            TIER_ALL_KANJI_KNOWN,
            TIER_KANA_ONLY,
            *DEFAULT_TIER_ORDER[2:],
        )
        scored = score_cards(
            cards,
            strategy=STRATEGY_EASY_FIRST_TIERED_V1,
            tier_order=custom_tier_order,
        )
        self.assertEqual([entry.card.card_id for entry in scored], [2, 1])

    def test_tiered_strategy_can_disable_shorter_expression_tiebreak(self) -> None:
        cards = [
            self.make_card(
                card_id=1,
                expression="ありがとうございます",
                known_kanji_count=0,
                total_kanji_count=0,
                raw_rank=100,
                rank_source="freqsort",
                due=1,
            ),
            self.make_card(
                card_id=2,
                expression="ありがと",
                known_kanji_count=0,
                total_kanji_count=0,
                raw_rank=100,
                rank_source="freqsort",
                due=2,
            ),
        ]
        scored = score_cards(
            cards,
            strategy=STRATEGY_EASY_FIRST_TIERED_V1,
            prefer_shorter_expressions=False,
        )
        self.assertEqual([entry.card.card_id for entry in scored], [1, 2])


if __name__ == "__main__":
    unittest.main()
