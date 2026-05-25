from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "benchmark_ranking.py"

spec = importlib.util.spec_from_file_location("benchmark_ranking", SCRIPT_PATH)
assert spec is not None
benchmark_ranking = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = benchmark_ranking
assert spec.loader is not None
spec.loader.exec_module(benchmark_ranking)


class BenchmarkRankingTests(unittest.TestCase):
    def test_small_unranked_synthetic_input_does_not_crash(self) -> None:
        result = benchmark_ranking.evaluate_synthetic(
            benchmark_ranking.STRATEGY_FREQUENCY_FIRST_SOFT_V1,
            size=1,
            seed=0,
        )

        self.assertEqual(result["size"], 1)
        self.assertIsNone(result["meanTop50Rank"])
        self.assertEqual(result["noRankTop100Rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
