from __future__ import annotations

import math
from pathlib import Path

import pygame

from .atlas import SpriteBank
from .entities import SeesawPlatform
from .enemy import ENEMY_DEAD_FRAMES as _ENEMY_DEAD_FRAMES
from .settings import (
    FS_HUD,
    FS_MED,
    FS_SUB,
    FS_TITLE,
    HUD_ROW1,
    HUD_ROW2,
    HUD_X_COINS,
    HUD_X_LIVES,
    HUD_X_MARIO,
    HUD_X_TIME,
    HUD_X_WORLD,
    SCREEN_SIZE,
    TILE_SIZE,
)
from .ui_font import BitmapFont
from .world import GameWorld, WorldState

_W, _H = SCREEN_SIZE

_WHITE = (255, 255, 255)
_YELLOW = (255, 255, 0)
_RED_BLINK = (255, 80, 80)
_POPUP_YELLOW = (255, 220, 60)
_POPUP_1UP = (112, 255, 112)
_GREY_SUB = (200, 200, 200)
_BONUS_GOLD = (255, 200, 50)
_VICTORY_YELLOW = (255, 255, 100)


class Renderer:
    def __init__(self, screen: pygame.Surface, sprites: SpriteBank, font: BitmapFont) -> None:
        self._screen = screen
        self._sprites = sprites
        self._font = font

    # ------------------------------------------------------------------
    # Main game draw
    # ------------------------------------------------------------------

    def draw(self, world: GameWorld, paused: bool = False) -> None:
        self._screen.fill(world.theme.sky)
        cam_x = round(world.camera_x)
        cam_y = round(world.camera_y)
        visible = pygame.Rect(
            cam_x - TILE_SIZE,
            cam_y - TILE_SIZE * 2,
            SCREEN_SIZE[0] + TILE_SIZE * 2,
            SCREEN_SIZE[1] + TILE_SIZE * 4,
        )

        self._draw_background(world, cam_x, cam_y, visible)
        self._draw_decorations(world, cam_x, cam_y, visible)
        self._draw_tiles(world, cam_x, cam_y, visible)
        self._draw_platforms(world, cam_x, cam_y, visible)
        self._draw_bumps(world, cam_x, cam_y, visible)
        self._draw_collectibles(world, cam_x, cam_y, visible)
        self._draw_enemies(world, cam_x, cam_y, visible)
        self._draw_fireballs(world, cam_x, cam_y, visible)
        self._draw_enemy_projectiles(world, cam_x, cam_y, visible)
        self._draw_particles(world, cam_x, cam_y, visible)
        self._draw_hazards(world, cam_x, cam_y)
        self._draw_goals(world, cam_x, cam_y)
        self._draw_player(world, cam_x, cam_y)
        self._draw_popups(world, cam_x, cam_y)
        self._draw_hud(world)

        if paused:
            self._draw_paused()
        elif world.state is WorldState.COMPLETE:
            self._draw_level_complete(world)
        elif world.state is WorldState.TIMEOUT:
            self._draw_time_up()
        elif world.state is WorldState.GAMEOVER:
            self._draw_game_over(world)

        pygame.display.flip()

    # ------------------------------------------------------------------
    # Standalone screens (called by game.py for non-gameplay states)
    # ------------------------------------------------------------------

    def draw_title(
        self,
        levels: tuple[Path, ...],
        player_count: int = 1,
        *,
        main_index: int = 0,
        select_world: bool = False,
        selected_world: int = 0,
        selected_stage: int = 0,
        stage_available: list[list[bool]] | None = None,
    ) -> None:
        # Design space mirrors C++ MenuSystem: 800×448
        _DW, _DH = 800.0, 448.0
        scale = min(_W / _DW, _H / _DH)
        off_x = (_W - _DW * scale) * 0.5
        off_y = (_H - _DH * scale) * 0.5

        def sx(x: float) -> float:
            return off_x + x * scale

        def sy(y: float) -> float:
            return off_y + y * scale

        def ss(s: int) -> int:
            return max(1, round(s * scale))

        self._screen.fill((0, 0, 0))

        # Logo "super_mario_bros" at design (80, 48)
        logo_native = self._sprites.native_size("super_mario_bros")
        if logo_native:
            lw = max(1, round(logo_native[0] * scale))
            lh = max(1, round(logo_native[1] * scale))
            self._screen.blit(
                self._sprites.get("super_mario_bros", (lw, lh)),
                (round(sx(80)), round(sy(48))),
            )

        # Mario sprite at design (800/3, 448/2), 4× native scale
        mario_name = "mario_stand" if self._sprites.native_size("mario_stand") else "mario_st"
        mario_native = self._sprites.native_size(mario_name)
        if mario_native:
            ms = 4.0 * scale
            mw = max(1, round(mario_native[0] * ms))
            mh = max(1, round(mario_native[1] * ms))
            self._screen.blit(
                self._sprites.get(mario_name, (mw, mh)),
                (round(sx(_DW / 3)), round(sy(_DH / 2))),
            )

        # 4 menu items (C++ positions)
        f = self._font
        fs = ss(16)
        _ITEMS = (
            ("1 PLAYER GAME", 178, 276),
            ("2 PLAYER GAME", 178, 308),
            ("OPTIONS", 222, 340),
            ("ABOUT", 237, 372),
        )
        for text, dx, dy in _ITEMS:
            f.draw(self._screen, text, sx(dx), sy(dy), fs)

        # Active option marker at design (item.x − 32, item.y)
        if 0 <= main_index < len(_ITEMS):
            _, item_dx, item_dy = _ITEMS[main_index]
            mx = round(sx(item_dx - 32))
            my = round(sy(item_dy))
            marker_native = self._sprites.native_size("active_option")
            if marker_native:
                aw = max(1, round(marker_native[0] * scale))
                ah = max(1, round(marker_native[1] * scale))
                self._screen.blit(self._sprites.get("active_option", (aw, ah)), (mx, my))
            else:
                f.draw(self._screen, ">", mx, my, fs)

        # Footer with black shadow + white text (C++ renderFooter)
        footer = "WWW.LUKASZJAKOWSKI.PL"
        fs8 = ss(8)
        fx = sx(4)
        fy = sy(_DH - 4 - 8)
        f.draw(self._screen, footer, fx, fy, fs8, (0, 0, 0))
        f.draw(self._screen, footer, fx + scale, fy - scale, fs8)

        # World-select overlay panel (C++ renderWorldSelect)
        if select_world:
            self._draw_world_select_panel(
                selected_world, selected_stage,
                stage_available or [[True] * 4 for _ in range(8)],
                sx, sy, ss, scale,
            )

        pygame.display.flip()

    def _draw_world_select_panel(
        self,
        selected_world: int,
        selected_stage: int,
        stage_available: list[list[bool]],
        sx, sy, ss, scale: float,
    ) -> None:
        # Panel at design (122, 280), 306×72, near-black fill + white inner border
        px, py = round(sx(122)), round(sy(280))
        pw, ph = round(306 * scale), round(72 * scale)
        panel = pygame.Surface((pw, ph), pygame.SRCALPHA)
        panel.fill((4, 4, 4, 235))
        self._screen.blit(panel, (px, py))
        pygame.draw.rect(self._screen, (255, 255, 255), (px + 1, py + 1, pw - 2, ph - 2), 1)

        f = self._font
        fs = ss(16)

        # "SELECT WORLD" centered in panel
        title = "SELECT WORLD"
        tw = f.width(title, fs)
        f.draw(self._screen, title, px + (pw - tw) // 2, round(py + 16 * scale), fs)

        # 8 world slots; selected world shows "W-S", others show "W"
        extra_x = 0
        for i in range(8):
            base_x = 122 + 16 * (i + 1) + 16 * i + extra_x
            slot_x = round(sx(base_x))
            slot_y = round(sy(280 + 16 + 24))
            if i == selected_world:
                label = f"{i + 1}-{selected_stage + 1}"
                s_avail = stage_available[i][selected_stage] if i < len(stage_available) else False
                color = _WHITE if s_avail else (120, 120, 120)
                f.draw(self._screen, label, slot_x, slot_y, fs, color)
                extra_x = 32
            else:
                label = str(i + 1)
                w_avail = any(stage_available[i]) if i < len(stage_available) else False
                color = (90, 90, 90) if w_avail else (35, 35, 35)
                f.draw(self._screen, label, slot_x, slot_y, fs, color)

    def draw_intermission(self, world_display: str, lives: int, character: str = "MARIO") -> None:
        self._screen.fill((0, 0, 0))
        f = self._font
        cx = _W // 2
        cy = int(_H * 0.40)
        line1 = f"WORLD {world_display}"
        line2 = f"{character}  x  {lives:02d}"
        f.draw_shadow(self._screen, line1, cx - f.width(line1, FS_TITLE) // 2, cy, FS_TITLE)
        f.draw_shadow(self._screen, line2, cx - f.width(line2, FS_MED) // 2, cy + 50, FS_MED)
        pygame.display.flip()

    def draw_victory(self, timer: float) -> None:
        self._screen.fill((0, 0, 0))
        f = self._font
        cx = _W // 2
        cy = int(_H * 0.38)
        line1 = "THANK YOU MARIO!"
        f.draw_shadow(self._screen, line1, cx - f.width(line1, FS_TITLE) // 2, cy, FS_TITLE, _VICTORY_YELLOW)
        if timer >= 1.5:
            line2 = "YOUR QUEST IS OVER."
            f.draw_shadow(self._screen, line2, cx - f.width(line2, FS_HUD) // 2, cy + 55, FS_HUD)
        if timer >= 3.0:
            line3 = "PRESS JUMP TO RETURN"
            f.draw(self._screen, line3, cx - f.width(line3, FS_SUB) // 2, cy + 100, FS_SUB, _GREY_SUB)
        pygame.display.flip()

    # ------------------------------------------------------------------
    # Game-state overlays
    # ------------------------------------------------------------------

    def _draw_paused(self) -> None:
        f = self._font
        veil = pygame.Surface(SCREEN_SIZE, pygame.SRCALPHA)
        veil.fill((0, 0, 0, 140))
        self._screen.blit(veil, (0, 0))
        cx = _W // 2
        cy = int(_H * 0.45)
        title = "PAUSED"
        f.draw_shadow(self._screen, title, cx - f.width(title, FS_TITLE) // 2, cy, FS_TITLE)
        sub = "PRESS PAUSE TO CONTINUE"
        f.draw(self._screen, sub, cx - f.width(sub, FS_SUB) // 2, cy + 40, FS_SUB, _GREY_SUB)

    def _draw_game_over(self, world: GameWorld) -> None:
        f = self._font
        veil = pygame.Surface(SCREEN_SIZE, pygame.SRCALPHA)
        veil.fill((0, 0, 0, 200))
        self._screen.blit(veil, (0, 0))
        cx = _W // 2
        cy = int(_H * 0.42)
        title = "GAME OVER"
        f.draw_shadow(self._screen, title, cx - f.width(title, FS_TITLE) // 2, cy, FS_TITLE)
        lives_str = f"LIVES {world.lives:02d}"
        f.draw_shadow(self._screen, lives_str, cx - f.width(lives_str, FS_HUD) // 2, cy + 38, FS_HUD)
        if world.gameover_timer <= 0:
            prompt = "PRESS JUMP OR RUN"
            f.draw(self._screen, prompt, cx - f.width(prompt, FS_HUD) // 2, cy + 76, FS_HUD, _GREY_SUB)

    def _draw_level_complete(self, world: GameWorld) -> None:
        f = self._font
        is_castle = world.is_castle
        veil = pygame.Surface(SCREEN_SIZE, pygame.SRCALPHA)
        veil.fill((0, 0, 0, 230 if is_castle else 160))
        self._screen.blit(veil, (0, 0))
        cx = _W // 2
        cy = int(_H * 0.35)
        timer = world.complete_timer

        if is_castle:
            if timer >= 0.35:
                toad_surf = self._sprites.get("toad", (56, 56))
                self._screen.blit(toad_surf, (cx - 28, cy - 48))
                for i, line in enumerate(("THANK YOU MARIO!", "BUT OUR PRINCESS IS IN", "ANOTHER CASTLE!")):
                    f.draw_shadow(self._screen, line, cx - f.width(line, FS_HUD) // 2, cy + 28 + i * 26, FS_HUD)
            bonus_y = cy + 130
        else:
            title = "WORLD CLEAR"
            f.draw_shadow(self._screen, title, cx - f.width(title, FS_TITLE) // 2, cy, FS_TITLE, _YELLOW)
            stage = f"WORLD {world.world_display}"
            f.draw_shadow(self._screen, stage, cx - f.width(stage, FS_MED) // 2, cy + 40, FS_MED)
            bonus_y = cy + 90

        if timer >= 0.5:
            lbl = "TIME BONUS"
            f.draw_shadow(self._screen, lbl, cx - f.width(lbl, FS_HUD) // 2, bonus_y, FS_HUD)
            bonus_str = f"{world.time_bonus_remaining:05d}"
            f.draw_shadow(self._screen, bonus_str, cx - f.width(bonus_str, FS_HUD) // 2, bonus_y + 25, FS_HUD, _BONUS_GOLD)
            score_str = f"SCORE {world.score:07d}"
            f.draw_shadow(self._screen, score_str, cx - f.width(score_str, FS_HUD) // 2, bonus_y + 55, FS_HUD)

    def _draw_time_up(self) -> None:
        f = self._font
        y = _H // 2 - 24
        band = pygame.Surface((_W, FS_TITLE + 24), pygame.SRCALPHA)
        band.fill((0, 0, 0, 140))
        self._screen.blit(band, (0, y - 12))
        msg = "TIME UP!"
        f.draw_shadow(self._screen, msg, _W // 2 - f.width(msg, FS_TITLE) // 2, y, FS_TITLE, _RED_BLINK)

    # ------------------------------------------------------------------
    # HUD
    # ------------------------------------------------------------------

    def _draw_hud(self, world: GameWorld) -> None:
        f = self._font
        ticks = pygame.time.get_ticks()
        fs = FS_HUD

        character = "MARIO"
        if world.sessions and world.active_player_index < len(world.sessions):
            character = world.sessions[world.active_player_index].character

        # Row 1: labels
        f.draw_shadow(self._screen, character, HUD_X_MARIO, HUD_ROW1, fs)
        f.draw_shadow(self._screen, "COINS", HUD_X_COINS, HUD_ROW1, fs)
        f.draw_shadow(self._screen, "WORLD", HUD_X_WORLD, HUD_ROW1, fs)
        f.draw_shadow(self._screen, "TIME", HUD_X_TIME, HUD_ROW1, fs)
        f.draw_shadow(self._screen, "LIVES", HUD_X_LIVES, HUD_ROW1, fs)

        # Row 2: values
        f.draw_shadow(self._screen, f"{world.score:06d}", HUD_X_MARIO, HUD_ROW2, fs)

        # C++ HUDSystem: formatNumber(coins, 2) — just the 2-digit number, no "x" prefix
        f.draw_shadow(self._screen, f"{world.coins:02d}", HUD_X_COINS, HUD_ROW2, fs)

        f.draw_shadow(self._screen, world.world_display, HUD_X_WORLD, HUD_ROW2, fs)

        time_val = int(math.ceil(world.time_remaining))
        time_str = f"{time_val:03d}"
        if 0 < time_val < 100:
            blink_ms = 200 if time_val < 30 else 400
            if (ticks // blink_ms) % 2 == 0:
                f.draw_shadow(self._screen, time_str, HUD_X_TIME, HUD_ROW2, fs, _RED_BLINK)
        else:
            f.draw_shadow(self._screen, time_str, HUD_X_TIME, HUD_ROW2, fs)

        # C++ HUDSystem: formatNumber(lives, 2) — just the 2-digit number, no "x" prefix
        f.draw_shadow(self._screen, f"{world.lives:02d}", HUD_X_LIVES, HUD_ROW2, fs)

    # ------------------------------------------------------------------
    # World rendering helpers (all accept cam_x, cam_y)
    # ------------------------------------------------------------------

    def _draw_background(self, world: GameWorld, cam_x: int, cam_y: int, visible: pygame.Rect) -> None:
        blits: list[tuple[pygame.Surface, tuple[int, int]]] = []
        for tile_rect in world.background_tiles:
            if not visible.colliderect(tile_rect):
                continue
            sprite_name = world.background_sprites[tile_rect.topleft]
            blits.append((self._sprites.get(sprite_name), (tile_rect.x - cam_x, tile_rect.y - cam_y)))
        if blits:
            self._screen.blits(blits)

    def _draw_decorations(self, world: GameWorld, cam_x: int, cam_y: int, visible: pygame.Rect) -> None:
        blits: list[tuple[pygame.Surface, tuple[int, int]]] = []
        for rect, sprite_name in world.decoration_tiles:
            if not visible.colliderect(rect):
                continue
            blits.append((self._sprites.get(sprite_name), (rect.x - cam_x, rect.y - cam_y)))
        if blits:
            self._screen.blits(blits)

    def _draw_tiles(self, world: GameWorld, cam_x: int, cam_y: int, visible: pygame.Rect) -> None:
        question_phase = (0, 0, 0, 1, 2, 1)[int(pygame.time.get_ticks() / 130) % 6]
        blits: list[tuple[pygame.Surface, tuple[int, int]]] = []
        for tile_rect in world.solid_tiles:
            if not visible.colliderect(tile_rect):
                continue
            key = (tile_rect.x, tile_rect.y)
            sprite_name = world.tile_sprites.get(key, "gnd_red_1")
            if (
                world.tile_types.get(key) in {"Question", "QuestionBlock"}
                and sprite_name.startswith("blockq")
                and not sprite_name.endswith("_used")
            ):
                base = sprite_name.rsplit("_", 1)[0]
                sprite_name = f"{base}_{question_phase}"
            blits.append((self._sprites.get(sprite_name), (tile_rect.x - cam_x, tile_rect.y - cam_y)))
        if blits:
            self._screen.blits(blits)

    def _draw_bumps(self, world: GameWorld, cam_x: int, cam_y: int, visible: pygame.Rect) -> None:
        for bump in world.bumps:
            if not visible.colliderect(bump.rect):
                continue
            offset = int(round(-12 * (bump.timer / 0.18) * (1 - bump.timer / 0.18) * 4))
            self._screen.blit(
                self._sprites.get(bump.sprite),
                (bump.rect.x - cam_x, bump.rect.y + offset - cam_y),
            )

    def _draw_platforms(self, world: GameWorld, cam_x: int, cam_y: int, visible: pygame.Rect) -> None:
        platform_surf = self._sprites.get("platform", (32, 16))
        blits: list[tuple[pygame.Surface, tuple[int, int]]] = []
        all_platforms = (*world.moving_platforms, *world.falling_platforms, *world.seesaw_platforms)
        for p in all_platforms:
            rect = p.rect
            if not visible.colliderect(rect):
                continue
            if isinstance(p, SeesawPlatform):
                pygame.draw.line(
                    self._screen,
                    (180, 180, 180),
                    (rect.centerx - cam_x, rect.top - cam_y),
                    (rect.centerx - cam_x, round(p.y_neutral) - cam_y),
                    2,
                )
            segments = int(p.width)
            for i in range(segments):
                blits.append((platform_surf, (rect.x + i * 32 - cam_x, rect.y - cam_y)))
        if blits:
            self._screen.blits(blits)

    # C++ render sizes from Constants.h (in tiles × 32):
    # coin=0.6×0.75→19×24  star/flower/mushroom=0.75×0.75→24×24
    _COIN_SIZE = (19, 24)
    _SM_SIZE = (24, 24)   # star / mushroom / flower

    def _draw_collectibles(self, world: GameWorld, cam_x: int, cam_y: int, visible: pygame.Rect) -> None:
        for collectible in world.collectibles:
            if not visible.colliderect(collectible.rect):
                continue
            sprite = collectible.sprite
            size = (TILE_SIZE, TILE_SIZE)
            if collectible.kind == "Coin":
                phase = int(pygame.time.get_ticks() / 100) % 4
                sprite = f"coin_an{phase}"
                size = self._COIN_SIZE
            elif collectible.kind in {"FireFlower", "Flower"}:
                phase = int(pygame.time.get_ticks() / 120) % 4
                sprite = f"flower{phase}"
                size = self._SM_SIZE
            elif collectible.kind == "Star":
                phase = int(pygame.time.get_ticks() / 80) % 4
                sprite = f"star_{phase}"
                size = self._SM_SIZE
            elif collectible.kind in {"Mushroom", "OneUp"}:
                size = self._SM_SIZE
            self._screen.blit(self._sprites.get(sprite, size), (collectible.rect.x - cam_x, collectible.rect.y - cam_y))

    def _draw_enemies(self, world: GameWorld, cam_x: int, cam_y: int, visible: pygame.Rect) -> None:
        for enemy in world.enemies:
            if not visible.colliderect(enemy.body.rect):
                continue
            if not enemy.alive and enemy.death_timer <= 0:
                continue
            if not enemy.alive:
                dead_sprite = _ENEMY_DEAD_FRAMES.get(enemy.kind)
                if dead_sprite:
                    self._blit_actor(dead_sprite, enemy.body.rect, cam_x, cam_y)
                else:
                    # No dedicated dead frame: show first walk frame flipped upside-down
                    self._blit_actor(enemy.frames[0], enemy.body.rect, cam_x, cam_y, flip_y=True)
                continue
            frames = enemy.frames
            # 150ms/frame (C++ AnimationState default) ≈ 6.667 fps; kicked shell spins faster
            speed = 6.667
            if enemy.shell_state.value == "shell_kicked":
                speed = 18.0
            frame = frames[int(enemy.age * speed) % len(frames)]
            self._blit_actor(
                frame, enemy.body.rect, cam_x, cam_y,
                flip_x=enemy.body.facing < 0,
            )

    def _draw_fireballs(self, world: GameWorld, cam_x: int, cam_y: int, visible: pygame.Rect) -> None:
        for fireball in world.fireballs:
            rect = fireball.rect
            if not visible.colliderect(rect):
                continue
            if fireball.alive:
                phase = int(fireball.age * 16) % 4
                self._blit_sprite(f"fireball_{phase}", (rect.x - cam_x, rect.y - cam_y), size=(14, 14))
            else:
                phase = int((0.15 - fireball.explode_timer) * 30) % 2
                self._blit_sprite(f"fire_{phase}", (rect.x - cam_x - 6, rect.y - 6 - cam_y), size=(24, 24))

    def _draw_enemy_projectiles(self, world: GameWorld, cam_x: int, cam_y: int, visible: pygame.Rect) -> None:
        for proj in world.enemy_projectiles:
            if not proj.alive or not visible.colliderect(proj.rect):
                continue
            if proj.kind == "hammer":
                phase = int(proj.age * 18) % 4
                self._blit_sprite(f"hammer_{phase}", (proj.rect.x - cam_x, proj.rect.y - cam_y), size=(20, 20))
            elif proj.kind == "bowserfire":
                phase = int(proj.age * 12) % 2
                self._blit_sprite(
                    f"fire_{phase}", (proj.rect.x - cam_x, proj.rect.y - cam_y),
                    flip_x=proj.velocity.x < 0, size=(24, 16),
                )
            else:
                phase = int(proj.age * 12) % 2
                self._blit_sprite(f"fire_{phase}", (proj.rect.x - cam_x, proj.rect.y - cam_y), size=(20, 16))

    def _draw_particles(self, world: GameWorld, cam_x: int, cam_y: int, visible: pygame.Rect) -> None:
        for particle in world.particles:
            x = int(particle.pos.x) - cam_x
            y = int(particle.pos.y) - cam_y
            sprite = particle.sprite
            if sprite == "coin_an0":
                sprite = f"coin_an{int(particle.age * 10) % 4}"
            self._blit_sprite(sprite, (x, y), size=(16, 16))

    def _draw_hazards(self, world: GameWorld, cam_x: int, cam_y: int) -> None:
        for fire in world.upfires:
            if fire.state != 0:
                # C++ render_w=0.5, render_h=0.75 tiles → 16×24 px
                self._blit_sprite("upfire", (int(fire.pos.x) - cam_x, int(fire.pos.y) - cam_y), size=(16, 24))
        for bar in world.firebars:
            for pos in bar.segment_positions:
                self._blit_sprite("fire_0", (int(pos.x) - cam_x - 8, int(pos.y) - 8 - cam_y), size=(16, 16))

    def _draw_goals(self, world: GameWorld, cam_x: int, cam_y: int) -> None:
        ts = TILE_SIZE

        # Castle axe (only present in castle levels)
        for axe in world.axe_rects:
            self._blit_sprite("axe_0", (axe.x - cam_x, axe.y - cam_y), size=(ts, ts))

        for goal in world.goal_rects:
            # goal_rect: x = entity.x * ts, y = (entity.y - 5) * ts
            # entity sits at tile row 13 (ground); dot is 12 rows above = tile row 1
            entity_wld_y = goal.y + 5 * ts
            dot_y = entity_wld_y - 12 * ts  # world-pixel y of the dot (tile row 1)
            pole_x = goal.x                  # world-pixel x (left-aligned to tile column)

            # Dot at pole top
            dot_surf = self._sprites.get("end0_dot", (ts // 3, ts // 3))
            self._screen.blit(dot_surf, (pole_x - cam_x, dot_y - cam_y))

            # 11 × end0_l segments (tile rows 2–12), left-aligned to match tile renderer
            seg_surf = self._sprites.get("end0_l", (7, ts))
            for i in range(11):
                self._screen.blit(seg_surf, (pole_x - cam_x, dot_y + ts * (i + 1) - cam_y))

            # Flag hangs just below the dot, slightly right of the pole
            self._screen.blit(
                self._sprites.get("end0_flag"),
                (pole_x + ts // 4 - cam_x, dot_y + ts // 2 - cam_y),
            )

    def _draw_player(self, world: GameWorld, cam_x: int, cam_y: int) -> None:
        if world.player.invincible_timer > 0 and int(world.player.invincible_timer * 20) % 2 == 0:
            return
        rect = world.player.rect
        frame = world.player_frame()
        size = self._fit_to_height(frame, rect.height)
        sprite = self._sprites.get(frame, size)
        if world.player.facing < 0:
            sprite = pygame.transform.flip(sprite, True, False)
        if world.player.star_timer > 0:
            tint = self._star_tint(world.player.star_timer)
            sprite = sprite.copy()
            sprite.fill(tint, special_flags=pygame.BLEND_RGB_ADD)
        self._screen.blit(sprite, (rect.centerx - size[0] // 2 - cam_x, rect.bottom - size[1] - cam_y))

    def _draw_popups(self, world: GameWorld, cam_x: int, cam_y: int) -> None:
        f = self._font
        for popup in world.popups:
            text = popup.text
            color = _POPUP_1UP if text == "1UP!" else _POPUP_YELLOW
            x = int(popup.pos.x) - cam_x - f.width(text, FS_SUB) // 2
            y = int(popup.pos.y) - cam_y
            f.draw_shadow(self._screen, text, x, y, FS_SUB, color)

    # ------------------------------------------------------------------
    # Sprite helpers
    # ------------------------------------------------------------------

    def _fit_to_height(self, sprite_name: str, height: int) -> tuple[int, int]:
        native = self._sprites.native_size(sprite_name)
        if not native or native[1] == 0:
            return (height, height)
        return (max(1, round(height * native[0] / native[1])), height)

    @staticmethod
    def _star_tint(star_timer: float) -> tuple[int, int, int]:
        phase = int(star_timer * 12) % 4
        return ((40, 0, 0), (0, 40, 0), (0, 0, 40), (30, 30, 0))[phase]

    def _blit_sprite(
        self,
        sprite_name: str,
        position: tuple[int, int],
        *,
        flip_x: bool = False,
        size: tuple[int, int] = (TILE_SIZE, TILE_SIZE),
    ) -> None:
        sprite = self._sprites.get(sprite_name, size)
        if flip_x:
            sprite = pygame.transform.flip(sprite, True, False)
        self._screen.blit(sprite, position)

    def _blit_actor(
        self,
        sprite_name: str,
        hitbox: pygame.Rect,
        cam_x: int,
        cam_y: int,
        *,
        flip_x: bool = False,
        flip_y: bool = False,
    ) -> None:
        native = self._sprites.native_size(sprite_name)
        if not native or native[0] == 0:
            size = (hitbox.width, hitbox.height)
        else:
            width = hitbox.width
            size = (width, max(1, round(width * native[1] / native[0])))
        sprite = self._sprites.get(sprite_name, size)
        if flip_x or flip_y:
            sprite = pygame.transform.flip(sprite, flip_x, flip_y)
        self._screen.blit(sprite, (hitbox.centerx - size[0] // 2 - cam_x, hitbox.bottom - size[1] - cam_y))
