from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import ModuleType
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]


def load_package_addon() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "package_addon", ROOT / "scripts" / "package_addon.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load package_addon.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


package_addon = load_package_addon()


class PackageAddonTests(unittest.TestCase):
    def test_iter_package_files_skips_runtime_and_bytecode_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            addon_root = Path(temp_dir) / "anki_sorter"
            addon_root.mkdir(parents=True)

            (addon_root / "addon.py").write_text("# addon\n", encoding="utf-8")
            (addon_root / "config.json").write_text("{}\n", encoding="utf-8")
            (addon_root / "meta.json").write_text("{}", encoding="utf-8")

            user_files_dir = addon_root / "user_files"
            user_files_dir.mkdir()
            (user_files_dir / "sorter_state.json").write_text("{}", encoding="utf-8")

            pycache_dir = addon_root / "__pycache__"
            pycache_dir.mkdir()
            (pycache_dir / "addon.cpython-314.pyc").write_bytes(b"pyc")

            packaged = [
                str(path.relative_to(addon_root))
                for path in package_addon.iter_package_files(addon_root)
            ]

        self.assertEqual(packaged, ["addon.py", "config.json"])

    def test_release_package_ships_safe_sync_defaults(self) -> None:
        config_path = ROOT / "addon" / "anki_sorter" / "config.json"

        packaged_paths = package_addon.iter_package_files(config_path.parent)
        relative_paths = {
            path.relative_to(config_path.parent).as_posix() for path in packaged_paths
        }

        self.assertIn("config.json", relative_paths)
        config = json.loads(config_path.read_text(encoding="utf-8"))
        self.assertEqual(config["autoSortMode"], "manual_only")
        self.assertEqual(config["syncSafetyMode"], "mobile_guarded")

    def test_release_package_excludes_user_files(self) -> None:
        addon_root = ROOT / "addon" / "anki_sorter"
        private_path = addon_root / "user_files" / "private-test-cache.json"
        private_path.parent.mkdir(exist_ok=True)
        private_path.write_text('{"secret": true}', encoding="utf-8")
        try:
            package_addon.main()
            archive_path = ROOT / "dist" / "anki_sorter.ankiaddon"
            with ZipFile(archive_path) as archive:
                names = set(archive.namelist())

            self.assertNotIn("user_files/private-test-cache.json", names)
            self.assertTrue(all(not name.startswith("user_files/") for name in names))
        finally:
            private_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
