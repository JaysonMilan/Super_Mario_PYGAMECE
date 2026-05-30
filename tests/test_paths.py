from __future__ import annotations

import unittest
import shutil
from pathlib import Path

from super_mario_pygamece.paths import ProjectPaths


class ProjectPathsTests(unittest.TestCase):
    def test_available_levels_deduplicates_resolved_paths(self) -> None:
        root = Path.cwd() / ".test_tmp" / "paths"
        shutil.rmtree(root, ignore_errors=True)
        self.addCleanup(shutil.rmtree, root.parent, True)

        level_dir = root / "assets" / "levels"
        build_level_dir = root / "build" / "Debug" / "assets" / "levels"
        level_dir.mkdir(parents=True)
        build_level_dir.mkdir(parents=True)
        (level_dir / "1-1.json").write_text("{}", encoding="utf-8")
        (build_level_dir / "custom_level.json").write_text("{}", encoding="utf-8")

        paths = ProjectPaths(project_root=root / "pygame", sdl3_root=root)

        self.assertEqual(
            paths.available_levels(),
            (
                (level_dir / "1-1.json").resolve(),
                (build_level_dir / "custom_level.json").resolve(),
            )
        )

    def test_find_level_accepts_stem_or_filename(self) -> None:
        root = Path.cwd() / ".test_tmp" / "find_level"
        shutil.rmtree(root, ignore_errors=True)
        self.addCleanup(shutil.rmtree, root.parent, True)

        level_dir = root / "build" / "Debug" / "assets" / "levels"
        level_dir.mkdir(parents=True)
        level_path = level_dir / "1-1.json"
        level_path.write_text("{}", encoding="utf-8")

        paths = ProjectPaths(project_root=root / "pygame", sdl3_root=root)

        self.assertEqual(paths.find_level("1-1"), level_path.resolve())
        self.assertEqual(paths.find_level("1-1.json"), level_path.resolve())
        self.assertIsNone(paths.find_level("missing"))


if __name__ == "__main__":
    unittest.main()
