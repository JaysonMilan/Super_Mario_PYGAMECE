from __future__ import annotations

from pathlib import Path

import pygame

from .atlas import SpriteBank
from .entities import PowerState
from .player import BIG_SIZE, SMALL_SIZE
from .settings import SCREEN_SIZE, SKY_COLOR, TILE_SIZE
from .world import GameWorld, WorldState


class Renderer:
    def __init__(self, screen: pygame.Surface, sprites: SpriteBank, font: pygame.Font) -> None:
        self._screen = screen
        self._sprites = sprites
        self._font = font
        self._small_font = pygame.font.Font(None, 20)

    def draw(self, world: GameWorld, overlay: str | None = None) -> None:
        self._screen.fill(world.theme.sky)
        camera = round(world.camera_x)
        visible = pygame.Rect(
            camera - TILE_SIZE,
            -TILE_SIZE * 2,
            SCREEN_SIZE[0] + TILE_SIZE * 2,
            SCREEN_SIZE[1] + TILE_SIZE * 4,
        )

        self._draw_background(world, camera, visible)
        self._draw_tiles(world, camera, visible)
        self._draw_bumps(world, camera, visible)
        self._draw_collectibles(world, camera, visible)
        self._draw_enemies(world, camera, visible)
        self._draw_fireballs(world, camera, visible)
        self._draw_enemy_projectiles(world, camera, visible)
        self._draw_particles(world, camera, visible)
        self._draw_goals(world, camera)
        self._draw_player(world, camera)
        self._draw_popups(world, camera)
        self._draw_hud(world)
        if overlay is not None:
            self._draw_center_overlay(overlay, "ENTER/P RESUME   R RESTART   ESC LEVELS")

        pygame.display.flip()

    def draw_title(self, levels: tuple[Path, ...], selected_index: int) -> None:
        self._screen.fill((40, 40, 60))
        title = self._font.render("SUPER MARIO PYGAMECE", True, (255, 255, 255))
        self._screen.blit(title, title.get_rect(center=(SCREEN_SIZE[0] // 2, 56)))

        subtitle = self._small_font.render(
            "UP/DOWN SELECT  -  ENTER START  -  ESC QUIT",
            True,
            (210, 210, 210),
        )
        self._screen.blit(subtitle, subtitle.get_rect(center=(SCREEN_SIZE[0] // 2, 92)))

        controls = self._small_font.render(
            "Move: A/D or Arrows   Jump: SPACE/Z   Run: SHIFT   Fire: X   Restart: R   Pause: P",
            True,
            (200, 200, 200),
        )
        self._screen.blit(controls, controls.get_rect(center=(SCREEN_SIZE[0] // 2, 116)))

        if not levels:
            message = self._font.render(
                "NO LEVEL JSON FOUND - FALLBACK LEVEL WILL RUN", True, (255, 255, 255)
            )
            self._screen.blit(message, message.get_rect(center=(SCREEN_SIZE[0] // 2, 200)))
            pygame.display.flip()
            return

        rows = 11
        center = rows // 2
        start = max(0, selected_index - center)
        end = min(len(levels), start + rows)
        start = max(0, end - rows)
        y = 165
        for index, path in enumerate(levels[start:end], start=start):
            marker = ">" if index == selected_index else " "
            label = f"{marker} {path.stem}"
            color = (255, 230, 100) if index == selected_index else (220, 220, 220)
            line = self._font.render(label, True, color)
            self._screen.blit(line, (SCREEN_SIZE[0] // 2 - 140, y))
            y += 26

        footer = self._small_font.render(
            f"{len(levels)} levels available", True, (180, 180, 180)
        )
        self._screen.blit(footer, footer.get_rect(center=(SCREEN_SIZE[0] // 2, SCREEN_SIZE[1] - 30)))
        pygame.display.flip()

    def _draw_tiles(self, world: GameWorld, camera: int, visible: pygame.Rect) -> None:
        for tile_rect in world.solid_tiles:
            if visible.colliderect(tile_rect):
                key = (tile_rect.x, tile_rect.y)
                sprite_name = world.tile_sprites.get(key, "gnd_red_1")
                self._screen.blit(self._sprites.get(sprite_name), (tile_rect.x - camera, tile_rect.y))

    def _draw_background(self, world: GameWorld, camera: int, visible: pygame.Rect) -> None:
        for tile_rect in world.background_tiles:
            if visible.colliderect(tile_rect):
                sprite_name = world.background_sprites[tile_rect.topleft]
                self._screen.blit(self._sprites.get(sprite_name), (tile_rect.x - camera, tile_rect.y))

    def _draw_bumps(self, world: GameWorld, camera: int, visible: pygame.Rect) -> None:
        for bump in world.bumps:
            if not visible.colliderect(bump.rect):
                continue
            offset = int(round(-12 * (bump.timer / 0.18) * (1 - bump.timer / 0.18) * 4))
            self._screen.blit(
                self._sprites.get(bump.sprite),
                (bump.rect.x - camera, bump.rect.y + offset),
            )

    def _draw_collectibles(self, world: GameWorld, camera: int, visible: pygame.Rect) -> None:
        for collectible in world.collectibles:
            if not visible.colliderect(collectible.rect):
                continue
            sprite = collectible.sprite
            if collectible.kind == "Coin":
                phase = int(pygame.time.get_ticks() / 120) % 3
                sprite = ("coin_0", "coin_1", "coin_2")[phase]
            elif collectible.kind in {"FireFlower", "Flower"}:
                phase = int(pygame.time.get_ticks() / 120) % 4
                sprite = f"flower{phase}"
            elif collectible.kind == "Star":
                phase = int(pygame.time.get_ticks() / 80) % 4
                sprite = f"star_{phase}"
            self._screen.blit(
                self._sprites.get(sprite),
                (collectible.rect.x - camera, collectible.rect.y),
            )

    def _draw_enemies(self, world: GameWorld, camera: int, visible: pygame.Rect) -> None:
        for enemy in world.enemies:
            if not visible.colliderect(enemy.body.rect):
                continue
            if not enemy.alive and enemy.death_timer <= 0:
                continue
            frames = enemy.frames
            speed = 8.0
            if enemy.shell_state.value == "shell_kicked":
                speed = 18.0
            frame = frames[int(enemy.age * speed) % len(frames)]
            self._blit_sprite(
                frame,
                (enemy.body.rect.x - camera, enemy.body.rect.y),
                flip_x=enemy.body.facing < 0,
                size=(int(enemy.body.size.x), int(enemy.body.size.y)),
            )

    def _draw_fireballs(self, world: GameWorld, camera: int, visible: pygame.Rect) -> None:
        for fireball in world.fireballs:
            rect = fireball.rect
            if not visible.colliderect(rect):
                continue
            if fireball.alive:
                phase = int(fireball.age * 16) % 4
                sprite = f"fireball_{phase}"
                self._blit_sprite(sprite, (rect.x - camera, rect.y), size=(14, 14))
            else:
                phase = int((0.15 - fireball.explode_timer) * 30) % 2
                sprite = f"fire_{phase}"
                self._blit_sprite(sprite, (rect.x - camera - 6, rect.y - 6), size=(24, 24))

    def _draw_enemy_projectiles(self, world: GameWorld, camera: int, visible: pygame.Rect) -> None:
        for proj in world.enemy_projectiles:
            if not proj.alive or not visible.colliderect(proj.rect):
                continue
            if proj.kind == "hammer":
                phase = int(proj.age * 18) % 4
                self._blit_sprite(
                    f"hammer_{phase}",
                    (proj.rect.x - camera, proj.rect.y),
                    size=(20, 20),
                )
            elif proj.kind == "bowserfire":
                phase = int(proj.age * 12) % 2
                self._blit_sprite(
                    f"fire_{phase}",
                    (proj.rect.x - camera, proj.rect.y),
                    flip_x=proj.velocity.x < 0,
                    size=(24, 16),
                )
            else:
                phase = int(proj.age * 12) % 2
                self._blit_sprite(
                    f"fire_{phase}",
                    (proj.rect.x - camera, proj.rect.y),
                    size=(20, 16),
                )

    def _draw_particles(self, world: GameWorld, camera: int, visible: pygame.Rect) -> None:
        for particle in world.particles:
            x = int(particle.pos.x) - camera
            y = int(particle.pos.y)
            self._blit_sprite(particle.sprite, (x, y), size=(16, 16))

    def _draw_goals(self, world: GameWorld, camera: int) -> None:
        for goal in world.goal_rects:
            pygame.draw.rect(self._screen, (240, 240, 240), (goal.x - camera + 14, goal.y - 160, 4, 160))
            self._screen.blit(self._sprites.get("end0_flag"), (goal.x - camera - 8, goal.y - 150))

    def _draw_player(self, world: GameWorld, camera: int) -> None:
        size = (int(world.player.size.x), int(world.player.size.y))
        if world.player.invincible_timer > 0 and int(world.player.invincible_timer * 20) % 2 == 0:
            return
        sprite = self._sprites.get(world.player_frame(), size)
        if world.player.facing < 0:
            sprite = pygame.transform.flip(sprite, True, False)
        if world.player.star_timer > 0:
            tint = self._star_tint(world.player.star_timer)
            sprite = sprite.copy()
            sprite.fill(tint, special_flags=pygame.BLEND_RGB_ADD)
        self._screen.blit(sprite, (world.player.rect.x - camera, world.player.rect.y))

    @staticmethod
    def _star_tint(star_timer: float) -> tuple[int, int, int]:
        # Cycle warm/cool overlays at ~12 Hz for the rainbow flash effect.
        phase = int(star_timer * 12) % 4
        return ((40, 0, 0), (0, 40, 0), (0, 0, 40), (30, 30, 0))[phase]

    def _draw_popups(self, world: GameWorld, camera: int) -> None:
        for popup in world.popups:
            text = self._small_font.render(popup.text, True, (255, 255, 255))
            self._screen.blit(text, (int(popup.pos.x) - camera, int(popup.pos.y)))

    def _draw_hud(self, world: GameWorld) -> None:
        line1 = (
            f"MARIO  {world.score:06d}     COINS x{world.coins:02d}     "
            f"WORLD  {world.level.meta.name:<10}     TIME  {int(world.time_remaining):03d}"
        )
        line2 = f"LIVES x{world.lives}     R RESTART     TAB LEVEL SELECT     ESC QUIT"
        self._screen.blit(self._font.render(line1, True, (255, 255, 255)), (16, 12))
        self._screen.blit(self._small_font.render(line2, True, (210, 210, 210)), (16, 38))

        if world.state is WorldState.DYING or world.state is WorldState.TIMEOUT:
            text = self._font.render(
                "TIME UP" if world.state is WorldState.TIMEOUT else "TRY AGAIN",
                True,
                (255, 255, 255),
            )
            self._screen.blit(text, text.get_rect(center=(SCREEN_SIZE[0] // 2, 90)))
        elif world.state is WorldState.GAMEOVER:
            veil = pygame.Surface(SCREEN_SIZE, pygame.SRCALPHA)
            veil.fill((0, 0, 0, 220))
            self._screen.blit(veil, (0, 0))
            text = self._font.render("GAME OVER", True, (255, 255, 255))
            self._screen.blit(text, text.get_rect(center=(SCREEN_SIZE[0] // 2, SCREEN_SIZE[1] // 2)))
        elif world.completed:
            text = self._font.render(
                "LEVEL COMPLETE - PRESS R TO RESTART, TAB FOR LEVELS",
                True,
                (255, 255, 255),
            )
            self._screen.blit(text, text.get_rect(center=(SCREEN_SIZE[0] // 2, 90)))

        if world.player.powerup_freeze > 0:
            text = self._small_font.render("POWER UP", True, (255, 240, 80))
            self._screen.blit(text, text.get_rect(center=(SCREEN_SIZE[0] // 2, 110)))

    def _draw_center_overlay(self, title: str, subtitle: str) -> None:
        veil = pygame.Surface(SCREEN_SIZE, pygame.SRCALPHA)
        veil.fill((0, 0, 0, 120))
        self._screen.blit(veil, (0, 0))
        title_surface = self._font.render(title, True, (255, 255, 255))
        subtitle_surface = self._small_font.render(subtitle, True, (220, 220, 220))
        self._screen.blit(title_surface, title_surface.get_rect(center=(SCREEN_SIZE[0] // 2, 210)))
        self._screen.blit(subtitle_surface, subtitle_surface.get_rect(center=(SCREEN_SIZE[0] // 2, 246)))

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
