from __future__ import annotations

from enum import Enum
from typing import Protocol

import pygame

from .enemy import ENEMY_FRAMES, create_enemy, is_enemy_spawn
from .entities import (
    BlockBump,
    Collectible,
    Enemy,
    EnemyProjectile,
    Fireball,
    Particle,
    Player,
    PowerState,
    ScorePopup,
    ShellState,
)
from .level import (
    BRICK_TYPES,
    ITEM_CONTENT_BY_ID,
    QUESTION_TYPES,
    LevelData,
    create_collectible,
    goal_rect,
    is_collectible_spawn,
    is_solid_tile,
    tile_rect,
)
from .physics import TileCollider
from .player import BIG_SIZE, SMALL_SIZE, create_player, player_size_for
from .theme import LevelTheme, theme_for
from .settings import (
    AIR_ACCELERATION,
    CAMERA_FOLLOW_SPEED,
    COYOTE_TIME,
    ENEMY_DESPAWN_MARGIN,
    FIREBALL_COOLDOWN,
    FIREBALL_GRAVITY,
    FIREBALL_LIFETIME,
    FIREBALL_SPEED,
    FIREBALL_VBOUNCE,
    GROUND_ACCELERATION,
    GROUND_FRICTION,
    GRAVITY,
    JUMP_BUFFER_TIME,
    JUMP_CUT_MULTIPLIER,
    JUMP_SPEED,
    LOW_TIME_THRESHOLD,
    MAX_FALL_SPEED,
    POWERUP_FREEZE,
    RESPAWN_DELAY,
    RUN_SPEED,
    SCREEN_SIZE,
    SHELL_KICK_SPEED,
    SHELL_WAKE_TIME,
    STARTING_LIVES,
    STOMP_COMBO_SCORES,
    SUPER_JUMP_BONUS,
    TILE_SIZE,
    INVINCIBILITY_TIME,
    MUSHROOM_SPEED,
    WALK_SPEED,
)


class KeyState(Protocol):
    def __getitem__(self, key: int) -> bool: ...


class WorldState(Enum):
    PLAYING = "playing"
    DYING = "dying"
    COMPLETE = "complete"
    TIMEOUT = "timeout"
    FLAGPOLE = "flagpole"
    LEVEL_END_WALK = "level_end_walk"
    GAMEOVER = "gameover"


