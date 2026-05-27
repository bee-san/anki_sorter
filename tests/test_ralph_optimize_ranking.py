from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "ralph_optimize_ranking.py"

spec = importlib.util.spec_from_file_location("ralph_optimize_ranking", SCRIPT_PATH)
assert spec is not None
ralph_optimize_ranking = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = ralph_optimize_ranking
assert spec.loader is not None
spec.loader.exec_module(ralph_optimize_ranking)


class RalphOptimizeRankingTests(unittest.TestCase):
    def test_copy_repo_to_scratch_excludes_ignored_user_files(self) -> None:
        private_path = ROOT / "addon" / "anki_vn_sorter" / "user_files" / "private-test-cache.txt"
        private_path.parent.mkdir(parents=True, exist_ok=True)
        private_path.write_text("private cache contents\n", encoding="utf-8")
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                scratch = Path(temp_dir) / "scratch"
                ralph_optimize_ranking.copy_repo_to_scratch(scratch)

                self.assertTrue((scratch / "addon" / "anki_vn_sorter" / "config.py").exists())
                self.assertFalse((scratch / "addon" / "anki_vn_sorter" / "user_files" / "private-test-cache.txt").exists())
        finally:
            private_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
