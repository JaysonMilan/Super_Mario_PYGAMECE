from __future__ import annotations

from enum import Enum
from pathlib import Path

import pygame

from .assets import AudioManager, SpriteBank
from .audio import MusicManager
from .level import LevelData, find_default_level, generate_template_level, load_level
from .paths import ProjectPaths
from .renderer import Renderer
from .settings import FIXED_DT, LOW_TIME_THRESHOLD, SCREEN_SIZE, TILE_SIZE
from .world import GameWorld, WorldState


class AppState(Enum):
    TITLE = "title"
    PLAYING = "playing"
    PAUSED = "paused"


JUMP_KEYS = {pygame.K_SPACE, pygame.K_z, pygame.K_k}
FIRE_KEYS = {pygame.K_x, pygame.K_j}


class PygameMario:
    def __init__(self, level_path: Path | None, paths: ProjectPaths, audio_enabled: bool = True) -> None:
        pygame.init()
        pygame.display.set_caption("Super Mario PYGAMECE")
        self.screen = pygame.display.set_mode(SCREEN_SIZE)
        self.clock = pygame.Clock()
        self.font = pygame.font.Font(None, 26)
        self.paths = paths
        self.sprites = SpriteBank(self.paths.atlas_metadata, self.paths.atlas_dir, TILE_SIZE)
        self.renderer = Renderer(self.screen, self.sprites, self.font)
        self.audio = AudioManager(self.paths.sounds_dir, enabled=audio_enabled)
        self.music = MusicManager(self.paths.sounds_dir, enabled=audio_enabled)
        self.level_paths = self.paths.available_levels()
        self.selected_level_index = self._initial_level_index(level_path)
        self.level_path = level_path or find_default_level(self.paths)
        self.level = self._load_level()
        self.world = GameWorld(self.level)
        self.state = AppState.PLAYING if level_path is not None else AppState.TITLE

    def run(self, max_frames: int | None = None) -> int:
        accumulator = 0.0
        running = True
        frames = 0
        jump_pressed = False
        jump_released = False
        fire_pressed = False

        while running:
            dt = min(self.clock.tick(120) / 1000.0, 0.25)
            accumulator += dt

            for event in pygame.event.get():
                running, jump_pressed, jump_released, fire_pressed = self._handle_event(
                    event,
                    running,
                    jump_pressed,
                    jump_released,
                    fire_pressed,
                )

            while self.state is AppState.PLAYING and accumulator >= FIXED_DT:
                keys = pygame.key.get_pressed()
                jump_held = any(keys[key] for key in JUMP_KEYS)
                self.world.update(
                    keys,
                    jump_pressed,
                    jump_held,
                    jump_released,
                    FIXED_DT,
                    fire_pressed=fire_pressed,
                )
                self.audio.play_events(self.world.pop_events())
                jump_pressed = False
                jump_released = False
                fire_pressed = False
                accumulator -= FIXED_DT
                # Auto-return to title after a Game Over screen has been shown.
                if (
                    self.world.state is WorldState.GAMEOVER
                    and self.world.gameover_timer <= 0
                ):
                    self.world.restart(reset_score=True)
                    self.state = AppState.TITLE
                    break
            if self.state is not AppState.PLAYING:
                accumulator = 0.0

            self._update_music()
            self._draw()
            frames += 1
            if max_frames is not None and frames >= max_frames:
                running = False

        pygame.quit()
        return 0

    def _update_music(self) -> None:
        if self.state is AppState.TITLE:
            self.music.stop()
            return
        if self.state is AppState.PAUSED:
            return
        world = self.world
        is_complete = world.state in (WorldState.COMPLETE, WorldState.FLAGPOLE, WorldState.LEVEL_END_WALK)
        is_gameover = world.state is WorldState.GAMEOVER
        self.music.update(
            world.theme,
            low_time=world.time_remaining < LOW_TIME_THRESHOLD,
            star_power=world.player.star_timer > 0,
            level_complete=is_complete,
            gameover=is_gameover,
        )

    def _load_level(self) -> LevelData:
        if self.level_path is None:
            return generate_template_level()
        return load_level(self.level_path)

    def _handle_event(
        self,
        event: pygame.event.Event,
        running: bool,
        jump_pressed: bool,
        jump_released: bool,
        fire_pressed: bool,
    ) -> tuple[bool, bool, bool, bool]:
        if event.type == pygame.QUIT:
            return False, jump_pressed, jump_released, fire_pressed
        if event.type == pygame.KEYUP and event.key in JUMP_KEYS:
            return running, jump_pressed, True, fire_pressed
        if event.type != pygame.KEYDOWN:
            return running, jump_pressed, jump_released, fire_pressed

        if self.state is AppState.TITLE:
            running, jump_pressed = self._handle_title_key(event.key, running, jump_pressed)
            return running, jump_pressed, jump_released, fire_pressed
        if self.state is AppState.PAUSED:
            running, jump_pressed = self._handle_pause_key(event.key, running, jump_pressed)
            return running, jump_pressed, jump_released, fire_pressed
        running, jump_pressed, fire_pressed = self._handle_playing_key(
            event.key, running, jump_pressed, fire_pressed
        )
        return running, jump_pressed, jump_released, fire_pressed

    def _handle_title_key(self, key: int, running: bool, jump_pressed: bool) -> tuple[bool, bool]:
        if key == pygame.K_ESCAPE:
            return False, jump_pressed
        if key in {pygame.K_DOWN, pygame.K_s}:
            self._move_level_selection(1)
        elif key in {pygame.K_UP, pygame.K_w}:
            self._move_level_selection(-1)
        elif key in {pygame.K_PAGEDOWN}:
            self._move_level_selection(10)
        elif key in {pygame.K_PAGEUP}:
            self._move_level_selection(-10)
        elif key == pygame.K_HOME:
            self.selected_level_index = 0
        elif key == pygame.K_END:
            if self.level_paths:
                self.selected_level_index = len(self.level_paths) - 1
        elif key in {pygame.K_RETURN, pygame.K_SPACE, *JUMP_KEYS}:
            self._start_selected_level()
        return running, jump_pressed

    def _handle_pause_key(self, key: int, running: bool, jump_pressed: bool) -> tuple[bool, bool]:
        if key == pygame.K_ESCAPE:
            self.state = AppState.TITLE
        elif key in {pygame.K_p, pygame.K_RETURN, pygame.K_SPACE}:
            self.state = AppState.PLAYING
        elif key == pygame.K_r:
            self.world.restart(reset_score=True)
            self.state = AppState.PLAYING
        return running, jump_pressed

    def _handle_playing_key(
        self,
        key: int,
        running: bool,
        jump_pressed: bool,
        fire_pressed: bool = False,
    ) -> tuple[bool, bool, bool]:
        if key == pygame.K_ESCAPE:
            return False, jump_pressed, fire_pressed
        if key == pygame.K_p:
            self.state = AppState.PAUSED
        elif key == pygame.K_TAB:
            self.state = AppState.TITLE
        elif key == pygame.K_r:
            self.world.restart(reset_score=True)
        elif key in JUMP_KEYS:
            jump_pressed = True
        elif key in FIRE_KEYS:
            fire_pressed = True
        return running, jump_pressed, fire_pressed

    def _move_level_selection(self, direction: int) -> None:
        if not self.level_paths:
            return
        self.selected_level_index = (self.selected_level_index + direction) % len(self.level_paths)

    def _start_selected_level(self) -> None:
        if self.level_paths:
            self.level_path = self.level_paths[self.selected_level_index]
        self.level = self._load_level()
        self.world = GameWorld(self.level)
        self.state = AppState.PLAYING

    def _initial_level_index(self, level_path: Path | None) -> int:
        if level_path is None or not self.level_paths:
            return 0
        resolved = level_path.resolve()
        try:
            return self.level_paths.index(resolved)
        except ValueError:
            return 0

    def _draw(self) -> None:
        if self.state is AppState.TITLE:
            self.renderer.draw_title(self.level_paths, self.selected_level_index)
        elif self.state is AppState.PAUSED:
            self.renderer.draw(self.world, overlay="PAUSED")
        else:
            self.renderer.draw(self.world)


__all__ = ["AppState", "GameWorld", "PygameMario", "WorldState"]
