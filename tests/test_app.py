from __future__ import annotations

import json
import os
import shutil
import unittest
import warnings
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
warnings.filterwarnings("ignore", message="pkg_resources is deprecated.*", category=UserWarning)

import pygame

from super_mario_pygamece.app import AppState, PygameMario
from super_mario_pygamece.paths import ProjectPaths


class PygameMarioAppTests(unittest.TestCase):
    def tearDown(self) -> None:
        pygame.quit()

    def test_starts_on_title_without_explicit_level(self) -> None:
        root = _fixture_root("app_title")
        self.addCleanup(shutil.rmtree, root.parent, True)
        paths = _write_project_fixture(root)

        app = PygameMario(level_path=None, paths=paths, audio_enabled=False)

        self.assertEqual(app.state, AppState.TITLE)
        self.assertEqual(app.selected_level_index, 0)

    def test_explicit_level_starts_playing(self) -> None:
        root = _fixture_root("app_explicit")
        self.addCleanup(shutil.rmtree, root.parent, True)
        paths = _write_project_fixture(root)
        level_path = paths.find_level("1-2")

        app = PygameMario(level_path=level_path, paths=paths, audio_enabled=False)

        self.assertEqual(app.state, AppState.PLAYING)
        self.assertEqual(app.level.meta.name, "1-2")

    def test_pause_and_resume_keys_change_state(self) -> None:
        root = _fixture_root("app_pause")
        self.addCleanup(shutil.rmtree, root.parent, True)
        paths = _write_project_fixture(root)
        app = PygameMario(level_path=paths.find_level("1-1"), paths=paths, audio_enabled=False)

        app._handle_playing_key(pygame.K_p, running=True, jump_pressed=False)
        self.assertEqual(app.state, AppState.PAUSED)

        app._handle_pause_key(pygame.K_p, running=True, jump_pressed=False)
        self.assertEqual(app.state, AppState.PLAYING)

    def test_title_selection_wraps_and_starts_selected_level(self) -> None:
        root = _fixture_root("app_selection")
        self.addCleanup(shutil.rmtree, root.parent, True)
        paths = _write_project_fixture(root)
        app = PygameMario(level_path=None, paths=paths, audio_enabled=False)

        app._move_level_selection(-1)
        app._start_selected_level()

        self.assertEqual(app.state, AppState.PLAYING)
        self.assertEqual(app.level.meta.name, "1-2")


def _fixture_root(name: str) -> Path:
    root = Path.cwd() / ".test_tmp" / name
    shutil.rmtree(root, ignore_errors=True)
    return root


def _write_project_fixture(root: Path) -> ProjectPaths:
    atlas_dir = root / "assets" / "processed" / "atlases"
    level_dir = root / "build" / "Debug" / "assets" / "levels"
    atlas_dir.mkdir(parents=True)
    level_dir.mkdir(parents=True)
    (atlas_dir / "atlases.json").write_text(json.dumps({"atlases": {}}), encoding="utf-8")
    _write_level(level_dir / "1-1.json", "1-1")
    _write_level(level_dir / "1-2.json", "1-2")
    return ProjectPaths(project_root=root / "pygame", sdl3_root=root)


def _write_level(path: Path, name: str) -> None:
    path.write_text(
        json.dumps(
            {
                "level": {"name": name, "width": 32, "height": 15},
                "foreground": [{"type": "Ground", "sprite": "gnd_red_1", "x": x, "y": 14} for x in range(32)],
                "background": [],
                "entities": [{"type": "PlayerSpawn", "x": 3, "y": 13}],
            }
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
