from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.package_addon import iter_package_files


class PackageAddonTests(unittest.TestCase):
    def test_iter_package_files_skips_runtime_and_bytecode_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            addon_root = Path(temp_dir) / "anki_vn_sorter"
            addon_root.mkdir(parents=True)

            (addon_root / "addon.py").write_text("# addon\n", encoding="utf-8")
            (addon_root / "config.json").write_text("{}\n", encoding="utf-8")

            user_files_dir = addon_root / "user_files"
            user_files_dir.mkdir()
            (user_files_dir / "sorter_state.json").write_text("{}", encoding="utf-8")

            pycache_dir = addon_root / "__pycache__"
            pycache_dir.mkdir()
            (pycache_dir / "addon.cpython-314.pyc").write_bytes(b"pyc")

            packaged = [
                str(path.relative_to(addon_root))
                for path in iter_package_files(addon_root)
            ]

        self.assertEqual(packaged, ["addon.py", "config.json"])


if __name__ == "__main__":
    unittest.main()
