from __future__ import annotations

from enum import Enum
from pathlib import Path

import pygame

from .assets import AudioManager, SpriteBank
from .audio import MusicManager
from .entities import PipeState
from .level import LevelData, find_default_level, generate_template_level, load_level
from .paths import ProjectPaths
from .renderer import Renderer
from .settings import (
    FIXED_DT,
    LOW_TIME_THRESHOLD,
    PIPE_ANIM_DURATION,
    SCREEN_SIZE,
    TILE_SIZE,
)
from .ui_font import BitmapFont
from .world import GameWorld, WorldState


class AppState(Enum):
    TITLE = "title"
    PLAYING = "playing"
    PAUSED = "paused"
    INTERMISSION = "intermission"
    VICTORY = "victory"


JUMP_KEYS = {pygame.K_SPACE, pygame.K_z, pygame.K_k}
FIRE_KEYS = {pygame.K_x, pygame.K_j}


class PygameMario:
    def __init__(self, level_path: Path | None, paths: ProjectPaths, audio_enabled: bool = True) -> None:
        pygame.init()
        pygame.joystick.init()
        pygame.display.set_caption("Super Mario PYGAMECE")
        self.screen = pygame.display.set_mode(SCREEN_SIZE)
        self.clock = pygame.time.Clock()
        self.paths = paths
        self.sprites = SpriteBank(self.paths.atlas_metadata, self.paths.atlas_dir, TILE_SIZE)

        font_strip = self.sprites.native_surface("font")
        ui_font_path = self.paths.atlas_dir / "ui_font.json"
        self.bitmap_font = BitmapFont(font_strip, ui_font_path if ui_font_path.exists() else None)

        self.renderer = Renderer(self.screen, self.sprites, self.bitmap_font)
        self.audio = AudioManager(self.paths.sounds_dir, enabled=audio_enabled)
        self.music = MusicManager(self.paths.sounds_dir, enabled=audio_enabled)
        self.level_paths = self.paths.available_levels()
        self.selected_level_index = self._initial_level_index(level_path)
        self.level_path = level_path or find_default_level(self.paths)
        self.level = self._load_level()
        self.player_count = 1
        self.world = GameWorld(self.level)
        self.fullscreen = False
        self.debug_overlay = False
        self.authentic_mode = False
        self._stage_availability_cache: list[list[bool]] | None = None
        self._gamepad: pygame.joystick.JoystickType | None = None
        self._gamepad_jump_held = False
        self._gamepad_fire_held = False
        self._detect_gamepad()

        # Intermission / victory state
        self._pending_world: GameWorld | None = None
        self.intermission_timer = 0.0
        self.intermission_world_display = "1-1"
        self.intermission_lives = 3
        self.intermission_character = "MARIO"
        self.victory_timer = 0.0

        # Title-screen menu state (mirrors C++ MenuSystem)
        self.menu_main_index = 0       # 0=1P, 1=2P, 2=OPTIONS, 3=ABOUT
        self.menu_select_world = False
        self.menu_selected_world = 0   # 0-7
        self.menu_selected_stage = 0   # 0-3

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
                    event, running, jump_pressed, jump_released, fire_pressed,
                )

            # ---- PLAYING fixed-step loop ----
            while self.state is AppState.PLAYING and accumulator >= FIXED_DT:
                keys = self._combined_keys(pygame.key.get_pressed())
                jump_held = any(keys[key] for key in JUMP_KEYS)
                self.world.update(
                    keys, jump_pressed, jump_held, jump_released, FIXED_DT,
                    fire_pressed=fire_pressed,
                )
                self.audio.play_events(self.world.pop_events())
                jump_pressed = False
                jump_released = False
                fire_pressed = False
                accumulator -= FIXED_DT

                if self.world.pending_level_warp:
                    self._do_level_warp(self.world.pending_level_warp)
                    break

                # Skip level-complete bonus on jump/fire (after 1 s of COMPLETE state).
                if (
                    self.world.state is WorldState.COMPLETE
                    and (jump_pressed or fire_pressed)
                    and self.world.complete_timer >= 1.0
                ):
                    self.world.skip_complete = True

                # Advance when bonus countdown finished.
                if (
                    self.world.state is WorldState.COMPLETE
                    and self.world.time_bonus_remaining == 0
                    and (self.world.complete_timer >= 3.7 or self.world.skip_complete)
                ):
                    self._advance_to_next_level()
                    break

                # Wait for jump/fire after the 3-second game-over delay.
                if (
                    self.world.state is WorldState.GAMEOVER
                    and self.world.gameover_timer <= 0
                    and (jump_pressed or fire_pressed)
                ):
                    self._continue_after_gameover()
                    jump_pressed = False
                    fire_pressed = False
                    break

            # ---- INTERMISSION frame-rate timer ----
            if self.state is AppState.INTERMISSION:
                self.intermission_timer += dt
                if (jump_pressed or fire_pressed) and self.intermission_timer >= 1.0:
                    self._end_intermission()
                    jump_pressed = False
                    fire_pressed = False
                elif self.intermission_timer >= 3.5:
                    self._end_intermission()

            # ---- VICTORY frame-rate timer ----
            if self.state is AppState.VICTORY:
                self.victory_timer += dt
                if (jump_pressed or fire_pressed) and self.victory_timer >= 3.0:
                    self.state = AppState.TITLE
                    jump_pressed = False
                    fire_pressed = False

            if self.state not in (AppState.PLAYING,):
                accumulator = 0.0

            self._update_music()
            self._draw()
            frames += 1
            if max_frames is not None and frames >= max_frames:
                running = False

        pygame.quit()
        return 0

    # ------------------------------------------------------------------
    # Level transitions
    # ------------------------------------------------------------------

    def _advance_to_next_level(self) -> None:
        import re

        stem = self.level_path.stem if self.level_path else ""
        match = re.fullmatch(r"(\d+)-(\d+)[a-z]*", stem, re.IGNORECASE)
        next_path = None
        crossed_world = False
        if match:
            world_no, stage_no = int(match.group(1)), int(match.group(2))
            crossed_world = stage_no == 4
            world_no, stage_no = (world_no, stage_no + 1) if stage_no < 4 else (world_no + 1, 1)
            wanted = f"{world_no}-{stage_no}"
            next_path = next((p for p in self.level_paths if p.stem == wanted), None)

        if next_path is None:
            self._enter_victory()
            return

        self.world.sync_to_session()
        sessions = self.world.sessions
        active = self.world.active_player_index
        self.level_path = next_path
        self.selected_level_index = self._initial_level_index(next_path)
        self.level = self._load_level()
        new_world = GameWorld(self.level)
        new_world.authentic_movement = self.authentic_mode
        new_world.player_count = self.player_count
        new_world.sessions = sessions
        new_world.active_player_index = active
        new_world.apply_from_session()
        new_world._apply_state_change(sessions[active].state)

        if crossed_world:
            self._pending_world = new_world
            character = sessions[active].character if sessions else "MARIO"
            self._enter_intermission(new_world.world_display, new_world.lives, character)
        else:
            self.world = new_world
            self.state = AppState.PLAYING

    def _enter_intermission(self, world_display: str, lives: int, character: str = "MARIO") -> None:
        self.intermission_timer = 0.0
        self.intermission_world_display = world_display
        self.intermission_lives = lives
        self.intermission_character = character
        self.state = AppState.INTERMISSION
        self.audio.play_events(("intermission",))

    def _end_intermission(self) -> None:
        if self._pending_world is not None:
            self.world = self._pending_world
            self.world.authentic_movement = self.authentic_mode
            self._pending_world = None
        self.state = AppState.PLAYING

    def _enter_victory(self) -> None:
        self.victory_timer = 0.0
        self.state = AppState.VICTORY
        self.audio.play_events(("princessmusic",))

    def _do_level_warp(self, dest_level_name: str) -> None:
        dest_stem = Path(dest_level_name).stem
        found_path = None
        for p in self.level_paths:
            if p.stem == dest_stem or p.name == dest_level_name:
                found_path = p
                break

        if not found_path:
            try_path = self.paths.local_assets / "levels" / f"{dest_stem}.json"
            if try_path.exists():
                found_path = try_path

        if found_path:
            self.world.sync_to_session()
            active_player_index = self.world.active_player_index
            sessions = self.world.sessions
            time_remaining = self.world.time_remaining

            dest_x = self.world.player.pipe_dest_x
            dest_y = self.world.player.pipe_dest_y
            exit_facing_right = self.world.player.pipe_exit_facing_right
            exit_horizontal = self.world.player.pipe_exit_horizontal

            self.level_path = found_path
            self.level = self._load_level()
            self.world = GameWorld(self.level)
            self.world.authentic_movement = self.authentic_mode
            self.world.sessions = sessions
            self.world.active_player_index = active_player_index
            self.world.apply_from_session()
            self.world._apply_state_change(sessions[active_player_index].state)
            self.world.time_remaining = time_remaining

            self.world.player.pos.x = dest_x
            self.world.player.pos.y = dest_y
            self.world.player.facing = 1 if exit_facing_right else -1
            self.world.player.pipe_state = (
                PipeState.EXITING_RIGHT if exit_horizontal and exit_facing_right
                else (PipeState.EXITING_LEFT if exit_horizontal else PipeState.EXITING_UP)
            )
            self.world.player.pipe_timer = PIPE_ANIM_DURATION
            self.world.camera_x = max(0.0, self.world.player.pos.x - SCREEN_SIZE[0] * 0.5)
        else:
            self.world.pending_level_warp = None

    # ------------------------------------------------------------------
    # Music
    # ------------------------------------------------------------------

    def _update_music(self) -> None:
        if self.state in (AppState.TITLE, AppState.INTERMISSION, AppState.VICTORY):
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

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

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
        if event.type == pygame.JOYDEVICEADDED:
            self._detect_gamepad()
            return running, jump_pressed, jump_released, fire_pressed
        if event.type == pygame.JOYDEVICEREMOVED:
            self._detect_gamepad()
            self._gamepad_jump_held = False
            self._gamepad_fire_held = False
            return running, jump_pressed, jump_released, fire_pressed
        if event.type == pygame.JOYBUTTONDOWN:
            if event.button in {0, 1}:
                self._gamepad_jump_held = True
                jump_pressed = True
            elif event.button in {2, 3, 5}:
                self._gamepad_fire_held = True
                fire_pressed = True
            elif event.button in {6, 7}:
                if self.state is AppState.PLAYING:
                    self.state = AppState.PAUSED
                elif self.state is AppState.PAUSED:
                    self.state = AppState.PLAYING
            return running, jump_pressed, jump_released, fire_pressed
        if event.type == pygame.JOYBUTTONUP:
            if event.button in {0, 1}:
                self._gamepad_jump_held = False
                jump_released = True
            elif event.button in {2, 3, 5}:
                self._gamepad_fire_held = False
            return running, jump_pressed, jump_released, fire_pressed
        if event.type == pygame.KEYUP and event.key in JUMP_KEYS:
            return running, jump_pressed, True, fire_pressed
        if event.type != pygame.KEYDOWN:
            return running, jump_pressed, jump_released, fire_pressed

        if event.key == pygame.K_F11 or (
            event.key == pygame.K_RETURN and (event.mod & pygame.KMOD_ALT)
        ):
            self._toggle_fullscreen()
            return running, jump_pressed, jump_released, fire_pressed
        if event.key == pygame.K_F3:
            self.debug_overlay = not self.debug_overlay
            return running, jump_pressed, jump_released, fire_pressed
        if event.key == pygame.K_F6:
            self.authentic_mode = not self.authentic_mode
            self.world.authentic_movement = self.authentic_mode
            return running, jump_pressed, jump_released, fire_pressed

        if self.state is AppState.TITLE:
            running, jump_pressed = self._handle_title_key(event.key, running, jump_pressed)
        elif self.state is AppState.PAUSED:
            running, jump_pressed = self._handle_pause_key(event.key, running, jump_pressed)
        elif self.state is AppState.INTERMISSION:
            if event.key == pygame.K_ESCAPE:
                self._pending_world = None
                self.state = AppState.TITLE
            elif event.key in JUMP_KEYS or event.key in FIRE_KEYS:
                jump_pressed = True
        elif self.state is AppState.VICTORY:
            if event.key == pygame.K_ESCAPE:
                self.state = AppState.TITLE
            elif event.key in JUMP_KEYS or event.key in FIRE_KEYS:
                jump_pressed = True
        else:
            running, jump_pressed, fire_pressed = self._handle_playing_key(
                event.key, running, jump_pressed, fire_pressed
            )
        return running, jump_pressed, jump_released, fire_pressed

    def _handle_title_key(self, key: int, running: bool, jump_pressed: bool) -> tuple[bool, bool]:
        if key == pygame.K_ESCAPE:
            if self.menu_select_world:
                self.menu_select_world = False
                return running, jump_pressed
            return False, jump_pressed

        if self.menu_select_world:
            if key in {pygame.K_UP, pygame.K_w}:
                self._menu_move_stage(-1)
            elif key in {pygame.K_DOWN, pygame.K_s}:
                self._menu_move_stage(1)
            elif key in {pygame.K_LEFT, pygame.K_a}:
                self._menu_move_world(-1)
            elif key in {pygame.K_RIGHT, pygame.K_d}:
                self._menu_move_world(1)
            elif key in {pygame.K_RETURN, pygame.K_SPACE, *JUMP_KEYS}:
                self._start_world_stage_level()
        else:
            if key in {pygame.K_UP, pygame.K_w}:
                self.menu_main_index = (self.menu_main_index - 1) % 4
            elif key in {pygame.K_DOWN, pygame.K_s}:
                self.menu_main_index = (self.menu_main_index + 1) % 4
            elif key == pygame.K_t:
                self.player_count = 2 if self.player_count == 1 else 1
            elif key == pygame.K_1:
                self.player_count = 1
            elif key == pygame.K_2:
                self.player_count = 2
            elif key in {pygame.K_RETURN, pygame.K_SPACE, *JUMP_KEYS}:
                if self.menu_main_index == 0:
                    self.player_count = 1
                    self.menu_select_world = True
                elif self.menu_main_index == 1:
                    self.player_count = 2
                    self.menu_select_world = True
                # OPTIONS (2) / ABOUT (3): not yet implemented
        return running, jump_pressed

    def _stage_availability(self) -> list[list[bool]]:
        if self._stage_availability_cache is not None:
            return [row[:] for row in self._stage_availability_cache]

        import re
        available = [[False] * 4 for _ in range(8)]
        for p in self.level_paths:
            m = re.fullmatch(r"(\d+)-(\d+)", p.stem)
            if m:
                w, s = int(m.group(1)) - 1, int(m.group(2)) - 1
                if 0 <= w < 8 and 0 <= s < 4:
                    available[w][s] = True
        self._stage_availability_cache = available
        return [row[:] for row in available]

    def _menu_move_world(self, direction: int) -> None:
        avail = self._stage_availability()
        for _ in range(8):
            self.menu_selected_world = (self.menu_selected_world + direction) % 8
            if any(avail[self.menu_selected_world]):
                for s in range(4):
                    if avail[self.menu_selected_world][s]:
                        self.menu_selected_stage = s
                        break
                return

    def _menu_move_stage(self, direction: int) -> None:
        avail = self._stage_availability()
        for _ in range(4):
            self.menu_selected_stage = (self.menu_selected_stage + direction) % 4
            if avail[self.menu_selected_world][self.menu_selected_stage]:
                return

    def _start_world_stage_level(self) -> None:
        stem = f"{self.menu_selected_world + 1}-{self.menu_selected_stage + 1}"
        found = next((p for p in self.level_paths if p.stem == stem), None)
        if found:
            self.level_path = found
            self.selected_level_index = next(
                (i for i, p in enumerate(self.level_paths) if p == found), 0
            )
            self.menu_select_world = False
            self._start_selected_level()

    def _handle_pause_key(self, key: int, running: bool, jump_pressed: bool) -> tuple[bool, bool]:
        if key == pygame.K_ESCAPE:
            self.state = AppState.TITLE
        elif key in {pygame.K_p, pygame.K_RETURN, pygame.K_SPACE}:
            self.state = AppState.PLAYING
        elif key == pygame.K_r:
            self.world.restart(reset_score=True, player_count=self.player_count)
            self.state = AppState.PLAYING
        return running, jump_pressed

    def _handle_playing_key(
        self,
        key: int,
        running: bool,
        jump_pressed: bool,
        fire_pressed: bool = False,
    ) -> tuple[bool, bool, bool]:
        if self.world.state is WorldState.GAMEOVER and self.world.gameover_timer <= 0:
            if key in {pygame.K_ESCAPE, pygame.K_TAB}:
                self._return_to_title_after_gameover()
                return running, jump_pressed, fire_pressed
            if key in JUMP_KEYS:
                jump_pressed = True
                return running, jump_pressed, fire_pressed
            if key in FIRE_KEYS:
                fire_pressed = True
                return running, jump_pressed, fire_pressed

        if key == pygame.K_ESCAPE:
            return False, jump_pressed, fire_pressed
        if key == pygame.K_p:
            self.state = AppState.PAUSED
        elif key == pygame.K_TAB:
            self.state = AppState.TITLE
        elif key == pygame.K_r:
            self.world.restart(reset_score=True, player_count=self.player_count)
        elif key in JUMP_KEYS:
            jump_pressed = True
        elif key in FIRE_KEYS:
            fire_pressed = True
        return running, jump_pressed, fire_pressed

    def _continue_after_gameover(self) -> None:
        self.world.restart(reset_score=True, player_count=self.player_count)
        self.world.authentic_movement = self.authentic_mode
        self.state = AppState.PLAYING

    def _return_to_title_after_gameover(self) -> None:
        self.world.restart(reset_score=True, player_count=self.player_count)
        self.state = AppState.TITLE

    def _move_level_selection(self, direction: int) -> None:
        if not self.level_paths:
            return
        self.selected_level_index = (self.selected_level_index + direction) % len(self.level_paths)

    def _start_selected_level(self) -> None:
        if self.level_paths:
            self.level_path = self.level_paths[self.selected_level_index]
        self.level = self._load_level()
        new_world = GameWorld(self.level)
        new_world.authentic_movement = self.authentic_mode
        new_world.restart(reset_score=True, player_count=self.player_count)
        self._pending_world = new_world
        character = "MARIO"
        self._enter_intermission(new_world.world_display, new_world.lives, character)

    def _initial_level_index(self, level_path: Path | None) -> int:
        if level_path is None or not self.level_paths:
            return 0
        resolved = level_path.resolve()
        try:
            return self.level_paths.index(resolved)
        except ValueError:
            return 0

    # ------------------------------------------------------------------
    # Draw dispatch
    # ------------------------------------------------------------------

    def _draw(self) -> None:
        if self.state is AppState.TITLE:
            self.renderer.draw_title(
                self.level_paths,
                self.player_count,
                main_index=self.menu_main_index,
                select_world=self.menu_select_world,
                selected_world=self.menu_selected_world,
                selected_stage=self.menu_selected_stage,
                stage_available=self._stage_availability(),
            )
        elif self.state is AppState.PAUSED:
            self.renderer.draw(self.world, paused=True, debug=self.debug_overlay, fps=self.clock.get_fps())
        elif self.state is AppState.INTERMISSION:
            self.renderer.draw_intermission(
                self.intermission_world_display,
                self.intermission_lives,
                self.intermission_character,
            )
        elif self.state is AppState.VICTORY:
            self.renderer.draw_victory(self.victory_timer)
        else:
            self.renderer.draw(self.world, debug=self.debug_overlay, fps=self.clock.get_fps())

    def _toggle_fullscreen(self) -> None:
        self.fullscreen = not self.fullscreen
        flags = pygame.FULLSCREEN if self.fullscreen else 0
        self.screen = pygame.display.set_mode(SCREEN_SIZE, flags)
        self.renderer.set_surface(self.screen)

    def _detect_gamepad(self) -> None:
        self._gamepad = None
        if pygame.joystick.get_count() > 0:
            self._gamepad = pygame.joystick.Joystick(0)
            self._gamepad.init()

    def _combined_keys(self, keyboard: pygame.key.ScancodeWrapper) -> _CombinedKeys:
        left = right = up = down = False
        if self._gamepad is not None:
            try:
                axis_x = self._gamepad.get_axis(0)
                axis_y = self._gamepad.get_axis(1)
                hat_x, hat_y = self._gamepad.get_hat(0) if self._gamepad.get_numhats() else (0, 0)
                left = axis_x < -0.35 or hat_x < 0
                right = axis_x > 0.35 or hat_x > 0
                up = axis_y < -0.35 or hat_y > 0
                down = axis_y > 0.35 or hat_y < 0
            except pygame.error:
                self._gamepad = None
        return _CombinedKeys(
            keyboard,
            left=left,
            right=right,
            up=up,
            down=down,
            jump=self._gamepad_jump_held,
            fire=self._gamepad_fire_held,
        )


class _CombinedKeys:
    def __init__(
        self,
        keyboard: pygame.key.ScancodeWrapper,
        *,
        left: bool,
        right: bool,
        up: bool,
        down: bool,
        jump: bool,
        fire: bool,
    ) -> None:
        self._keyboard = keyboard
        self._pressed = {
            pygame.K_LEFT: left,
            pygame.K_a: left,
            pygame.K_RIGHT: right,
            pygame.K_d: right,
            pygame.K_UP: up,
            pygame.K_w: up,
            pygame.K_DOWN: down,
            pygame.K_s: down,
            pygame.K_SPACE: jump,
            pygame.K_z: jump,
            pygame.K_k: jump,
            pygame.K_x: fire,
            pygame.K_j: fire,
            pygame.K_LSHIFT: fire,
            pygame.K_RSHIFT: fire,
        }

    def __getitem__(self, key: int) -> bool:
        return bool(self._keyboard[key] or self._pressed.get(key, False))


__all__ = ["AppState", "GameWorld", "PygameMario", "WorldState"]
