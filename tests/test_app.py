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
from super_mario_pygamece.entities import PipeState
from super_mario_pygamece.paths import ProjectPaths
from super_mario_pygamece.settings import STARTING_LIVES
from super_mario_pygamece.world import WorldState


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

        # Starting a level now shows the intermission screen first.
        self.assertEqual(app.state, AppState.INTERMISSION)
        self.assertEqual(app.level.meta.name, "1-2")
        app._end_intermission()
        self.assertEqual(app.state, AppState.PLAYING)

    def test_gameover_continue_restarts_current_stage(self) -> None:
        root = _fixture_root("app_continue")
        self.addCleanup(shutil.rmtree, root.parent, True)
        paths = _write_project_fixture(root)
        app = PygameMario(level_path=paths.find_level("1-2"), paths=paths, audio_enabled=False)
        app.world.state = WorldState.GAMEOVER
        app.world.gameover_timer = 0
        app.world.lives = 0
        app.world.score = 1234

        app._continue_after_gameover()

        self.assertEqual(app.state, AppState.PLAYING)
        self.assertEqual(app.level.meta.name, "1-2")
        self.assertEqual(app.world.state, WorldState.PLAYING)
        self.assertEqual(app.world.lives, STARTING_LIVES)
        self.assertEqual(app.world.score, 0)

    def test_gameover_escape_returns_to_title(self) -> None:
        root = _fixture_root("app_gameover_title")
        self.addCleanup(shutil.rmtree, root.parent, True)
        paths = _write_project_fixture(root)
        app = PygameMario(level_path=paths.find_level("1-1"), paths=paths, audio_enabled=False)
        app.world.state = WorldState.GAMEOVER
        app.world.gameover_timer = 0

        running, _, _ = app._handle_playing_key(pygame.K_ESCAPE, running=True, jump_pressed=False)

        self.assertTrue(running)
        self.assertEqual(app.state, AppState.TITLE)

    def test_warp_resolves_sdl3_relative_destination_and_preserves_exit(self) -> None:
        root = _fixture_root("app_warp")
        self.addCleanup(shutil.rmtree, root.parent, True)
        paths = _write_project_fixture(root)
        _write_level(paths.sdl3_root / "build" / "Debug" / "assets" / "levels" / "1-1b.json", "1-1b")
        app = PygameMario(level_path=paths.find_level("1-1"), paths=paths, audio_enabled=False)
        app.world.player.pipe_dest_x = 18 * 32
        app.world.player.pipe_dest_y = 12 * 32
        app.world.player.pipe_exit_facing_right = False
        app.world.player.pipe_exit_horizontal = True
        app.world.time_remaining = 321.0

        app._do_level_warp("assets/levels/1-1b.json")

        self.assertEqual(app.level_path.stem, "1-1b")
        self.assertEqual(app.world.player.pos.x, 18 * 32)
        self.assertEqual(app.world.player.pos.y, 12 * 32)
        self.assertEqual(app.world.player.pipe_state, PipeState.EXITING_LEFT)
        self.assertEqual(app.world.time_remaining, 321.0)

    def test_sublevel_completion_normalizes_to_next_main_stage(self) -> None:
        root = _fixture_root("app_progression")
        self.addCleanup(shutil.rmtree, root.parent, True)
        paths = _write_project_fixture(root)
        level_dir = paths.sdl3_root / "build" / "Debug" / "assets" / "levels"
        _write_level(level_dir / "1-2c.json", "1-2c")
        _write_level(level_dir / "1-3.json", "1-3")
        app = PygameMario(level_path=paths.find_level("1-2c"), paths=paths, audio_enabled=False)

        app._advance_to_next_level()

        self.assertEqual(app.level_path.stem, "1-3")
        self.assertEqual(app.state, AppState.PLAYING)


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
