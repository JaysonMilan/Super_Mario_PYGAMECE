from __future__ import annotations

import shutil
import unittest
from pathlib import Path

from super_mario_pygamece.diagnostics import _version_status, build_diagnostic_report
from super_mario_pygamece.paths import ProjectPaths


class DiagnosticsTests(unittest.TestCase):
    def test_report_includes_missing_asset_status(self) -> None:
        root = Path.cwd() / ".test_tmp" / "diagnostics_missing"
        shutil.rmtree(root, ignore_errors=True)
        self.addCleanup(shutil.rmtree, root.parent, True)

        report = build_diagnostic_report(ProjectPaths(project_root=root / "pygame", sdl3_root=root))

        self.assertIn("Atlas metadata: MISSING", report)
        self.assertIn("Levels found: 0", report)

    def test_report_counts_levels_and_sounds(self) -> None:
        root = Path.cwd() / ".test_tmp" / "diagnostics_counts"
        shutil.rmtree(root, ignore_errors=True)
        self.addCleanup(shutil.rmtree, root.parent, True)
        (root / "assets" / "processed" / "atlases").mkdir(parents=True)
        (root / "assets" / "processed" / "atlases" / "atlases.json").write_text("{}", encoding="utf-8")
        level_dir = root / "build" / "Debug" / "assets" / "levels"
        level_dir.mkdir(parents=True)
        (level_dir / "1-1.json").write_text("{}", encoding="utf-8")
        sounds_dir = root / "assets" / "sounds"
        sounds_dir.mkdir(parents=True)
        (sounds_dir / "coin.wav").write_bytes(b"")

        report = build_diagnostic_report(ProjectPaths(project_root=root / "pygame", sdl3_root=root))

        self.assertIn("Atlas metadata: OK", report)
        self.assertIn("Levels found: 1", report)
        self.assertIn("Sounds found: 1", report)

    def test_version_status_reports_outdated_versions(self) -> None:
        self.assertEqual(_version_status("2.5.1", "2.5.7"), "OUTDATED, required >= 2.5.7")
        self.assertEqual(_version_status("2.5.7", "2.5.7"), "OK")
        self.assertEqual(_version_status("not installed", "2.5.7"), "MISSING, required >= 2.5.7")


if __name__ == "__main__":
    unittest.main()
