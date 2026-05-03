#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

EXCLUDED_DIR_NAMES = {"__pycache__", "user_files"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}


def iter_package_files(addon_root: Path) -> list[Path]:
    paths: list[Path] = []
    for path in sorted(addon_root.rglob("*")):
        if path.is_dir():
            continue
        relative_path = path.relative_to(addon_root)
        if any(part in EXCLUDED_DIR_NAMES for part in relative_path.parts):
            continue
        if path.suffix in EXCLUDED_SUFFIXES:
            continue
        paths.append(path)
    return paths


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    addon_root = repo_root / "addon" / "anki_vn_sorter"
    dist_dir = repo_root / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    output_path = dist_dir / "anki_vn_sorter.ankiaddon"

    with ZipFile(output_path, "w", compression=ZIP_DEFLATED) as archive:
        for path in iter_package_files(addon_root):
            archive.write(path, arcname=path.relative_to(addon_root))

    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
