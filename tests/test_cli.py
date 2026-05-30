from __future__ import annotations

import contextlib
import io
import shutil
import unittest
from pathlib import Path

from super_mario_pygamece.cli import build_parser, main, resolve_level_path


class CliTests(unittest.TestCase):
    def test_list_levels_prints_discovered_levels(self) -> None:
        root = _fixture_root("cli_list")
        self.addCleanup(shutil.rmtree, root.parent, True)
        _write_level(root, "1-1.json")

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = main(["--sdl3-root", str(root), "--list-levels"])

        self.assertEqual(result, 0)
        self.assertIn("1-1.json", stdout.getvalue())

    def test_doctor_prints_diagnostic_report(self) -> None:
        root = _fixture_root("cli_doctor")
        self.addCleanup(shutil.rmtree, root.parent, True)
        _write_atlas_metadata(root)

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = main(["--sdl3-root", str(root), "--doctor"])

        self.assertEqual(result, 0)
        self.assertIn("SDL3 root:", stdout.getvalue())

    def test_missing_level_name_exits_with_error(self) -> None:
        root = _fixture_root("cli_missing_level")
        self.addCleanup(shutil.rmtree, root.parent, True)
        _write_atlas_metadata(root)

        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as error:
                main(["--sdl3-root", str(root), "--level-name", "missing", "--no-audio"])

        self.assertEqual(error.exception.code, 2)

    def test_parser_rejects_explicit_level_and_level_name(self) -> None:
        parser = build_parser()

        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as error:
                parser.parse_args(["--level", "a.json", "--level-name", "1-1"])

        self.assertEqual(error.exception.code, 2)

    def test_resolve_level_path_prefers_explicit_path(self) -> None:
        root = _fixture_root("cli_resolve_explicit")
        self.addCleanup(shutil.rmtree, root.parent, True)
        paths = _write_atlas_metadata(root)
        explicit = root / "custom.json"

        self.assertEqual(
            resolve_level_path(paths, explicit, None, _raise_error),
            explicit,
        )

    def test_resolve_level_path_finds_named_level(self) -> None:
        root = _fixture_root("cli_resolve_named")
        self.addCleanup(shutil.rmtree, root.parent, True)
        _write_level(root, "1-1.json")
        paths = _write_atlas_metadata(root)

        self.assertEqual(
            resolve_level_path(paths, None, "1-1", _raise_error),
            (root / "build" / "Debug" / "assets" / "levels" / "1-1.json").resolve(),
        )


def _fixture_root(name: str) -> Path:
    root = Path.cwd() / ".test_tmp" / name
    shutil.rmtree(root, ignore_errors=True)
    return root


def _write_level(root: Path, filename: str) -> None:
    level_dir = root / "build" / "Debug" / "assets" / "levels"
    level_dir.mkdir(parents=True)
    (level_dir / filename).write_text("{}", encoding="utf-8")


def _write_atlas_metadata(root: Path):
    atlas_dir = root / "assets" / "processed" / "atlases"
    atlas_dir.mkdir(parents=True)
    (atlas_dir / "atlases.json").write_text('{"atlases": {}}', encoding="utf-8")
    from super_mario_pygamece.paths import ProjectPaths

    return ProjectPaths(project_root=root / "pygame", sdl3_root=root)


def _raise_error(message: str):
    raise AssertionError(message)


if __name__ == "__main__":
    unittest.main()