class GameWorld:
    def __init__(self, level: LevelData) -> None:
        self.level = level
        self.theme: LevelTheme = theme_for(level.meta.name)
        self.camera_x = 0.0
        self.score = 0
        self.coins = 0
        self.lives = STARTING_LIVES
        self.state = WorldState.PLAYING
        self.respawn_timer = 0.0
        self.coyote_timer = 0.0
        self.jump_buffer_timer = 0.0
        self.events: list[str] = []
        self.player: Player
        self.fireballs: list[Fireball] = []
        self.enemy_projectiles: list[EnemyProjectile] = []
        self.bumps: list[BlockBump] = []
        self.popups: list[ScorePopup] = []
        self.particles: list[Particle] = []
        self.time_remaining: float = float(level.meta.time_limit)
        self._low_time_warned = False
        self.complete_timer = 0.0
        self.flagpole_timer = 0.0
        self.flagpole_target_y: float = 0.0
        self.gameover_timer = 0.0
        self.restart()

    @property
    def completed(self) -> bool:
        return self.state is WorldState.COMPLETE

    def pop_events(self) -> tuple[str, ...]:
        events = tuple(self.events)
        self.events.clear()
        return events

    def restart(self, reset_score: bool = False) -> None:
        if reset_score:
            self.score = 0
            self.coins = 0
            self.lives = STARTING_LIVES
        spawn = next((entity for entity in self.level.entities if entity.type == "PlayerSpawn"), None)
        spawn_x = (spawn.x if spawn else 3.0) * TILE_SIZE
        spawn_y = (spawn.y if spawn else 13.0) * TILE_SIZE
        self.player = create_player(spawn_x / TILE_SIZE, spawn_y / TILE_SIZE)
        self.background_tiles = tuple(tile_rect(tile) for tile in self.level.background)
        self.background_sprites = {
            (tile.x * TILE_SIZE, tile.y * TILE_SIZE): tile.sprite for tile in self.level.background
        }
        solid_tiles = [tile_rect(tile) for tile in self.level.foreground if is_solid_tile(tile)]
        self.solid_tiles: list[pygame.Rect] = solid_tiles
        self.collider = TileCollider(solid_tiles)
        self.tile_sprites: dict[tuple[int, int], str] = {
            (tile.x * TILE_SIZE, tile.y * TILE_SIZE): tile.sprite
            for tile in self.level.foreground
            if is_solid_tile(tile)
        }
        self.tile_types: dict[tuple[int, int], str] = {
            (tile.x * TILE_SIZE, tile.y * TILE_SIZE): tile.type
            for tile in self.level.foreground
            if is_solid_tile(tile)
        }
        # ?-block contents come from each tile's `item_content` index in the level
        # JSON (0=coin, 1=mushroom, 2=fire flower, 3=star, 4=1up). Blocks without an
        # explicit content default to a coin.
        self.block_contents: dict[tuple[int, int], str] = {}
        for tile in self.level.foreground:
            if tile.type in QUESTION_TYPES:
                key = (tile.x * TILE_SIZE, tile.y * TILE_SIZE)
                self.block_contents[key] = ITEM_CONTENT_BY_ID.get(tile.item_content, "Coin")
        self.enemies: list[Enemy] = [
            create_enemy(entity) for entity in self.level.entities if is_enemy_spawn(entity)
        ]
        self.collectibles: list[Collectible] = [
            create_collectible(entity)
            for entity in self.level.entities
            if is_collectible_spawn(entity)
        ]
        self.goal_rects = tuple(goal_rect(entity) for entity in self.level.entities if entity.type == "Goal")
        self.fireballs = []
        self.enemy_projectiles = []
        self.bumps = []
        self.popups = []
        self.particles = []
        self.state = WorldState.PLAYING
        self.respawn_timer = 0.0
        self.coyote_timer = COYOTE_TIME
        self.jump_buffer_timer = 0.0
        self.time_remaining = float(self.level.meta.time_limit)
        self._low_time_warned = False
        self.complete_timer = 0.0
        self.flagpole_timer = 0.0
        self.flagpole_target_y = 0.0
        self.gameover_timer = 0.0
        self.camera_x = max(0.0, self.player.pos.x - SCREEN_SIZE[0] * 0.38)

    def update(
        self,
        keys: KeyState,
        jump_pressed: bool,
        jump_held: bool,
        jump_released: bool,
        dt: float,
        fire_pressed: bool = False,
    ) -> None:
        if self.state is WorldState.DYING or self.state is WorldState.TIMEOUT:
            self.player.death_timer += dt
            if self.player.death_timer < 0.4:
                self.player.velocity.y = -480.0
            else:
                self.player.velocity.y = min(self.player.velocity.y + GRAVITY * dt, MAX_FALL_SPEED)
            self.player.pos.y += self.player.velocity.y * dt
            self.respawn_timer -= dt
            if self.respawn_timer <= 0:
                if self.lives <= 0:
                    self._enter_gameover()
                else:
                    self.restart()
            self._tick_effects(dt)
            self._update_camera(dt)
            return

        if self.state is WorldState.GAMEOVER:
            self.gameover_timer -= dt
            self._tick_effects(dt)
            return

        if self.state is WorldState.COMPLETE:
            self.complete_timer += dt
            self._tick_effects(dt)
            self._update_camera(dt)
            return

        if self.state is WorldState.FLAGPOLE:
            self._update_flagpole(dt)
            self._tick_effects(dt)
            self._update_camera(dt)
            return

        if self.state is WorldState.LEVEL_END_WALK:
            self._update_level_end_walk(dt)
            self._tick_effects(dt)
            self._update_camera(dt)
            return

        # PLAYING
        self.time_remaining = max(0.0, self.time_remaining - dt * 2.5)
        if self.time_remaining < LOW_TIME_THRESHOLD and not self._low_time_warned:
            self.events.append("lowtime")
            self._low_time_warned = True
        if self.time_remaining <= 0:
            self.state = WorldState.TIMEOUT
            self.respawn_timer = RESPAWN_DELAY
            self.lives -= 1
            self.player.death_timer = 0.0
            self.player.velocity.update(0.0, -480.0)
            self.events.append("death")
            return

        if self.player.powerup_freeze > 0:
            self.player.powerup_freeze = max(0.0, self.player.powerup_freeze - dt)
            if self.player.powerup_freeze == 0 and self.player.pending_state is not None:
                self._apply_state_change(self.player.pending_state)
                self.player.pending_state = None
            self._tick_effects(dt)
            self._update_camera(dt)
            return

        self._update_player(keys, jump_pressed, jump_held, jump_released, fire_pressed, dt)
        self._update_enemies(dt)
        self._update_fireballs(dt)
        self._update_enemy_projectiles(dt)
        self._update_collectibles(dt)
        self._handle_entity_collisions()
        self._handle_goal()
        self._tick_effects(dt)
        self._update_camera(dt)

    # --------------------------------------------------------------- rendering
    def player_frame(self) -> str:
        prefix = self._mario_prefix()
        if self.player.crouching and prefix != "mario":
            return f"{prefix}_squat"
        if not self.player.on_ground:
            return f"{prefix}_jump"
        if abs(self.player.velocity.x) < 1:
            return f"{prefix}_st"
        phase = int(pygame.time.get_ticks() / 100) % 3
        return f"{prefix}_move{phase}"

    def _mario_prefix(self) -> str:
        if self.player.state is PowerState.FIRE:
            return "mario2"
        if self.player.state is PowerState.SUPER:
            return "mario1"
        return "mario"

    # --------------------------------------------------------------- internals
    def _update_player(
        self,
        keys: KeyState,
        jump_pressed: bool,
        jump_held: bool,
        jump_released: bool,
        fire_pressed: bool,
        dt: float,
    ) -> None:
        if self.player.on_ground:
            self.coyote_timer = COYOTE_TIME
        else:
            self.coyote_timer = max(0.0, self.coyote_timer - dt)
        if jump_pressed:
            self.jump_buffer_timer = JUMP_BUFFER_TIME
        else:
            self.jump_buffer_timer = max(0.0, self.jump_buffer_timer - dt)

        max_speed = RUN_SPEED if keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT] else WALK_SPEED
        direction = (1 if keys[pygame.K_RIGHT] or keys[pygame.K_d] else 0) - (
            1 if keys[pygame.K_LEFT] or keys[pygame.K_a] else 0
        )

        # Crouch: only meaningful for Big/Fire Mario on the ground; locks horizontal motion.
        crouch_held = (keys[pygame.K_DOWN] or keys[pygame.K_s]) and self.player.on_ground
        crouch_eligible = self.player.state is not PowerState.SMALL
        if crouch_held and crouch_eligible:
            if not self.player.crouching:
                self.player.crouching = True
                # Shrink hitbox so Mario can fit through one-tile gaps.
                self.player.size.y = 38
                self.player.pos.y += 22
            direction = 0  # no horizontal movement while crouched
        elif self.player.crouching:
            # Stand up; restore Big hitbox.
            self.player.crouching = False
            self.player.size.y = 60
            self.player.pos.y -= 22

        if direction:
            self.player.facing = direction
            acceleration = GROUND_ACCELERATION if self.player.on_ground else AIR_ACCELERATION
            self.player.velocity.x = _approach(self.player.velocity.x, direction * max_speed, acceleration * dt)
        elif self.player.on_ground:
            self.player.velocity.x = _approach(self.player.velocity.x, 0.0, GROUND_FRICTION * dt)

        if self.jump_buffer_timer > 0 and self.coyote_timer > 0:
            base = JUMP_SPEED + (SUPER_JUMP_BONUS if self.player.state is not PowerState.SMALL else 0.0)
            # Speed-based bonus: full sprint adds ~10 % to jump height.
            speed_ratio = min(1.0, abs(self.player.velocity.x) / RUN_SPEED)
            jump_speed = base + speed_ratio * 80.0
            self.player.velocity.y = -jump_speed
            self.player.on_ground = False
            self.coyote_timer = 0.0
            self.jump_buffer_timer = 0.0
            self.events.append("jumpbig" if self.player.state is not PowerState.SMALL else "jump")

        if jump_released and not jump_held and self.player.velocity.y < 0:
            self.player.velocity.y *= JUMP_CUT_MULTIPLIER

        # Fireball
        if self.player.fire_cooldown > 0:
            self.player.fire_cooldown = max(0.0, self.player.fire_cooldown - dt)
        if fire_pressed and self.player.state is PowerState.FIRE and self.player.fire_cooldown <= 0 and len(self.fireballs) < 2:
            self._spawn_fireball()

        if self.player.invincible_timer > 0:
            self.player.invincible_timer = max(0.0, self.player.invincible_timer - dt)

        self.player.velocity.y = min(self.player.velocity.y + GRAVITY * dt, MAX_FALL_SPEED)
        head_hits = self.collider.move_and_collide(self.player, dt)
        if self.player.on_ground:
            self.coyote_timer = COYOTE_TIME

        for tile in head_hits:
            self._handle_block_hit(tile)

        if self.player.pos.y > self.level.meta.height * TILE_SIZE + 200:
            self._kill_player(force=True)

    def _spawn_fireball(self) -> None:
        direction = 1 if self.player.facing >= 0 else -1
        spawn_x = self.player.pos.x + (self.player.size.x if direction > 0 else -10)
        spawn_y = self.player.pos.y + self.player.size.y * 0.4
        self.fireballs.append(
            Fireball(
                pos=pygame.Vector2(spawn_x, spawn_y),
                velocity=pygame.Vector2(direction * FIREBALL_SPEED, 80.0),
            )
        )
        self.player.fire_cooldown = FIREBALL_COOLDOWN
        self.events.append("fireball")

    def _update_enemies(self, dt: float) -> None:
        for enemy in list(self.enemies):  # copy because AI may append
            if not enemy.alive:
                if enemy.death_timer > 0:
                    enemy.death_timer -= dt
                    enemy.body.pos.y += 240.0 * dt
                continue

            # Off-screen culling — only behind the camera (the player has passed).
            if enemy.body.pos.x + enemy.body.size.x < self.camera_x - ENEMY_DESPAWN_MARGIN:
                enemy.alive = False
                continue

            enemy.age += dt
            ai = enemy.ai_type
            if ai == "piranha":
                self._update_piranha(enemy, dt)
            elif ai == "bullet":
                self._update_bullet(enemy, dt)
            elif ai == "lakitu":
                self._update_lakitu(enemy, dt)
            elif ai == "hammerbro":
                self._update_hammerbro(enemy, dt)
            elif ai == "bowser":
                self._update_bowser(enemy, dt)
            else:
                self._update_walker(enemy, dt)

            if enemy.body.pos.y > self.level.meta.height * TILE_SIZE + 200:
                enemy.alive = False

        # Kicked-shell vs other-enemy collisions (cascading combo scoring).
        for shell in self.enemies:
            if not shell.alive or shell.shell_state is not ShellState.SHELL_KICKED:
                continue
            for other in self.enemies:
                if other is shell or not other.alive:
                    continue
                if other.shell_state is ShellState.SHELL_KICKED:
                    continue
                if not shell.body.rect.colliderect(other.body.rect):
                    continue
                other.alive = False
                other.death_timer = 0.45
                other.body.velocity.update(0.0, -260.0)
                shell.kick_streak += 1
                self._award_combo_points(shell.kick_streak, other.body.rect.x, other.body.rect.y)
                self.events.append("kick")

    def _update_walker(self, enemy: Enemy, dt: float) -> None:
        # Wake up sleeping shells.
        if enemy.shell_state is ShellState.SHELL_STILL:
            enemy.shell_wake_timer -= dt
            if enemy.shell_wake_timer <= 0:
                self._wake_shell(enemy)

        before_x = enemy.body.pos.x
        before_vx = enemy.body.velocity.x
        enemy.body.velocity.y = min(enemy.body.velocity.y + GRAVITY * dt, MAX_FALL_SPEED)
        self.collider.move_and_collide(enemy.body, dt)

        # Wall contact: bounce shells, turn around walkers.
        if abs(enemy.body.pos.x - before_x) < 0.01 and abs(before_vx) > 1.0:
            if enemy.shell_state is ShellState.SHELL_KICKED:
                enemy.body.velocity.x = -before_vx
                enemy.body.facing = -enemy.body.facing
                self.events.append("blockhit")
            else:
                enemy.body.velocity.x = -before_vx if before_vx else -enemy.body.facing * 70.0
                enemy.body.facing = -enemy.body.facing

        # Ledge-aware turn (only walking enemies that opt in).
        if (
            enemy.ledge_aware
            and enemy.shell_state is ShellState.WALKING
            and enemy.body.on_ground
            and enemy.body.velocity.x
        ):
            probe_x = (
                enemy.body.rect.right
                if enemy.body.velocity.x > 0
                else enemy.body.rect.left - 2
            )
            probe = pygame.Rect(int(probe_x), int(enemy.body.rect.bottom), 2, 4)
            if not any(probe.colliderect(tile) for tile in self.collider.nearby(probe)):
                enemy.body.velocity.x = -enemy.body.velocity.x
                enemy.body.facing = -enemy.body.facing

    def _update_piranha(self, enemy: Enemy, dt: float) -> None:
        # 4-second cycle: 1s rising, 1.2s emerged, 1s falling, 0.8s hidden.
        # Cycle pauses (or restarts at hidden phase) when Mario is too close.
        cycle_speed = 64.0  # px/s rise+fall speed
        rise_distance = TILE_SIZE * 2
        player_dx = abs(self.player.pos.x - enemy.home_x)
        retract_threshold = TILE_SIZE * 3
        enemy.ai_timer += dt
        # Phases: 0=hidden, 1=rising, 2=emerged, 3=falling
        if enemy.ai_phase == 0:
            if enemy.ai_timer > 1.4 and player_dx > retract_threshold:
                enemy.ai_phase = 1
                enemy.ai_timer = 0.0
        elif enemy.ai_phase == 1:
            enemy.body.pos.y -= cycle_speed * dt
            if enemy.home_y - enemy.body.pos.y >= rise_distance:
                enemy.body.pos.y = enemy.home_y - rise_distance
                enemy.ai_phase = 2
                enemy.ai_timer = 0.0
        elif enemy.ai_phase == 2:
            if enemy.ai_timer > 1.4:
                enemy.ai_phase = 3
                enemy.ai_timer = 0.0
        elif enemy.ai_phase == 3:
            enemy.body.pos.y += cycle_speed * dt
            if enemy.body.pos.y >= enemy.home_y:
                enemy.body.pos.y = enemy.home_y
                enemy.ai_phase = 0
                enemy.ai_timer = 0.0

    def _update_bullet(self, enemy: Enemy, dt: float) -> None:
        # Bullet Bills ignore tile collisions and gravity entirely.
        enemy.body.pos.x += enemy.body.velocity.x * dt
        # Despawn once they leave the visible area on either side.
        if (
            enemy.body.pos.x + enemy.body.size.x < self.camera_x - ENEMY_DESPAWN_MARGIN
            or enemy.body.pos.x > self.camera_x + SCREEN_SIZE[0] + ENEMY_DESPAWN_MARGIN
        ):
            enemy.alive = False

    def _update_lakitu(self, enemy: Enemy, dt: float) -> None:
        # Float at a fixed altitude, follow the camera at a slight lead.
        target_x = self.camera_x + SCREEN_SIZE[0] * 0.55
        diff = target_x - enemy.body.pos.x
        speed = max(-160.0, min(160.0, diff * 2.5))
        enemy.body.velocity.x = speed
        enemy.body.facing = -1 if self.player.pos.x < enemy.body.pos.x else 1
        enemy.body.pos.x += enemy.body.velocity.x * dt
        # Hover near the top of the play area.
        target_y = max(48.0, self.camera_x * 0 + 64.0)
        enemy.body.pos.y += (target_y - enemy.body.pos.y) * min(1.0, dt * 4)
        # Drop a Spiny periodically.
        enemy.ai_timer += dt
        if enemy.ai_timer > 4.5:
            enemy.ai_timer = 0.0
            self._spawn_spiny_drop(enemy)

    def _spawn_spiny_drop(self, lakitu: Enemy) -> None:
        from .level import EntitySpawn

        spiny = create_enemy(EntitySpawn(type="Spiny", x=lakitu.body.pos.x / TILE_SIZE, y=(lakitu.body.pos.y + 32) / TILE_SIZE))
        spiny.body.velocity.update(0.0, 80.0)
        self.enemies.append(spiny)

    def _update_hammerbro(self, enemy: Enemy, dt: float) -> None:
        # Reuses walker physics but limits horizontal range to ~3 tiles around home_x.
        self._update_walker(enemy, dt)
        if enemy.body.pos.x < enemy.home_x - TILE_SIZE * 2:
            enemy.body.velocity.x = abs(enemy.body.velocity.x or 50.0)
            enemy.body.facing = 1
        elif enemy.body.pos.x > enemy.home_x + TILE_SIZE * 2:
            enemy.body.velocity.x = -abs(enemy.body.velocity.x or 50.0)
            enemy.body.facing = -1
        # Periodic jump.
        enemy.ai_timer += dt
        if enemy.body.on_ground and enemy.ai_timer > 1.5:
            enemy.body.velocity.y = -560.0
            enemy.ai_timer = 0.0
        # Periodic hammer throw aimed roughly at the player.
        enemy.ai_phase += 1
        if enemy.ai_phase * dt > 1.2:
            enemy.ai_phase = 0
            if abs(self.player.pos.x - enemy.body.pos.x) < SCREEN_SIZE[0] * 0.7:
                self._throw_hammer(enemy)

    def _update_bowser(self, enemy: Enemy, dt: float) -> None:
        self._update_walker(enemy, dt)
        if enemy.body.pos.x < enemy.home_x - TILE_SIZE * 3:
            enemy.body.velocity.x = abs(enemy.body.velocity.x or 40.0)
            enemy.body.facing = 1
        elif enemy.body.pos.x > enemy.home_x + TILE_SIZE * 3:
            enemy.body.velocity.x = -abs(enemy.body.velocity.x or 40.0)
            enemy.body.facing = -1
        enemy.ai_timer += dt
        if enemy.body.on_ground and enemy.ai_timer > 2.5:
            enemy.body.velocity.y = -480.0
            enemy.ai_timer = 0.0
        # Bowser breathes fire roughly every 1.8s when player is in front of him.
        enemy.ai_phase += 1
        if enemy.ai_phase * dt > 1.8 and abs(self.player.pos.x - enemy.body.pos.x) < SCREEN_SIZE[0] * 0.9:
            enemy.ai_phase = 0
            self._spawn_bowser_fire(enemy)

    # ----------------------------------------------------------- enemy attacks
    def _throw_hammer(self, enemy: Enemy) -> None:
        direction = -1 if self.player.pos.x < enemy.body.pos.x else 1
        self.enemy_projectiles.append(
            EnemyProjectile(
                pos=pygame.Vector2(enemy.body.pos.x + (16 if direction > 0 else -8), enemy.body.pos.y - 16),
                velocity=pygame.Vector2(direction * 220.0, -460.0),
                kind="hammer",
                affected_by_gravity=True,
                lifetime=4.0,
            )
        )

    def _spawn_bowser_fire(self, enemy: Enemy) -> None:
        direction = -1 if self.player.pos.x < enemy.body.pos.x else 1
        self.enemy_projectiles.append(
            EnemyProjectile(
                pos=pygame.Vector2(
                    enemy.body.pos.x + (enemy.body.size.x if direction > 0 else -16),
                    enemy.body.pos.y + enemy.body.size.y * 0.4,
                ),
                velocity=pygame.Vector2(direction * 240.0, 0.0),
                kind="bowserfire",
                affected_by_gravity=False,
                lifetime=5.0,
            )
        )
        self.events.append("fire")

    def _update_enemy_projectiles(self, dt: float) -> None:
        kept: list[EnemyProjectile] = []
        for proj in self.enemy_projectiles:
            if not proj.alive:
                continue
            proj.age += dt
            if proj.affected_by_gravity:
                proj.velocity.y = min(proj.velocity.y + GRAVITY * dt, MAX_FALL_SPEED)
            proj.pos.x += proj.velocity.x * dt
            proj.pos.y += proj.velocity.y * dt
            # Tile collisions (hammers bounce off ground; fire breath dies on tile).
            for tile in self.collider.nearby(proj.rect):
                if proj.rect.colliderect(tile):
                    if proj.kind == "hammer" and proj.velocity.y > 0:
                        proj.pos.y = tile.top - proj.rect.height
                        proj.velocity.y = -260.0
                    elif proj.kind != "hammer":
                        proj.alive = False
                    break
            if proj.age > proj.lifetime:
                proj.alive = False
            elif (
                proj.pos.x < self.camera_x - ENEMY_DESPAWN_MARGIN
                or proj.pos.x > self.camera_x + SCREEN_SIZE[0] + ENEMY_DESPAWN_MARGIN
            ):
                proj.alive = False
            if proj.alive:
                kept.append(proj)
        self.enemy_projectiles = kept

        # Player-fireball vs enemy-projectile (Mario's fireball can clear hammers).
        for fb in self.fireballs:
            if not fb.alive:
                continue
            for proj in self.enemy_projectiles:
                if proj.alive and fb.rect.colliderect(proj.rect):
                    proj.alive = False
                    fb.alive = False
                    fb.explode_timer = 0.15
                    self.score += 50
                    break

        # Kicked-shell vs other-enemy collisions (combo scoring).
        for shell in self.enemies:
            if not shell.alive or shell.shell_state is not ShellState.SHELL_KICKED:
                continue
            for other in self.enemies:
                if other is shell or not other.alive:
                    continue
                if not shell.body.rect.colliderect(other.body.rect):
                    continue
                # Same-team kicked shells: no friendly fire when both kicked.
                if other.shell_state is ShellState.SHELL_KICKED:
                    continue
                other.alive = False
                other.death_timer = 0.45
                other.body.velocity.update(0.0, -260.0)
                shell.kick_streak += 1
                self._award_combo_points(shell.kick_streak, other.body.rect.x, other.body.rect.y)
                self.events.append("kick")

    def _update_fireballs(self, dt: float) -> None:
        kept: list[Fireball] = []
        for fireball in self.fireballs:
            if not fireball.alive:
                if fireball.explode_timer > 0:
                    fireball.explode_timer -= dt
                    if fireball.explode_timer > 0:
                        kept.append(fireball)
                continue
            fireball.age += dt
            fireball.velocity.y = min(fireball.velocity.y + FIREBALL_GRAVITY * dt, MAX_FALL_SPEED)
            fireball.pos.x += fireball.velocity.x * dt
            for tile in self.collider.nearby(fireball.rect):
                if fireball.rect.colliderect(tile):
                    fireball.alive = False
                    fireball.explode_timer = 0.15
                    break
            if not fireball.alive:
                kept.append(fireball)
                continue
            fireball.pos.y += fireball.velocity.y * dt
            for tile in self.collider.nearby(fireball.rect):
                if fireball.rect.colliderect(tile):
                    if fireball.velocity.y > 0:
                        fireball.pos.y = tile.top - fireball.rect.height
                        fireball.velocity.y = -FIREBALL_VBOUNCE
                    else:
                        fireball.pos.y = tile.bottom
                        fireball.velocity.y = abs(fireball.velocity.y) * 0.5
            if fireball.age > FIREBALL_LIFETIME:
                fireball.alive = False
                fireball.explode_timer = 0.1
            elif fireball.pos.x < self.camera_x - 80 or fireball.pos.x > self.camera_x + SCREEN_SIZE[0] + 80:
                fireball.alive = False
                fireball.explode_timer = 0.0
            else:
                kept.append(fireball)
        self.fireballs = kept

    def _update_collectibles(self, dt: float) -> None:
        for collectible in self.collectibles:
            if collectible.emerge_remaining > 0:
                collectible.emerge_remaining -= dt
                collectible.rect.y -= int(round(MUSHROOM_SPEED * dt))
                if collectible.emerge_remaining <= 0:
                    collectible.emerge_remaining = 0.0
                    collectible.velocity.x = MUSHROOM_SPEED
                continue
            if collectible.kind in {"Mushroom", "OneUp", "Star"}:
                collectible.velocity.y = min(collectible.velocity.y + GRAVITY * dt, MAX_FALL_SPEED)
                collectible.rect.x += int(round(collectible.velocity.x * dt))
                # Horizontal collision: flip on wall
                for tile in self.collider.nearby(collectible.rect):
                    if collectible.rect.colliderect(tile):
                        if collectible.velocity.x > 0:
                            collectible.rect.right = tile.left
                        elif collectible.velocity.x < 0:
                            collectible.rect.left = tile.right
                        collectible.velocity.x *= -1
                collectible.rect.y += int(round(collectible.velocity.y * dt))
                collectible.on_ground = False
                for tile in self.collider.nearby(collectible.rect):
                    if collectible.rect.colliderect(tile):
                        if collectible.velocity.y > 0:
                            collectible.rect.bottom = tile.top
                            if collectible.kind == "Star":
                                # Stars bounce; mushrooms come to rest.
                                collectible.velocity.y = -540.0
                            else:
                                collectible.velocity.y = 0
                            collectible.on_ground = True
                        elif collectible.velocity.y < 0:
                            collectible.rect.top = tile.bottom
                            collectible.velocity.y = 0

    def _handle_block_hit(self, tile_rect_: pygame.Rect) -> None:
        key = (tile_rect_.x, tile_rect_.y)
        tile_type = self.tile_types.get(key)
        if tile_type is None:
            return
        if tile_type in QUESTION_TYPES:
            content = self.block_contents.get(key, "Coin")
            # SMB convention: a mushroom upgrades to a fire flower if Mario is already big.
            if content == "Mushroom" and self.player.state is not PowerState.SMALL:
                content = "FireFlower"
            self._convert_to_used(tile_rect_)
            self.bumps.append(BlockBump(rect=pygame.Rect(tile_rect_), sprite="blockq_used"))
            if content == "Coin":
                self.coins += 1
                self.score += 200
                self.events.append("coin")
                self._spawn_block_coin(tile_rect_)
                self._popup("200", tile_rect_.x, tile_rect_.y)
                self._maybe_oneup()
            elif content == "OneUp":
                self._spawn_block_powerup(tile_rect_, "OneUp")
                self.events.append("mushroomappear")
            elif content == "Star":
                self._spawn_block_powerup(tile_rect_, "Star")
                self.events.append("mushroomappear")
            else:
                # Mushroom or FireFlower
                self._spawn_block_powerup(tile_rect_, content)
                self.events.append("mushroomappear")
        elif tile_type in BRICK_TYPES:
            if self.player.state is PowerState.SMALL:
                self.bumps.append(BlockBump(rect=pygame.Rect(tile_rect_), sprite=self.tile_sprites.get(key, "brick1")))
                self.events.append("blockhit")
            else:
                sprite = self.tile_sprites.get(key, "brick1")
                self._remove_tile(tile_rect_)
                self._spawn_brick_particles(tile_rect_, sprite)
                self.score += 50
                self.events.append("blockbreak")

    def _convert_to_used(self, tile_rect_: pygame.Rect) -> None:
        key = (tile_rect_.x, tile_rect_.y)
        self.tile_types[key] = "UsedBlock"
        self.tile_sprites[key] = "blockq_used"
        self.block_contents.pop(key, None)

    def _remove_tile(self, tile_rect_: pygame.Rect) -> None:
        key = (tile_rect_.x, tile_rect_.y)
        self.tile_sprites.pop(key, None)
        self.tile_types.pop(key, None)
        self.collider.remove(tile_rect_)
        self.solid_tiles[:] = [tile for tile in self.solid_tiles if tile.topleft != tile_rect_.topleft]

    def _spawn_block_coin(self, tile_rect_: pygame.Rect) -> None:
        # Visual feedback only - the score/coin are already counted.
        self.particles.append(
            Particle(
                pos=pygame.Vector2(tile_rect_.x + 4, tile_rect_.y - TILE_SIZE),
                velocity=pygame.Vector2(0, -380.0),
                sprite="coin_an0",
                timer=0.45,
            )
        )

    def _spawn_block_powerup(self, tile_rect_: pygame.Rect, kind: str) -> None:
        sprite_by_kind = {
            "Mushroom": "mushroom",
            "OneUp": "mushroom_1up",
            "FireFlower": "flower0",
            "Star": "star_0",
        }
        sprite = sprite_by_kind.get(kind, "mushroom")
        # Mushrooms (and 1-ups, stars) drift sideways, fire flowers stay put.
        if kind in {"Mushroom", "OneUp"}:
            velocity = pygame.Vector2(MUSHROOM_SPEED, 0.0)
        elif kind == "Star":
            # Stars launch with an upward bounce and full horizontal drift.
            velocity = pygame.Vector2(MUSHROOM_SPEED, -480.0)
        else:
            velocity = pygame.Vector2(0.0, 0.0)
        self.collectibles.append(
            Collectible(
                kind=kind,
                rect=pygame.Rect(tile_rect_.x + 2, tile_rect_.y, TILE_SIZE, TILE_SIZE),
                sprite=sprite,
                velocity=velocity,
                emerge_remaining=0.6,
            )
        )

    def _spawn_brick_particles(self, tile_rect_: pygame.Rect, sprite: str) -> None:
        for direction_x, vy in ((-1, -480.0), (1, -480.0), (-1, -260.0), (1, -260.0)):
            self.particles.append(
                Particle(
                    pos=pygame.Vector2(tile_rect_.x + 8, tile_rect_.y),
                    velocity=pygame.Vector2(direction_x * 160.0, vy),
                    sprite=sprite,
                    timer=0.7,
                )
            )

    def _handle_entity_collisions(self) -> None:
        player_rect = self.player.rect

        for enemy in self.enemies:
            if not enemy.alive or not player_rect.colliderect(enemy.body.rect):
                continue
            from_above = (
                self.player.velocity.y > 0
                and player_rect.bottom <= enemy.body.rect.centery + 8
            )

            # Star power: Mario kills anything he touches.
            if self.player.star_timer > 0:
                self._kill_enemy(enemy, score=200, popup_x=enemy.body.rect.x, popup_y=enemy.body.rect.y)
                self.events.append("kick")
                continue

            # Shell-state collisions take priority over walker collisions.
            if enemy.shell_state is ShellState.SHELL_STILL:
                if from_above:
                    self.player.velocity.y = -JUMP_SPEED * 0.45
                    self._kick_shell(enemy, direction=1 if self.player.facing >= 0 else -1)
                else:
                    self._kick_shell(
                        enemy,
                        direction=1 if self.player.pos.x < enemy.body.pos.x else -1,
                    )
                continue
            if enemy.shell_state is ShellState.SHELL_KICKED:
                if from_above:
                    self.player.velocity.y = -JUMP_SPEED * 0.45
                    enemy.shell_state = ShellState.SHELL_STILL
                    enemy.shell_wake_timer = SHELL_WAKE_TIME
                    enemy.body.velocity.update(0.0, 0.0)
                    enemy.kick_streak = 0
                elif self.player.invincible_timer <= 0:
                    self._take_damage()
                    return
                continue

            # Plain walker.
            if from_above and enemy.stompable:
                self.player.velocity.y = -JUMP_SPEED * 0.45
                if enemy.gives_shell:
                    self._convert_to_shell(enemy)
                    self.score += 100
                    self._popup("100", enemy.body.rect.x, enemy.body.rect.y)
                else:
                    self._kill_enemy(enemy, score=100, popup_x=enemy.body.rect.x, popup_y=enemy.body.rect.y)
                self.events.append("stomp")
            elif self.player.invincible_timer > 0:
                continue
            else:
                self._take_damage()
                return

        # Fireball vs enemies (skip fire-immune enemies).
        for fireball in self.fireballs:
            if not fireball.alive:
                continue
            for enemy in self.enemies:
                if not enemy.alive or not fireball.rect.colliderect(enemy.body.rect):
                    continue
                if enemy.fire_immune:
                    fireball.alive = False
                    fireball.explode_timer = 0.15
                    break
                self._kill_enemy(enemy, score=200, popup_x=enemy.body.rect.x, popup_y=enemy.body.rect.y)
                enemy.body.velocity.y = -300.0
                fireball.alive = False
                fireball.explode_timer = 0.15
                self.events.append("kick")
                break

        # Enemy projectiles (hammers, bowser fire) damage the player on contact.
        for proj in self.enemy_projectiles:
            if proj.alive and player_rect.colliderect(proj.rect):
                if self.player.star_timer > 0 or self.player.invincible_timer > 0:
                    proj.alive = False
                    continue
                proj.alive = False
                self._take_damage()
                return

        kept_collectibles: list[Collectible] = []
        for collectible in self.collectibles:
            if collectible.emerge_remaining <= 0 and player_rect.colliderect(collectible.rect):
                self._collect(collectible)
            else:
                kept_collectibles.append(collectible)
        self.collectibles = kept_collectibles

    def _collect(self, collectible: Collectible) -> None:
        if collectible.kind == "Coin":
            self.coins += 1
            self.score += 200
            self.events.append("coin")
            self._popup("200", collectible.rect.x, collectible.rect.y)
            self._maybe_oneup()
        elif collectible.kind == "Mushroom":
            self.score += 1000
            self._popup("1000", collectible.rect.x, collectible.rect.y)
            if self.player.state is PowerState.SMALL:
                self._begin_powerup(PowerState.SUPER)
            else:
                pass
            self.events.append("powerup")
        elif collectible.kind in {"FireFlower", "Flower"}:
            self.score += 1000
            self._popup("1000", collectible.rect.x, collectible.rect.y)
            self._begin_powerup(PowerState.FIRE)
            self.events.append("powerup")
        elif collectible.kind == "Star":
            self.score += 1000
            self._popup("1000", collectible.rect.x, collectible.rect.y)
            self.player.star_timer = 9.0
            self.events.append("rainboom")
        elif collectible.kind == "OneUp":
            self.lives += 1
            self.events.append("oneup")
            self._popup("1UP", collectible.rect.x, collectible.rect.y)

    def _maybe_oneup(self) -> None:
        if self.coins >= 100:
            self.coins -= 100
            self.lives += 1
            self.events.append("oneup")

    def _begin_powerup(self, state: PowerState) -> None:
        self.player.powerup_freeze = POWERUP_FREEZE
        self.player.pending_state = state

    def _apply_state_change(self, state: PowerState) -> None:
        was_small = self.player.state is PowerState.SMALL
        self.player.state = state
        new_size = player_size_for(state)
        if was_small and state is not PowerState.SMALL:
            self.player.pos.y -= (new_size.y - self.player.size.y)
        self.player.size = pygame.Vector2(new_size)

    def _take_damage(self) -> None:
        if self.player.state is PowerState.SMALL:
            self._kill_player()
            return
        # Demote to SMALL with brief invincibility
        self._apply_state_change(PowerState.SMALL)
        self.player.invincible_timer = INVINCIBILITY_TIME
        self.events.append("shrink")

    def _handle_goal(self) -> None:
        player_rect = self.player.rect
        world_end = self.level.meta.width * TILE_SIZE - TILE_SIZE * 2

        if any(player_rect.colliderect(goal) for goal in self.goal_rects):
            # Touched the flagpole — score by grab height (top of pole = best).
            goal = next(goal for goal in self.goal_rects if player_rect.colliderect(goal))
            self._begin_flagpole_slide(goal)
            return

        if player_rect.x >= world_end:
            # No flagpole found, but Mario walked off the right edge: count as complete.
            self.state = WorldState.COMPLETE
            self.score += 1000 + int(self.time_remaining) * 50
            self.events.append("complete")

    def _begin_flagpole_slide(self, goal: pygame.Rect) -> None:
        # Convert vertical position on the pole to a score tier.
        # Top  of pole grants 5000, bottom grants 100.
        top = goal.top
        bottom = goal.top + goal.height
        relative = (self.player.pos.y - top) / max(1.0, (bottom - top))
        relative = max(0.0, min(1.0, relative))
        tiers = (5000, 2000, 800, 400, 100)
        idx = min(int(relative * len(tiers)), len(tiers) - 1)
        self.score += tiers[idx]
        self._popup(str(tiers[idx]), int(self.player.pos.x), int(self.player.pos.y))
        self.player.velocity.update(0.0, 0.0)
        # Snap Mario to the side of the pole.
        self.player.pos.x = goal.x - 4
        self.flagpole_target_y = float(goal.bottom - self.player.size.y - 4)
        self.flagpole_timer = 0.0
        self.state = WorldState.FLAGPOLE
        self.events.append("complete")

    def _update_flagpole(self, dt: float) -> None:
        # Slide Mario down the pole until he reaches the flagpole_target_y.
        slide_speed = 240.0
        self.flagpole_timer += dt
        if self.player.pos.y < self.flagpole_target_y:
            self.player.pos.y = min(self.flagpole_target_y, self.player.pos.y + slide_speed * dt)
            return
        # After landing, pause briefly then start the level-end walk.
        if self.flagpole_timer < 1.0:
            return
        # Flip Mario to the right and start walking toward the castle.
        self.player.facing = 1
        self.player.velocity.update(120.0, 0.0)
        self.complete_timer = 0.0
        self.state = WorldState.LEVEL_END_WALK

    def _update_level_end_walk(self, dt: float) -> None:
        # Mario walks ~3 seconds at a fixed pace, then the level completes.
        self.complete_timer += dt
        self.player.pos.x += 120.0 * dt
        # Drop a small time bonus tally per second.
        if self.time_remaining > 0:
            consumed = min(self.time_remaining, dt * 30.0)
            self.time_remaining -= consumed
            self.score += int(consumed * 50)
        if self.complete_timer >= 3.0:
            self.score += 1000  # base completion bonus
            self.state = WorldState.COMPLETE
            self.complete_timer = 0.0

    def _enter_gameover(self) -> None:
        self.state = WorldState.GAMEOVER
        self.gameover_timer = 3.0
        self.events.append("gameover")

    def _tick_effects(self, dt: float) -> None:
        for bump in self.bumps:
            bump.timer -= dt
        self.bumps = [bump for bump in self.bumps if bump.timer > 0]
        for popup in self.popups:
            popup.timer -= dt
            popup.pos.y -= 30.0 * dt
        self.popups = [popup for popup in self.popups if popup.timer > 0]
        for particle in self.particles:
            particle.timer -= dt
            particle.velocity.y = min(particle.velocity.y + GRAVITY * dt, MAX_FALL_SPEED)
            particle.pos.x += particle.velocity.x * dt
            particle.pos.y += particle.velocity.y * dt
        self.particles = [particle for particle in self.particles if particle.timer > 0]
        if self.player.star_timer > 0:
            self.player.star_timer = max(0.0, self.player.star_timer - dt)

    def _popup(self, text: str, x: int, y: int) -> None:
        self.popups.append(ScorePopup(text=text, pos=pygame.Vector2(x, y)))

    def _update_camera(self, dt: float) -> None:
        target = self.player.pos.x - SCREEN_SIZE[0] * 0.38
        max_camera = max(0, self.level.meta.width * TILE_SIZE - SCREEN_SIZE[0])
        clamped_target = max(self.camera_x, min(target, float(max_camera)))
        if abs(self.camera_x - clamped_target) < 0.5:
            self.camera_x = clamped_target
        else:
            self.camera_x += (clamped_target - self.camera_x) * min(1.0, CAMERA_FOLLOW_SPEED * dt)

    def _kill_enemy(self, enemy: Enemy, score: int, popup_x: int, popup_y: int) -> None:
        enemy.alive = False
        enemy.death_timer = 0.5
        enemy.body.velocity.y = -260.0
        if score:
            self.score += score
            self._popup(str(score), popup_x, popup_y)

    def _convert_to_shell(self, enemy: Enemy) -> None:
        enemy.shell_state = ShellState.SHELL_STILL
        enemy.shell_wake_timer = SHELL_WAKE_TIME
        enemy.kick_streak = 0
        # Squish the hitbox so the player can stand next to a shell, not on it.
        if enemy.body.size.y > 22:
            shrink = enemy.body.size.y - 22
            enemy.body.pos.y += shrink
            enemy.body.size.y = 22
        enemy.body.velocity.update(0.0, 0.0)
        enemy.frames = enemy.shell_frames

    def _wake_shell(self, enemy: Enemy) -> None:
        enemy.shell_state = ShellState.WALKING
        # Restore body height (assumes original walker was 28 tall).
        if enemy.body.size.y < 28:
            grow = 28 - enemy.body.size.y
            enemy.body.pos.y -= grow
            enemy.body.size.y = 28
        enemy.body.velocity.x = -70.0 if enemy.body.facing < 0 else 70.0
        enemy.frames = ENEMY_FRAMES.get(enemy.kind, enemy.frames)

    def _kick_shell(self, enemy: Enemy, direction: int) -> None:
        enemy.shell_state = ShellState.SHELL_KICKED
        enemy.body.velocity.x = SHELL_KICK_SPEED * direction
        enemy.body.facing = direction
        enemy.kick_streak = 0
        self.score += 400
        self._popup("400", enemy.body.rect.x, enemy.body.rect.y)
        self.events.append("kick")

    def _award_combo_points(self, streak: int, popup_x: int, popup_y: int) -> None:
        # streak counts the hits this kicked-shell has chained, starting at 1.
        if streak >= len(STOMP_COMBO_SCORES):
            self.lives += 1
            self._popup("1UP", popup_x, popup_y)
            self.events.append("oneup")
            return
        bonus = STOMP_COMBO_SCORES[streak - 1] if streak >= 1 else STOMP_COMBO_SCORES[0]
        self.score += bonus
        self._popup(str(bonus), popup_x, popup_y)

    def _kill_player(self, force: bool = False) -> None:
        if self.state is not WorldState.PLAYING and not force:
            return
        self.lives -= 1
        self.state = WorldState.DYING
        self.respawn_timer = RESPAWN_DELAY
        self.player.death_timer = 0.0
        self.player.velocity.update(0.0, -480.0)
        self.events.append("death")


def _approach(current: float, target: float, amount: float) -> float:
    if current < target:
        return min(current + amount, target)
    if current > target:
        return max(current - amount, target)
    return target
