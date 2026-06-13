from __future__ import annotations

import math
import random
from enum import Enum
from typing import Protocol

import pygame

from .enemy import ENEMY_DEAD_FRAMES, ENEMY_FRAMES, create_enemy, is_enemy_spawn
from .entities import (
    BlockBump,
    CheepSpawner,
    Collectible,
    Enemy,
    EnemyProjectile,
    FallingPlatform,
    FireBar,
    Fireball,
    MovingPlatform,
    Particle,
    PipeState,
    Player,
    PlayerSession,
    PowerState,
    ScorePopup,
    SeesawPlatform,
    ShellState,
    UpFire,
)
from .level import (
    BRICK_TYPES,
    ITEM_CONTENT_BY_ID,
    QUESTION_TYPES,
    EntitySpawn,
    LevelData,
    WarpDirection,
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
    ENEMY_SPEED,
    FIREBALL_COOLDOWN,
    FIREBALL_GRAVITY,
    FIREBALL_LIFETIME,
    FIREBALL_SPEED,
    FIREBALL_TERMINAL,
    FIREBALL_VBOUNCE,
    GROUND_ACCELERATION,
    RUN_ACCELERATION,
    GROUND_FRICTION,
    GRAVITY,
    GRAVITY_RISING,
    GRAVITY_CUT,
    HAMMER_GRAVITY,
    JUMP_BUFFER_TIME,
    JUMP_SPEED,
    LOW_TIME_THRESHOLD,
    MAX_FALL_SPEED,
    PIPE_ANIM_DURATION,
    POWERUP_FREEZE,
    RESPAWN_DELAY,
    RUN_SPEED,
    SCREEN_SIZE,
    SHELL_KICK_SPEED,
    SHELL_WAKE_TIME,
    STARTING_LIVES,
    STOMP_COMBO_SCORES,
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
        self.theme: LevelTheme = theme_for(level.meta.name, level.meta.level_type)
        self.underwater = level.meta.level_type.lower() == "underwater"
        self.camera_x = 0.0
        self.camera_y = 0.0
        self.time_bonus_remaining = 0
        self.time_bonus_tick = 0.0
        self.skip_complete = False
        self.score = 0
        self.coins = 0
        self.lives = STARTING_LIVES
        self.player_count = 1
        self.active_player_index = 0
        self.sessions: list[PlayerSession] = []
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
        self.moving_platforms: list[MovingPlatform] = []
        self.falling_platforms: list[FallingPlatform] = []
        self.seesaw_platforms: list[SeesawPlatform] = []
        self.upfires: list[UpFire] = []
        self.firebars: list[FireBar] = []
        self.cheep_spawners: list[CheepSpawner] = []
        self.on_platform: MovingPlatform | FallingPlatform | SeesawPlatform | None = None
        self.time_remaining: float = float(level.meta.time_limit)
        self._low_time_warned = False
        self.complete_timer = 0.0
        self.flagpole_timer = 0.0
        self.flagpole_target_y: float = 0.0
        self.gameover_timer = 0.0
        self.pending_level_warp: str | None = None
        self.restart()

    @property
    def completed(self) -> bool:
        return self.state is WorldState.COMPLETE

    @property
    def is_castle(self) -> bool:
        return self.theme.name == "castle"

    @property
    def world_display(self) -> str:
        """Level name as the HUD WORLD value, e.g. "World 1-1" -> "1-1"."""
        name = self.level.meta.name
        stripped = name.lower().removeprefix("world").strip(" -_")
        return stripped or name or "-"

    def pop_events(self) -> tuple[str, ...]:
        events = tuple(self.events)
        self.events.clear()
        return events

    def restart(self, reset_score: bool = False, player_count: int | None = None) -> None:
        if player_count is not None:
            self.player_count = player_count

        if reset_score or not self.sessions:
            self.active_player_index = 0
            self.sessions = [PlayerSession(character="MARIO")]
            if self.player_count == 2:
                self.sessions.append(PlayerSession(character="LUIGI"))
            
            # Initial sync of global state to MARIO session if reset_score is True
            if reset_score:
                self.score = 0
                self.coins = 0
                self.lives = STARTING_LIVES
                for s in self.sessions:
                    s.score = 0
                    s.coins = 0
                    s.lives = STARTING_LIVES
                    s.state = PowerState.SMALL

        self.apply_from_session()

        spawn = next((entity for entity in self.level.entities if entity.type == "PlayerSpawn"), None)
        spawn_x = (spawn.x if spawn else 3.0) * TILE_SIZE
        spawn_y = (spawn.y if spawn else 13.0) * TILE_SIZE
        self.player = create_player(spawn_x / TILE_SIZE, spawn_y / TILE_SIZE)
        self.player.state = self.sessions[self.active_player_index].state
        self.background_tiles = tuple(tile_rect(tile) for tile in self.level.background)
        self.background_sprites = {
            (tile.x * TILE_SIZE, tile.y * TILE_SIZE): tile.sprite for tile in self.level.background
        }
        solid_tiles = [tile_rect(tile) for tile in self.level.foreground if is_solid_tile(tile)]
        self.solid_tiles: list[pygame.Rect] = solid_tiles
        self.collider = TileCollider(solid_tiles)
        # Non-solid foreground tiles (clouds, bushes, hills, castle) are scenery.
        self.decoration_tiles: list[tuple[pygame.Rect, str]] = [
            (tile_rect(tile), tile.sprite)
            for tile in self.level.foreground
            if not is_solid_tile(tile)
        ]
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
        # Castle axe: touching it drops Bowser and completes the castle level.
        self.axe_rects: list[pygame.Rect] = [
            pygame.Rect(round(e.x * TILE_SIZE), round((e.y - 1) * TILE_SIZE), TILE_SIZE, TILE_SIZE)
            for e in self.level.entities
            if e.type == "CastleAxe"
        ]
        
        self.moving_platforms = [
            MovingPlatform(
                pos=pygame.Vector2(p.start_x * TILE_SIZE, p.start_y * TILE_SIZE),
                velocity=pygame.Vector2(0, 0),
                width=p.width,
                start_pos=pygame.Vector2(p.start_x * TILE_SIZE, p.start_y * TILE_SIZE),
                end_pos=pygame.Vector2(p.end_x * TILE_SIZE, p.end_y * TILE_SIZE),
                speed=p.speed * TILE_SIZE,
                ease_endpoints=p.ease_endpoints,
                ease_distance=p.ease_distance,
            )
            for p in self.level.moving_platforms
        ]
        self.falling_platforms = [
            FallingPlatform(
                pos=pygame.Vector2(p.x * TILE_SIZE, p.y * TILE_SIZE),
                width=p.width,
                fall_speed=p.fall_speed * TILE_SIZE,
            )
            for p in self.level.falling_platforms
        ]
        self.seesaw_platforms = []
        for pair in self.level.seesaw_pairs:
            idx_a = len(self.seesaw_platforms)
            idx_b = idx_a + 1
            self.seesaw_platforms.append(
                SeesawPlatform(
                    pos=pygame.Vector2(pair.ax * TILE_SIZE, pair.ay * TILE_SIZE),
                    width=pair.width,
                    y_neutral=pair.ay * TILE_SIZE,
                    drop_threshold=pair.drop_threshold * TILE_SIZE,
                    partner_idx=idx_b,
                )
            )
            self.seesaw_platforms.append(
                SeesawPlatform(
                    pos=pygame.Vector2(pair.bx * TILE_SIZE, pair.by * TILE_SIZE),
                    width=pair.width,
                    y_neutral=pair.by * TILE_SIZE,
                    drop_threshold=pair.drop_threshold * TILE_SIZE,
                    partner_idx=idx_a,
                )
            )

        self.upfires = [
            UpFire(
                pos=pygame.Vector2(p.x * TILE_SIZE, p.origin_y * TILE_SIZE),
                origin_y=p.origin_y * TILE_SIZE,
                rise_height=p.rise_height * TILE_SIZE,
            )
            for p in self.level.upfires
        ]
        self.firebars = [
            FireBar(
                center=pygame.Vector2(p.center_x * TILE_SIZE, p.center_y * TILE_SIZE),
                segments=p.segments,
                radius=p.radius * TILE_SIZE,
                angular_speed=p.angular_speed,
                angle=p.start_angle,
            )
            for p in self.level.firebars
        ]
        self.cheep_spawners = [
            CheepSpawner(
                entry_x=p.entry_x * TILE_SIZE,
                exit_x=p.exit_x * TILE_SIZE,
                spawn_y=p.spawn_y * TILE_SIZE,
                interval_min=p.interval_min,
                interval_max=p.interval_max,
            )
            for p in self.level.cheep_spawners
        ]

        self.fireballs = []
        self.enemy_projectiles = []
        self.bumps = []
        self.popups = []
        self.particles = []
        self.state = WorldState.PLAYING
        self.respawn_timer = 0.0
        self.coyote_timer = COYOTE_TIME
        self.jump_buffer_timer = 0.0
        self.stomp_combo: int = 1        # C++ ComboState::combo; resets to 1 after kComboWindow
        self.stomp_combo_timer: float = 0.0  # C++ kComboWindow = 0.67s
        self.time_remaining = float(self.level.meta.time_limit)
        self._low_time_warned = False
        self.complete_timer = 0.0
        self.flagpole_timer = 0.0
        self.flagpole_target_y = 0.0
        self.gameover_timer = 0.0
        self.time_bonus_remaining = 0
        self.time_bonus_tick = 0.0
        self.skip_complete = False
        self.on_platform = None
        self.camera_x = max(0.0, self.player.rect.centerx - SCREEN_SIZE[0] * 0.5)
        self.camera_y = self._static_camera_y()

    def _static_camera_y(self) -> float:
        """Vertical framing, mirroring SDL3 getCameraPosition (static per level)."""
        view_h = float(SCREEN_SIZE[1])
        world_h = float(self.level.meta.height * TILE_SIZE)
        bias = TILE_SIZE * 2.0
        if view_h > world_h:
            diff = view_h - world_h
            return max(-diff, -(diff * 0.5) - bias)
        max_y = max(0.0, world_h - view_h)
        target = max(0.0, (world_h - view_h) * 0.5) - bias
        return min(max(target, 0.0), max_y)

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
            # SDL3: after 1.2s the time bonus drains into the score,
            # 1 unit every 0.05s at 50 points per unit.
            if self.skip_complete and self.complete_timer >= 1.0 and self.time_bonus_remaining > 0:
                self.score += self.time_bonus_remaining * 50
                self.time_bonus_remaining = 0
            if self.complete_timer >= 1.2 and self.time_bonus_remaining > 0:
                if self.time_bonus_tick == 0.0:
                    self.events.append("scorering")
                self.time_bonus_tick += dt
                while self.time_bonus_tick >= 0.05 and self.time_bonus_remaining > 0:
                    self.time_bonus_tick -= 0.05
                    self.time_bonus_remaining -= 1
                    self.score += 50
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

        # PLAYING — timer drains 1 unit per real second (matches SDL3).
        self.time_remaining = max(0.0, self.time_remaining - dt)
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

        if self.player.is_shrinking:
            self.player.shrink_timer += dt
            if self.player.shrink_timer >= 0.8:
                self.player.is_shrinking = False
                self.player.shrink_timer = 0.0
                shrink_target = self.player.pending_state if self.player.pending_state is not None else PowerState.SMALL
                self.player.pending_state = None
                self._apply_state_change(shrink_target)

        if self.player.pipe_state != PipeState.NONE:
            self._update_pipe_animation(dt)
            self._tick_effects(dt)
            self._update_camera(dt)
            return

        # C++ ComboState::tick — decay the stomp/kill combo window each frame
        if self.stomp_combo_timer > 0.0:
            self.stomp_combo_timer -= dt
            if self.stomp_combo_timer <= 0.0:
                self.stomp_combo = 1
                self.stomp_combo_timer = 0.0

        self._update_platforms(dt)
        if self.on_platform:
            self.player.pos += self.on_platform.delta_pos

        self._update_player(keys, jump_pressed, jump_held, jump_released, fire_pressed, dt)
        if self.player.pipe_state == PipeState.NONE:
            self._try_start_pipe_entry(keys)
        
        self._handle_platform_collisions()
        
        self._update_enemies(dt)
        self._update_fireballs(dt)
        self._update_enemy_projectiles(dt)
        self._update_collectibles(dt)
        self._update_hazards(dt)
        self._handle_entity_collisions()
        self._handle_goal()
        self._tick_effects(dt)
        self._update_camera(dt)

    def _update_hazards(self, dt: float) -> None:
        # UpFire (C++ UpFireSystem: Resting→Rising→Descending with stepped eased speed + random rest)
        for fire in self.upfires:
            if fire.state == 0:  # Resting
                fire.pos.y = fire.origin_y
                fire.rest_timer -= dt
                if fire.rest_timer <= 0:
                    fire.state = 1
                    fire.progress = 0.0
            elif fire.state == 1:  # Rising
                speed = _upfire_speed(fire.progress, fire.rise_height)
                fire.progress = min(fire.progress + speed * dt, fire.rise_height)
                fire.pos.y = fire.origin_y - fire.progress
                if fire.progress >= fire.rise_height:
                    fire.state = 2
                    fire.progress = 0.0
            else:  # Descending
                speed = _upfire_speed(fire.progress, fire.rise_height)
                fire.progress = min(fire.progress + speed * dt, fire.rise_height)
                fire.pos.y = fire.origin_y - fire.rise_height + fire.progress
                if fire.progress >= fire.rise_height:
                    fire.state = 0
                    # C++ kRestMin=25/60, kRestMax=380/60 (Jukawski: 25-380 frames)
                    fire.rest_timer = random.uniform(25.0 / 60.0, 380.0 / 60.0)

        # FireBar
        for bar in self.firebars:
            bar.angle += bar.angular_speed * dt
        
        # CheepSpawner
        for spawner in self.cheep_spawners:
            if self.player.pos.x >= spawner.entry_x and self.player.pos.x <= spawner.exit_x:
                spawner.timer -= dt
                if spawner.timer <= 0:
                    spawner.timer = random.uniform(spawner.interval_min, spawner.interval_max)
                    new_cheep = create_enemy(EntitySpawn(
                        type="CheepCheep",
                        x=self.player.pos.x / TILE_SIZE + random.uniform(-1, 1),
                        y=spawner.spawn_y / TILE_SIZE
                    ))
                    # Leaping cheeps arc ballistically instead of band-swimming.
                    new_cheep.ai_type = "cheep_spawned"
                    h_dir = random.choice([-1, 1])
                    new_cheep.body.velocity = pygame.Vector2(h_dir * 1.875 * TILE_SIZE, 0.0)
                    new_cheep.ai_timer = 11.0   # jump_distance budget in tiles (C++ SpawnedCheepBehavior default)
                    new_cheep.ai_phase = 0.0    # 0=rising, 1=falling
                    new_cheep.home_x = float(h_dir)  # horizontal direction scratch
                    self.enemies.append(new_cheep)

    # --------------------------------------------------------------- rendering
    def _update_platforms(self, dt: float) -> None:
        # Moving Platforms — C++ MovingPlatformSystem (bounce/ping-pong, half-speed near endpoints)
        for p in self.moving_platforms:
            old_pos = pygame.Vector2(p.pos)
            dist = p.start_pos.distance_to(p.end_pos)
            if dist > 0:
                effective_speed = p.speed
                if p.ease_endpoints and p.ease_distance > 0.0:
                    t_ease = (p.ease_distance * TILE_SIZE) / dist
                    if p.t < t_ease or (1.0 - p.t) < t_ease:
                        effective_speed *= 0.5

                prev_t = p.t
                p.t += (effective_speed / dist) * dt * p.direction
                if p.t >= 1.0:
                    p.t = 1.0
                    p.direction = -1
                elif p.t <= 0.0:
                    p.t = 0.0
                    p.direction = 1

                p.pos = p.start_pos.lerp(p.end_pos, p.t)

            p.delta_pos = p.pos - old_pos

        # Falling Platforms: C++ FallingPlatformSystem — constant fall_speed while player is on top.
        for p in self.falling_platforms:
            old_pos = pygame.Vector2(p.pos)
            if p.has_player:
                p.pos.y += p.fall_speed * dt  # constant speed (not accelerating)
            p.delta_pos = p.pos - old_pos

        # Seesaw Platforms
        processed_seesaws = set()
        for i, p in enumerate(self.seesaw_platforms):
            if i in processed_seesaws:
                continue
            partner = self.seesaw_platforms[p.partner_idx]
            processed_seesaws.add(i)
            processed_seesaws.add(p.partner_idx)

            old_pos_p = pygame.Vector2(p.pos)
            old_pos_partner = pygame.Vector2(partner.pos)

            if p.falling:
                p.pos.y += p.fall_speed * dt
                partner.pos.y += partner.fall_speed * dt
            else:
                if p.has_player and not partner.has_player:
                    move = p.tilt_speed * dt
                    p.pos.y += move
                    partner.pos.y -= move
                elif not p.has_player and partner.has_player:
                    move = partner.tilt_speed * dt
                    partner.pos.y += move
                    p.pos.y -= move
                
                if abs(p.pos.y - p.y_neutral) > p.drop_threshold:
                    p.falling = True
                    partner.falling = True

            p.delta_pos = p.pos - old_pos_p
            partner.delta_pos = partner.pos - old_pos_partner

    def _handle_platform_collisions(self) -> None:
        player_rect = self.player.rect
        # We only check for landing on a platform if we are falling or already on one.
        # But specifically, if the player's feet are just above the platform.
        
        # Reset has_player for all platforms
        for p in self.falling_platforms: p.has_player = False
        for p in self.seesaw_platforms: p.has_player = False
        
        new_on_platform = None
        
        # Check all platforms
        all_platforms = (
            *self.moving_platforms,
            *self.falling_platforms,
            *self.seesaw_platforms,
        )
        
        for p in all_platforms:
            plat_rect = p.rect
            # Check if player is above and moving down (or already on it)
            if (self.player.velocity.y >= 0 and 
                player_rect.right > plat_rect.left and 
                player_rect.left < plat_rect.right and
                player_rect.bottom <= plat_rect.top + 10 and
                player_rect.bottom >= plat_rect.top - 5):
                
                # Snap to top
                self.player.pos.y = plat_rect.top - self.player.size.y
                self.player.velocity.y = 0
                self.player.on_ground = True
                new_on_platform = p
                
                # Set specific state
                if isinstance(p, (FallingPlatform, SeesawPlatform)):
                    p.has_player = True
                break
        
        self.on_platform = new_on_platform

    def player_frame(self) -> str:
        if self.state is WorldState.DYING:
            return "mario_death"
        if self.player.powerup_freeze > 0 or self.player.is_shrinking:
            return "mario_lvlup"

        prefix = self._mario_prefix()

        if self.state is WorldState.LEVEL_END_WALK:
            suffix = ("_end", "_end1")[int(pygame.time.get_ticks() / 100) % 2]
            return f"{prefix}{suffix}"

        if self.player.pipe_state != PipeState.NONE:
            if self.player.state == PowerState.SMALL:
                return prefix
            else:
                return f"{prefix}_squat"

        if self.player.crouching and prefix != "mario":
            return f"{prefix}_squat"
        if self.underwater and not self.player.on_ground:
            phase = int(pygame.time.get_ticks() / 180) % 2
            return f"{prefix}_underwater{phase}"
        if not self.player.on_ground:
            return f"{prefix}_jump"
        if abs(self.player.velocity.x) < 1:
            return prefix
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

        run_held = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]
        if self.underwater:
            # C++ kRunSwimMultiplier=1.5 applied to max_walk_speed only.
            max_speed = WALK_SPEED * (1.5 if run_held else 1.0)
        else:
            max_speed = RUN_SPEED if run_held else WALK_SPEED
        direction = (1 if keys[pygame.K_RIGHT] or keys[pygame.K_d] else 0) - (
            1 if keys[pygame.K_LEFT] or keys[pygame.K_a] else 0
        )

        # Crouch: only meaningful for Big/Fire Mario on the ground; locks horizontal motion.
        crouch_held = (keys[pygame.K_DOWN] or keys[pygame.K_s]) and self.player.on_ground
        crouch_eligible = self.player.state is not PowerState.SMALL and not self.player.is_shrinking
        if crouch_held and crouch_eligible:
            if not self.player.crouching:
                self.player.crouching = True
                # Shrink hitbox: C++ PLAYER_SQUAT_HEIGHT = 1.375 t = 44 px
                self.player.size.y = 44
                self.player.pos.y += 20
            direction = 0  # no horizontal movement while crouched
        elif self.player.crouching:
            # Stand up; restore Big hitbox.
            self.player.crouching = False
            self.player.size.y = 64
            self.player.pos.y -= 20

        if direction:
            self.player.facing = direction
            if self.underwater:
                # C++ updateUnderwaterHorizontalMovement: always uses walk/run accel (not air_accel)
                acceleration = RUN_ACCELERATION if run_held else GROUND_ACCELERATION
            elif not self.player.on_ground:
                acceleration = AIR_ACCELERATION
                max_speed = RUN_SPEED  # C++: air always clamps to max_run_speed (keeps momentum)
            elif run_held:
                acceleration = RUN_ACCELERATION  # C++ run_accel = 35 t/s²
            else:
                acceleration = GROUND_ACCELERATION  # C++ walk_accel = 25 t/s²
            self.player.velocity.x = _approach(self.player.velocity.x, direction * max_speed, acceleration * dt)
        elif self.player.on_ground or self.underwater:
            # C++: ground friction on land; also always applied in underwater (updateUnderwaterHorizontalMovement)
            self.player.velocity.x = _approach(self.player.velocity.x, 0.0, GROUND_FRICTION * dt)

        if self.underwater:
            # Swim: each jump press is an upward stroke (SDL3 underwater swim).
            if jump_pressed:
                self.player.velocity.y = max(self.player.velocity.y - 256.0, -160.0)
                self.player.on_ground = False
                self.events.append("swim")
        elif self.jump_buffer_timer > 0 and self.coyote_timer > 0:
            # C++ PlayerControllerSystem: vel.vy = -jump.base_jump_speed (fixed, no bonuses).
            self.player.velocity.y = -JUMP_SPEED
            self.player.on_ground = False
            self.coyote_timer = 0.0
            self.jump_buffer_timer = 0.0
            self.events.append("jumpbig" if self.player.state is not PowerState.SMALL else "jump")

        # Fireball
        if self.player.fire_cooldown > 0:
            self.player.fire_cooldown = max(0.0, self.player.fire_cooldown - dt)
        if (fire_pressed and self.player.state is PowerState.FIRE
                and not self.player.is_shrinking
                and self.player.fire_cooldown <= 0 and len(self.fireballs) < 2):
            self._spawn_fireball()

        if self.player.invincible_timer > 0:
            self.player.invincible_timer = max(0.0, self.player.invincible_timer - dt)

        if self.underwater:
            # C++ kUWGravityScale=0.25, kUWTerminalVelocity=3 t/s
            self.player.velocity.y = min(self.player.velocity.y + GRAVITY * 0.25 * dt, 96.0)
        else:
            # C++ split gravity: jump_cut=True uses gravity_cut, rising uses gravity_rising, falling uses gravity_falling
            _jump_cut = not jump_held and self.player.velocity.y < 0
            _grav = GRAVITY_CUT if _jump_cut else (GRAVITY_RISING if self.player.velocity.y < 0 else GRAVITY)
            self.player.velocity.y = min(self.player.velocity.y + _grav * dt, MAX_FALL_SPEED)
        head_hits = self.collider.move_and_collide(self.player, dt)
        if self.player.on_ground:
            self.coyote_timer = COYOTE_TIME

        for tile in head_hits:
            self._handle_block_hit(tile)

        if self.player.pos.y > self.level.meta.height * TILE_SIZE + 200:
            self._kill_player(force=True)

    def _try_start_pipe_entry(self, keys: KeyState) -> None:
        want_down = keys[pygame.K_DOWN] or keys[pygame.K_s]
        want_left = keys[pygame.K_LEFT] or keys[pygame.K_a]
        want_right = keys[pygame.K_RIGHT] or keys[pygame.K_d]

        if not (want_down or want_left or want_right):
            return

        # Check tile types at player position/feet
        tx = int(self.player.rect.centerx // TILE_SIZE)
        ty = int(self.player.rect.centery // TILE_SIZE)
        if want_down:
            ty = int((self.player.rect.bottom + 4) // TILE_SIZE)

        tile_key = (tx * TILE_SIZE, ty * TILE_SIZE)
        tile_type = self.tile_types.get(tile_key)
        
        # We also check the tile to the right since pipes are 2 tiles wide
        if tile_type not in {"Pipe", "PipeTop", "PipeBody"}:
            tile_key_r = ((tx + 1) * TILE_SIZE, ty * TILE_SIZE)
            tile_type = self.tile_types.get(tile_key_r)
            if tile_type not in {"Pipe", "PipeTop", "PipeBody"}:
                tile_key_l = ((tx - 1) * TILE_SIZE, ty * TILE_SIZE)
                tile_type = self.tile_types.get(tile_key_l)
                if tile_type not in {"Pipe", "PipeTop", "PipeBody"}:
                    return

        # Find matching warp
        for warp in self.level.warps:
            # Check within 1 tile of the entry definition
            dx = abs(tx - warp.entry_tile_x)
            dy = abs(ty - warp.entry_tile_y)
            
            # For down warps, dy might be 0 if ty was adjusted to bottom+4
            if dx <= 1 and dy <= 1:
                if want_down and warp.entry_dir == WarpDirection.DOWN:
                    self.player.pipe_state = PipeState.ENTERING_DOWN
                elif want_left and warp.entry_dir == WarpDirection.LEFT:
                    self.player.pipe_state = PipeState.ENTERING_LEFT
                elif want_right and warp.entry_dir == WarpDirection.RIGHT:
                    self.player.pipe_state = PipeState.ENTERING_RIGHT
                else:
                    continue
                
                self.player.pipe_timer = PIPE_ANIM_DURATION
                self.player.pipe_dest_x = warp.dest_world_x * TILE_SIZE
                self.player.pipe_dest_y = warp.dest_world_y * TILE_SIZE
                self.player.pipe_dest_level = warp.dest_level
                self.player.pipe_exit_facing_right = warp.exit_facing_right
                self.player.pipe_exit_horizontal = warp.exit_horizontal
                
                # Center player on the entry tile (pipes are 2 tiles wide, warp defines one of them)
                # If it's a vertical pipe, we want to align X.
                if want_down:
                    # In many levels, entry_tile_x is the left tile of the pipe.
                    # Aligning Mario (32px) to a 2-tile pipe (64px) means he's at entry_tile_x * TILE_SIZE + 16
                    # BUT if entry_tile_x is already the "center" or intended position, we use it.
                    # Standard practice is entry_tile_x is the left tile.
                    self.player.pos.x = warp.entry_tile_x * TILE_SIZE
                else:
                    self.player.pos.y = warp.entry_tile_y * TILE_SIZE
                
                self.player.velocity.update(0, 0)
                self.events.append("pipe")
                return

    def _update_pipe_animation(self, dt: float) -> None:
        self.player.pipe_timer -= dt
        speed = (2.0 * TILE_SIZE) / PIPE_ANIM_DURATION
        
        state = self.player.pipe_state
        if state == PipeState.ENTERING_DOWN:
            self.player.pos.y += speed * dt
        elif state == PipeState.ENTERING_RIGHT:
            self.player.pos.x += speed * dt
        elif state == PipeState.ENTERING_LEFT:
            self.player.pos.x -= speed * dt
        elif state == PipeState.EXITING_UP:
            self.player.pos.y -= speed * dt
        elif state == PipeState.EXITING_RIGHT:
            self.player.pos.x += speed * dt
        elif state == PipeState.EXITING_LEFT:
            self.player.pos.x -= speed * dt
            
        if self.player.pipe_timer <= 0:
            if state in {PipeState.ENTERING_DOWN, PipeState.ENTERING_LEFT, PipeState.ENTERING_RIGHT}:
                # Warp trigger
                if self.player.pipe_dest_level and self.player.pipe_dest_level != self.level.meta.name:
                    self.pending_level_warp = self.player.pipe_dest_level
                else:
                    self.player.pos.x = self.player.pipe_dest_x
                    self.player.pos.y = self.player.pipe_dest_y
                    self.player.facing = 1 if self.player.pipe_exit_facing_right else -1
                    
                    if self.player.pipe_exit_horizontal:
                        self.player.pipe_state = PipeState.EXITING_RIGHT if self.player.pipe_exit_facing_right else PipeState.EXITING_LEFT
                    else:
                        self.player.pipe_state = PipeState.EXITING_UP
                    
                    self.player.pipe_timer = PIPE_ANIM_DURATION
                    self.events.append("pipe")
                    # Update camera immediately
                    self.camera_x = max(0.0, self.player.pos.x - SCREEN_SIZE[0] * 0.38)
            else:
                self.player.pipe_state = PipeState.NONE


    def _spawn_fireball(self) -> None:
        direction = 1 if self.player.facing >= 0 else -1
        # C++ spawn: pos.x ± 0.5t from center; pos.y + 0.15t from center (kSpawnYOffset=0.15)
        spawn_x = self.player.pos.x + self.player.size.x * 0.5 + direction * 0.5 * TILE_SIZE
        spawn_y = self.player.pos.y + self.player.size.y * 0.5 + 0.15 * TILE_SIZE
        self.fireballs.append(
            Fireball(
                pos=pygame.Vector2(spawn_x, spawn_y),
                velocity=pygame.Vector2(direction * FIREBALL_SPEED, 0.0),  # C++ initial vy = 0
            )
        )
        self.player.fire_cooldown = FIREBALL_COOLDOWN
        self.events.append("fireball")

    def _update_enemies(self, dt: float) -> None:
        for enemy in list(self.enemies):  # copy because AI may append
            if not enemy.alive:
                if enemy.death_timer > 0:
                    enemy.death_timer -= dt
                    if not enemy.stomp_kill:
                        # C++ DeathType::Hit: physics arc with rising/falling gravity split.
                        _dgrav = GRAVITY_RISING if enemy.body.velocity.y < 0 else GRAVITY
                        enemy.body.velocity.y = min(enemy.body.velocity.y + _dgrav * dt, MAX_FALL_SPEED)
                        enemy.body.pos.y += enemy.body.velocity.y * dt
                continue

            # Off-screen culling — only behind the camera (the player has passed).
            if enemy.body.pos.x + enemy.body.size.x < self.camera_x - ENEMY_DESPAWN_MARGIN:
                enemy.alive = False
                continue

            enemy.age += dt
            if enemy.kick_grace > 0:
                enemy.kick_grace = max(0.0, enemy.kick_grace - dt)
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
            elif ai == "blooper":
                self._update_blooper(enemy, dt)
            elif ai == "cheep":
                self._update_cheep(enemy, dt)
            elif ai == "cheep_spawned":
                self._update_cheep_spawned(enemy, dt)
            elif ai == "podoboo":
                self._update_podoboo(enemy, dt)
            else:
                self._update_walker(enemy, dt)

            if enemy.body.pos.y > self.level.meta.height * TILE_SIZE + 200:
                enemy.alive = False

        # Kicked-shell vs other-enemy collisions (cascading combo scoring).
        for shell in self.enemies:
            if not shell.alive or shell.shell_state is not ShellState.SHELL_KICKED:
                continue
            # C++ ComboState::kComboWindow=0.67s: reset streak when window expires.
            if shell.kick_streak > 0 and shell.combo_timer > 0:
                shell.combo_timer -= dt
                if shell.combo_timer <= 0:
                    shell.kick_streak = 0
            for other in self.enemies:
                if other is shell or not other.alive:
                    continue
                if other.shell_state is ShellState.SHELL_KICKED:
                    continue
                if not shell.body.rect.colliderect(other.body.rect):
                    continue
                other.alive = False
                other.death_timer = 1.0  # C++ DeathType::Hit: death_duration = 1.0s
                other.stomp_kill = False
                other.body.velocity.update(0.0, -256.0)  # C++ markEnemyHitDeath -8 t/s
                self._award_combo_score(other.body.rect.x, other.body.rect.y)
                self.events.append("kick")

        # Prune enemies whose death animation has fully expired.
        self.enemies = [e for e in self.enemies if e.alive or e.death_timer > 0]

    def _update_walker(self, enemy: Enemy, dt: float) -> None:
        # Lakitu egg hatches into a Spiny on landing or after 1.4s (C++ hatch_timer).
        if enemy.frames and enemy.frames[0] == "spikey1_0":
            enemy.ai_timer -= dt
            if enemy.body.on_ground or enemy.ai_timer <= 0:
                enemy.frames = ("spikey0_0", "spikey0_1")
                enemy.body.velocity.x = -1.2 * TILE_SIZE  # C++ Spiny: walk_speed=1.2, direction=-1
            else:
                # C++ LakituEgg: horizontal_speed=1.7 t/s toward player while falling.
                enemy.body.velocity.x = enemy.home_x * 1.7 * TILE_SIZE

        # Wake up sleeping shells.
        if enemy.shell_state is ShellState.SHELL_STILL:
            enemy.shell_wake_timer -= dt
            if enemy.shell_wake_timer <= 0:
                self._wake_shell(enemy)

        # Para-koopas hop every 1.2s while grounded (SDL3 KoopaWingedBehavior).
        if enemy.winged and enemy.body.on_ground:
            enemy.ai_timer -= dt
            if enemy.ai_timer <= 0:
                enemy.ai_timer = 1.1  # C++ EntityFactory: KoopaWingedBehavior.jump_interval = 1.1s
                enemy.body.velocity.y = -8.2 * TILE_SIZE  # C++ EntityFactory override: 8.2 t/s

        before_x = enemy.body.pos.x
        before_vx = enemy.body.velocity.x
        # C++ GravitySystem: rising entities use gravity_rising=55 t/s², falling uses gravity_falling=80 t/s²
        _egrav = GRAVITY_RISING if enemy.body.velocity.y < 0 else GRAVITY
        enemy.body.velocity.y = min(enemy.body.velocity.y + _egrav * dt, MAX_FALL_SPEED)
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
        cycle_speed = 60.0  # C++ move_speed = 30/16 t/s × 32 = 60 px/s
        rise_distance = TILE_SIZE * 2
        player_dx = abs(self.player.pos.x - enemy.home_x)
        # SMB1 gate: rise only when Mario is at least ~2 tiles away (0x21 px).
        retract_threshold = TILE_SIZE * 2.06
        enemy.ai_timer += dt
        # Phases: 0=hidden, 1=rising, 2=emerged, 3=falling
        if enemy.ai_phase == 0:
            if enemy.ai_timer > 64.0 / 60.0 and player_dx > retract_threshold:  # C++ pause_duration
                enemy.ai_phase = 1
                enemy.ai_timer = 0.0
        elif enemy.ai_phase == 1:
            enemy.body.pos.y -= cycle_speed * dt
            if enemy.home_y - enemy.body.pos.y >= rise_distance:
                enemy.body.pos.y = enemy.home_y - rise_distance
                enemy.ai_phase = 2
                enemy.ai_timer = 0.0
        elif enemy.ai_phase == 2:
            if enemy.ai_timer > 64.0 / 60.0:  # C++ pause_duration
                enemy.ai_phase = 3
                enemy.ai_timer = 0.0
        elif enemy.ai_phase == 3:
            enemy.body.pos.y += cycle_speed * dt
            if enemy.body.pos.y >= enemy.home_y:
                enemy.body.pos.y = enemy.home_y
                enemy.ai_phase = 0
                enemy.ai_timer = 0.0

    def _update_blooper(self, enemy: Enemy, dt: float) -> None:
        # SDL3 BlooperBehavior: pulse up toward Mario, hover, drift back down.
        # Phases via ai_phase: 0=diving, 1=rising, 2=gliding. home_y = origin.
        rise_speed = 1.5 * TILE_SIZE
        dive_speed = 0.65 * TILE_SIZE
        h_speed = 0.45 * TILE_SIZE
        upper = enemy.home_y - 0.9375 * TILE_SIZE
        if enemy.ai_phase == 1:  # rising — track the player horizontally
            enemy.frames = ("squid0",)  # C++: contracted squid during rising
            enemy.body.velocity.update(enemy.body.facing * h_speed, -rise_speed)
            enemy.ai_timer -= dt
            if enemy.ai_timer <= 0:  # retarget toward Mario every 0.35s
                enemy.ai_timer = 0.35
                enemy.body.facing = -1 if self.player.pos.x < enemy.body.pos.x else 1
            if enemy.body.pos.y <= upper:
                enemy.ai_phase = 2
                enemy.ai_timer = 0.5
        elif enemy.ai_phase == 2:  # gliding at the peak
            enemy.frames = ("squid1",)  # C++: open squid during gliding
            enemy.body.velocity.update(enemy.body.facing * h_speed * 0.25, 0.0)
            enemy.ai_timer -= dt
            if enemy.ai_timer <= 0:
                enemy.ai_phase = 0
        else:  # diving
            enemy.frames = ("squid1",)  # C++: open squid during diving
            enemy.body.velocity.update(enemy.body.facing * h_speed * 0.2, dive_speed)
            if enemy.body.pos.y >= enemy.home_y:
                enemy.ai_phase = 1
                enemy.ai_timer = 0.0
        enemy.body.pos += enemy.body.velocity * dt

    def _update_cheep(self, enemy: Enemy, dt: float) -> None:
        # SDL3 FlyingCheepCheepBehavior: swim sideways inside a vertical band.
        h_speed = 1.8 * TILE_SIZE
        v_speed = 1.05 * TILE_SIZE
        span = 30.0
        if enemy.body.pos.y <= enemy.home_y - span:
            enemy.ai_phase = 1  # moving down
        elif enemy.body.pos.y >= enemy.home_y + span:
            enemy.ai_phase = 0  # moving up
        enemy.body.velocity.x = enemy.body.facing * h_speed
        enemy.body.velocity.y = v_speed if enemy.ai_phase == 1 else -v_speed
        enemy.body.pos += enemy.body.velocity * dt

    def _update_cheep_spawned(self, enemy: Enemy, dt: float) -> None:
        # C++ SpawnedCheepBehavior: stepped speed table, no gravity, despawn at y>640.
        jd = enemy.ai_timer
        if enemy.ai_phase == 0.0:  # rising
            if   jd > 10.0: vy = 15.0
            elif jd >  9.0: vy = 14.0625
            elif jd >  8.0: vy = 13.125
            elif jd >  6.0: vy = 12.1875
            elif jd >  5.0: vy = 10.3125
            elif jd >  4.0: vy =  8.4375
            elif jd >  2.0: vy =  6.5625
            elif jd >  0.0: vy =  4.6875
            else:
                enemy.ai_phase = 1.0
                enemy.ai_timer = 13.0
                vy = 0.0
            enemy.body.velocity.y = -vy * TILE_SIZE
            enemy.ai_timer -= vy * dt
        else:  # falling
            if   jd > 11.0: vy =  4.6875
            elif jd >  9.0: vy =  6.5625
            elif jd >  8.0: vy =  8.4375
            elif jd >  7.0: vy = 10.3125
            elif jd >  6.0: vy = 12.1875
            elif jd >  4.0: vy = 13.125
            elif jd >  3.0: vy = 14.0625
            else:            vy = 15.0
            enemy.body.velocity.y = vy * TILE_SIZE
            enemy.ai_timer -= vy * dt
        enemy.body.velocity.x = enemy.home_x * 1.875 * TILE_SIZE
        enemy.body.pos += enemy.body.velocity * dt
        if enemy.body.pos.y > 20.0 * TILE_SIZE:  # C++ despawn at pos.y > 20 t
            enemy.alive = False

    def _update_podoboo(self, enemy: Enemy, dt: float) -> None:
        # SDL3 PodobooBehavior: leap out of the lava, fall back, rest, repeat.
        jump_speed = 12.5 * TILE_SIZE   # C++ EntityFactory::createPodoboo overrides to 12.5 t/s
        gravity = 30.0 * TILE_SIZE      # C++ EntityFactory::createPodoboo overrides to 30.0 t/s²
        if enemy.ai_phase == 0:  # resting in the lava
            enemy.body.pos.y = enemy.home_y
            enemy.ai_timer -= dt
            if enemy.ai_timer <= 0:
                enemy.ai_phase = 1
                enemy.body.velocity.y = -jump_speed
        else:  # airborne
            enemy.body.velocity.y += gravity * dt
            enemy.body.pos.y += enemy.body.velocity.y * dt
            if enemy.body.velocity.y > 0 and enemy.body.pos.y >= enemy.home_y:
                enemy.body.pos.y = enemy.home_y
                enemy.body.velocity.y = 0.0
                enemy.ai_phase = 0
                enemy.ai_timer = 1.75  # C++ EntityFactory::createPodoboo overrides to 1.75s

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
        # Vertical bob: C++ sin(bob_timer * 2.5) * 0.25t = 8 px; lerp coeff 0.12/frame × 60fps.
        enemy.ai_phase += dt  # bob_timer accumulator
        bob_target_y = enemy.home_y + math.sin(enemy.ai_phase * 2.5) * 8.0
        enemy.body.pos.y += (bob_target_y - enemy.body.pos.y) * min(1.0, dt * 7.2)

        # Follow player with a lead. C++ LakituBehavior: max_follow_speed=11.0 t/s.
        _MAX_FOLLOW = 11.0 * TILE_SIZE   # 352 px/s
        target_x = self.player.pos.x + 2.5 * TILE_SIZE  # ~lead_distance_medium ahead
        diff = target_x - enemy.body.pos.x
        desired_vx = max(-_MAX_FOLLOW, min(_MAX_FOLLOW, diff * 2.5))
        # C++ smooth blend: vel.vx += (desired - vel.vx) * min(1, dt*12)
        enemy.body.velocity.x += (desired_vx - enemy.body.velocity.x) * min(1.0, dt * 12.0)
        enemy.body.facing = -1 if self.player.pos.x < enemy.body.pos.x else 1
        enemy.body.pos.x += enemy.body.velocity.x * dt
        # Drop a Spiny periodically (countdown equivalent via accumulator).
        enemy.ai_timer += dt
        if enemy.ai_timer > 128.0 / 60.0:  # C++ frenzy_interval = 128/60 ≈ 2.13 s
            enemy.ai_timer = 0.0
            self._spawn_spiny_drop(enemy)

    def _spawn_spiny_drop(self, lakitu: Enemy) -> None:
        from .level import EntitySpawn

        # C++ createLakituEgg: spawn 0.20t ahead + 0.55t below Lakitu, toward player.
        direction = -1 if self.player.pos.x < lakitu.body.pos.x else 1
        spawn_x = (lakitu.body.pos.x + 0.20 * TILE_SIZE * direction) / TILE_SIZE
        spawn_y = (lakitu.body.pos.y + 0.55 * TILE_SIZE) / TILE_SIZE
        spiny = create_enemy(EntitySpawn(type="Spiny", x=spawn_x, y=spawn_y))
        spiny.frames = ("spikey1_0", "spikey1_1")
        spiny.body.velocity.update(direction * 1.7 * TILE_SIZE, 0.0)
        spiny.ai_timer = 1.4   # C++ hatch_timer = 1.4f
        spiny.home_x = float(direction)  # direction preserved for egg-phase velocity
        self.enemies.append(spiny)

    def _update_hammerbro(self, enemy: Enemy, dt: float) -> None:
        # Reuses walker physics but limits horizontal range to ~3 tiles around home_x.
        self._update_walker(enemy, dt)
        if enemy.body.pos.x < enemy.home_x - TILE_SIZE * 2:
            enemy.body.velocity.x = abs(enemy.body.velocity.x or 17.6)  # 0.55 t/s × 32
            enemy.body.facing = 1
        elif enemy.body.pos.x > enemy.home_x + TILE_SIZE * 2:
            enemy.body.velocity.x = -abs(enemy.body.velocity.x or 17.6)
            enemy.body.facing = -1
        # Periodic jump (countdown timer; C++ jump_interval [0.9, 1.4]s).
        enemy.ai_timer -= dt
        if enemy.body.on_ground and enemy.ai_timer <= 0:
            # C++ HammerBroBehavior: 22% chance of high_jump_speed (12.5 t/s), else 8.5 t/s
            js = (12.5 if random.random() < 0.22 else 8.5) * TILE_SIZE
            enemy.body.velocity.y = -js
            enemy.ai_timer = random.uniform(0.9, 1.4)
        # Periodic hammer throw aimed roughly at the player.
        enemy.ai_phase += dt
        if enemy.ai_phase > 48.0 / 60.0:  # C++ throw_interval = 48/60 s
            enemy.ai_phase = 0.0
            if abs(self.player.pos.x - enemy.body.pos.x) < SCREEN_SIZE[0] * 0.7:
                self._throw_hammer(enemy)

    def _update_bowser(self, enemy: Enemy, dt: float) -> None:
        self._update_walker(enemy, dt)
        if enemy.body.pos.x < enemy.home_x - TILE_SIZE * 3:
            enemy.body.velocity.x = abs(enemy.body.velocity.x or 24.0)  # 0.75 t/s × 32
            enemy.body.facing = 1
        elif enemy.body.pos.x > enemy.home_x + TILE_SIZE * 3:
            enemy.body.velocity.x = -abs(enemy.body.velocity.x or 24.0)
            enemy.body.facing = -1
        enemy.ai_timer -= dt
        if enemy.body.on_ground and enemy.ai_timer <= 0:  # C++ jump_interval [1.5, 2.8]s
            enemy.body.velocity.y = -304.0  # C++ jump_speed = 9.5 t/s × 32
            enemy.ai_timer = random.uniform(1.5, 2.8)
        # Bowser breathes fire. C++: random interval [1.5,2.9]s, max 1 active fire.
        enemy.ai_phase += dt
        if enemy.ai_phase > 1.8 and abs(self.player.pos.x - enemy.body.pos.x) < SCREEN_SIZE[0] * 0.9:
            active_fires = sum(1 for p in self.enemy_projectiles if p.kind == "bowserfire" and p.alive)
            if active_fires < 1:  # C++ kMaxActiveBowserFireProjectiles = 1
                enemy.ai_phase = 1.8 - random.uniform(1.5, 2.9)  # C++ fire_interval [1.5,2.9]s
                self._spawn_bowser_fire(enemy)

    # ----------------------------------------------------------- enemy attacks
    def _throw_hammer(self, enemy: Enemy) -> None:
        direction = -1 if self.player.pos.x < enemy.body.pos.x else 1
        self.enemy_projectiles.append(
            EnemyProjectile(
                pos=pygame.Vector2(enemy.body.pos.x + (16 if direction > 0 else -8), enemy.body.pos.y - 16),
                velocity=pygame.Vector2(direction * 121.6, -262.4),  # C++ vx=3.8 t/s, vy=-8.2 t/s
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
                velocity=pygame.Vector2(direction * 120.0, 0.0),  # C++ kBowserFireSpeed = 3.75 t/s × 32
                kind="bowserfire",
                affected_by_gravity=False,
                lifetime=4.0,  # C++ Lifetime(entity, 4.0f)
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
                # C++ hammer: terminal_velocity = 14.0 t/s = 448 px/s (not general MAX_FALL_SPEED)
                proj.velocity.y = min(proj.velocity.y + HAMMER_GRAVITY * dt, 14.0 * TILE_SIZE)
            proj.pos.x += proj.velocity.x * dt
            proj.pos.y += proj.velocity.y * dt
            # Tile collisions: hammers vanish when they land; Bowser fire
            # ignores terrain entirely (SMB1) — only Mario contact stops it.
            if proj.kind == "hammer":
                for tile in self.collider.nearby(proj.rect):
                    if proj.rect.colliderect(tile):
                        if proj.velocity.y > 0:
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
            fireball.velocity.y = min(fireball.velocity.y + FIREBALL_GRAVITY * dt, FIREBALL_TERMINAL)
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
                                collectible.velocity.y = -480.0  # C++ StarItemBounce::bounce_speed = 15 t/s × 32
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
                self.score += 200  # SMB1: coin = 200 points
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
        elif tile_type == "UsedBlock":
            # C++ BlockSystem: used blocks still play the bump reaction (no item given).
            self.bumps.append(BlockBump(rect=pygame.Rect(tile_rect_), sprite="blockq_used"))
            self.events.append("blockhit")
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
        # Visual feedback only — score/coin already counted.
        # C++ createCoinPop: Velocity(0, -5 t/s) = -160 px/s, no gravity, Lifetime 0.5s.
        self.particles.append(
            Particle(
                pos=pygame.Vector2(tile_rect_.x + 4, tile_rect_.y - TILE_SIZE),
                velocity=pygame.Vector2(0, -5.0 * TILE_SIZE),
                sprite="coin_an0",
                timer=0.5,
                gravity_affected=False,
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
                emerge_remaining=30.0 / MUSHROOM_SPEED,  # C++ rise_remaining = 30 px (0.9375 tiles)
            )
        )

    def _spawn_brick_particles(self, tile_rect_: pygame.Rect, sprite: str) -> None:
        # C++ createBrickDebrisBurst: 4 pieces at tile-unit velocities × 32, lifetime 1.2s
        cx = tile_rect_.x + TILE_SIZE * 0.5
        cy = tile_rect_.y + TILE_SIZE * 0.5
        for ox, oy, vx, vy in (
            (-0.18 * TILE_SIZE, 0.0,              -2.8 * TILE_SIZE, -6.8 * TILE_SIZE),
            ( 0.18 * TILE_SIZE, 0.0,               2.8 * TILE_SIZE, -6.8 * TILE_SIZE),
            (-0.18 * TILE_SIZE,  0.22 * TILE_SIZE, -1.6 * TILE_SIZE, -4.6 * TILE_SIZE),
            ( 0.18 * TILE_SIZE,  0.22 * TILE_SIZE,  1.6 * TILE_SIZE, -4.6 * TILE_SIZE),
        ):
            self.particles.append(
                Particle(
                    pos=pygame.Vector2(cx + ox, cy + oy),
                    velocity=pygame.Vector2(vx, vy),
                    sprite=sprite,
                    timer=1.2,
                )
            )

    def _handle_entity_collisions(self) -> None:
        player_rect = self.player.rect

        # Hazards
        if self.player.invincible_timer <= 0:
            for fire in self.upfires:
                if fire.state != 0 and player_rect.colliderect(fire.rect):
                    self._take_damage()
                    return
            for bar in self.firebars:
                for pos in bar.segment_positions:
                    if player_rect.colliderect(pygame.Rect(pos.x - 4, pos.y - 4, 8, 8)):
                        self._take_damage()
                        return

        for enemy in self.enemies:
            if not enemy.alive or not player_rect.colliderect(enemy.body.rect):
                continue
            from_above = (
                self.player.velocity.y > 0
                and player_rect.bottom <= enemy.body.rect.centery + 8
            )

            # Star power: Mario kills anything he touches.
            if self.player.star_timer > 0:
                self._kill_enemy(enemy, score=0, popup_x=enemy.body.rect.x, popup_y=enemy.body.rect.y,
                                 launch_vy=-320.0)  # C++ markEnemyHitDeath -10 t/s
                self._award_combo_score(enemy.body.rect.x, enemy.body.rect.y)
                self.events.append("kick")
                continue

            # Shell-state collisions take priority over walker collisions.
            if enemy.shell_state is ShellState.SHELL_STILL:
                if from_above:
                    self.player.velocity.y = -19.0 * TILE_SIZE  # C++ stomp_bounce = 19.0 t/s
                    self._kick_shell(enemy, direction=1 if self.player.facing >= 0 else -1)
                else:
                    self._kick_shell(
                        enemy,
                        direction=1 if self.player.pos.x < enemy.body.pos.x else -1,
                    )
                continue
            if enemy.shell_state is ShellState.SHELL_KICKED:
                if from_above:
                    self.player.velocity.y = -19.0 * TILE_SIZE  # C++ stomp_bounce = 19.0 t/s
                    enemy.shell_state = ShellState.SHELL_STILL
                    enemy.shell_wake_timer = SHELL_WAKE_TIME
                    enemy.body.velocity.update(0.0, 0.0)
                    enemy.kick_streak = 0
                elif enemy.kick_grace <= 0 and self.player.invincible_timer <= 0:
                    # Fresh kicks have a grace window so the shell clears Mario.
                    self._take_damage()
                    return
                continue

            # Plain walker.
            if from_above and enemy.stompable:
                self.player.velocity.y = -19.0 * TILE_SIZE  # C++ stomp_bounce = 19.0 t/s
                if enemy.winged:
                    # First stomp only strips the wings (SDL3 para-koopa rule).
                    enemy.winged = False
                    enemy.frames = ENEMY_FRAMES.get(
                        "RedKoopa" if enemy.kind == "RedParaKoopa" else "KoopaTroopa",
                        enemy.frames,
                    )
                    self._award_combo_score(enemy.body.rect.x, enemy.body.rect.y)
                    self.events.append("stomp")
                elif enemy.gives_shell:
                    self._convert_to_shell(enemy)
                    self._award_combo_score(enemy.body.rect.x, enemy.body.rect.y)
                else:
                    dead_frame = ENEMY_DEAD_FRAMES.get(enemy.kind)
                    squish = bool(dead_frame)
                    # C++ handleStomp: non-flattenable use markEnemyHitDeath(-9 t/s), no score.
                    launch_vy = 0.0 if squish else -9.0 * TILE_SIZE
                    self._kill_enemy(enemy, score=0, popup_x=enemy.body.rect.x, popup_y=enemy.body.rect.y,
                                     stomp_squish=squish, launch_vy=launch_vy)
                    if squish:
                        # C++ awardComboScore only for flattenable (squish) kills.
                        self._award_combo_score(enemy.body.rect.x, enemy.body.rect.y)
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
                if enemy.kind == "Bowser":
                    # Bowser soaks 5 fireball hits before falling (matches SDL3).
                    fireball.alive = False
                    fireball.explode_timer = 0.15
                    enemy.fireball_hits += 1
                    if enemy.fireball_hits >= 5:
                        self._kill_enemy(enemy, score=5000, popup_x=enemy.body.rect.x, popup_y=enemy.body.rect.y)
                        self.events.append("kick")
                    break
                self._kill_enemy(enemy, score=200, popup_x=enemy.body.rect.x, popup_y=enemy.body.rect.y)  # launch_vy=-256 default
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
            self.score += 200  # SMB1: coin = 200 points
            self.events.append("coin")
            self._popup("200", collectible.rect.x, collectible.rect.y)
            self._maybe_oneup()
        elif collectible.kind == "Mushroom":
            self.score += 1000
            self._popup("1000", collectible.rect.x, collectible.rect.y)
            self.player.invincible_timer = max(self.player.invincible_timer, INVINCIBILITY_TIME)
            if self.player.state is PowerState.SMALL:
                self._begin_powerup(PowerState.SUPER)
            self.events.append("powerup")
        elif collectible.kind in {"FireFlower", "Flower"}:
            self.score += 1000
            self._popup("1000", collectible.rect.x, collectible.rect.y)
            self.player.invincible_timer = max(self.player.invincible_timer, INVINCIBILITY_TIME)
            self._begin_powerup(PowerState.FIRE)
            self.events.append("powerup")
        elif collectible.kind == "Star":
            self.score += 1000
            self._popup("1000", collectible.rect.x, collectible.rect.y)
            self.player.star_timer = 9.17  # 550 frames @ 60fps, matches SDL3
            self.events.append("rainboom")
        elif collectible.kind == "OneUp":
            self.lives += 1
            self.score += 1000  # C++ ItemCollectionSystem: OneUp = 1000 pts
            self.player.invincible_timer = max(self.player.invincible_timer, INVINCIBILITY_TIME)
            self.events.append("oneup")
            self._popup("1UP", collectible.rect.x, collectible.rect.y)

    def _maybe_oneup(self) -> None:
        if self.coins >= 100:
            self.coins -= 100
            self.lives += 1
            self.player.invincible_timer = max(self.player.invincible_timer, INVINCIBILITY_TIME)
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
        # C++ handleDamage: Fire → Big, Big → Small.
        shrink_to = PowerState.SUPER if self.player.state is PowerState.FIRE else PowerState.SMALL
        self.player.is_shrinking = True
        self.player.shrink_timer = 0.0
        self.player.pending_state = shrink_to
        self.player.invincible_timer = INVINCIBILITY_TIME
        self.events.append("shrink")

    def _handle_goal(self) -> None:
        player_rect = self.player.rect
        world_end = self.level.meta.width * TILE_SIZE - TILE_SIZE * 2

        # Castle axe: grabbing it drops Bowser and ends the castle level.
        for axe in self.axe_rects:
            if player_rect.colliderect(axe):
                self.axe_rects.remove(axe)
                for enemy in self.enemies:
                    if enemy.kind == "Bowser" and enemy.alive:
                        self._kill_enemy(enemy, score=5000, popup_x=enemy.body.rect.x, popup_y=enemy.body.rect.y)
                self.player.velocity.update(0.0, 0.0)
                self.events.append("bridgebreak")
                self.events.append("bowserfall")
                self.score += 1000
                self._enter_complete()
                return

        if any(player_rect.colliderect(goal) for goal in self.goal_rects):
            # Touched the flagpole — score by grab height (top of pole = best).
            goal = next(goal for goal in self.goal_rects if player_rect.colliderect(goal))
            self._begin_flagpole_slide(goal)
            return

        if player_rect.x >= world_end:
            # No flagpole found, but Mario walked off the right edge: count as complete.
            self.score += 1000
            self._enter_complete()

    def _enter_complete(self) -> None:
        """Enter COMPLETE with the SDL3 time-bonus countdown queued up."""
        self.state = WorldState.COMPLETE
        self.complete_timer = 0.0
        self.time_bonus_remaining = max(0, int(self.time_remaining))
        self.time_bonus_tick = 0.0
        self.skip_complete = False
        self.events.append("complete")

    def _begin_flagpole_slide(self, goal: pygame.Rect) -> None:
        # Convert vertical position on the pole to a score tier.
        # Top  of pole grants 5000, bottom grants 100.
        top = goal.top
        bottom = goal.top + goal.height
        relative = (self.player.pos.y - top) / max(1.0, (bottom - top))
        relative = max(0.0, min(1.0, relative))
        tiers = (5000, 2000, 1000, 500, 200, 100)
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
        slide_speed = 384.0  # C++ kSlideSpeed = 12.0 t/s × 32
        if self.player.pos.y < self.flagpole_target_y:
            self.player.pos.y = min(self.flagpole_target_y, self.player.pos.y + slide_speed * dt)
            return
        # Mario landed. flagpole_timer counts time since landing (C++ flag_slide_walk_timer_).
        self.flagpole_timer += dt
        if self.flagpole_timer < 0.25:  # C++ kWalkDelay = 0.25s
            return
        # Flip Mario to the right and start walking toward the castle.
        self.player.facing = 1
        self.player.velocity.update(176.0, 0.0)  # C++ kWalkSpeed = 5.5 t/s × 32
        self.complete_timer = 0.0
        self.state = WorldState.LEVEL_END_WALK

    def _update_level_end_walk(self, dt: float) -> None:
        # Mario walks at a fixed pace, then the level completes.
        self.complete_timer += dt
        self.player.pos.x += 176.0 * dt  # C++ kWalkSpeed = 5.5 t/s × 32
        if self.complete_timer >= 1.6:  # C++ kWalkDuration = 1.6s
            self.score += 1000  # base completion bonus
            self._enter_complete()

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
            popup.pos.y -= 64.0 * dt
        self.popups = [popup for popup in self.popups if popup.timer > 0]
        for particle in self.particles:
            particle.timer -= dt
            particle.age += dt
            if particle.gravity_affected:
                particle.velocity.y = min(particle.velocity.y + GRAVITY * dt, MAX_FALL_SPEED)
            particle.pos.x += particle.velocity.x * dt
            particle.pos.y += particle.velocity.y * dt
        self.particles = [particle for particle in self.particles if particle.timer > 0]
        if self.player.star_timer > 0:
            self.player.star_timer = max(0.0, self.player.star_timer - dt)

    def _popup(self, text: str, x: int, y: int) -> None:
        self.popups.append(ScorePopup(text=text, pos=pygame.Vector2(x, y)))

    def _update_camera(self, dt: float) -> None:
        # SDL3 keeps Mario horizontally centered (no smoothing, no backscroll).
        target = self.player.rect.centerx - SCREEN_SIZE[0] * 0.5
        meta = self.level.meta
        # Use camera_max_x from JSON when set; fall back to full level width.
        if meta.camera_max_x > 0:
            max_camera = max(0, int(meta.camera_max_x * TILE_SIZE) - SCREEN_SIZE[0])
        else:
            max_camera = max(0, meta.width * TILE_SIZE - SCREEN_SIZE[0])
        min_camera = int(meta.camera_min_x * TILE_SIZE)
        self.camera_x = max(self.camera_x, min(max(target, float(min_camera)), float(max_camera)))

    def _kill_enemy(self, enemy: Enemy, score: int, popup_x: int, popup_y: int,
                    launch_vy: float = -256.0, stomp_squish: bool = False) -> None:
        enemy.alive = False
        enemy.stomp_kill = stomp_squish
        if stomp_squish:
            # C++ DeathType::Stomped: sprite stays put for 0.2s then disappears.
            enemy.death_timer = 0.2
            enemy.body.velocity.update(0.0, 0.0)
        else:
            # C++ DeathType::Hit: 1.0s duration (or off-screen), launch upward with gravity.
            enemy.death_timer = 1.0
            enemy.body.velocity.x = 0.0  # C++ markEnemyHitDeath: vel.vx = 0
            enemy.body.velocity.y = launch_vy
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
        enemy.body.velocity.x = -ENEMY_SPEED if enemy.body.facing < 0 else ENEMY_SPEED
        enemy.frames = ENEMY_FRAMES.get(enemy.kind, enemy.frames)

    def _kick_shell(self, enemy: Enemy, direction: int) -> None:
        # Kicking awards no points (matches SDL3); only chained shell hits score.
        enemy.shell_state = ShellState.SHELL_KICKED
        enemy.body.velocity.x = SHELL_KICK_SPEED * direction
        enemy.body.facing = direction
        enemy.kick_streak = 0
        enemy.combo_timer = 0.0
        enemy.kick_grace = 0.25  # matches SDL3: ~15 frames of contact immunity
        self.events.append("kick")

    def _award_combo_score(self, popup_x: int, popup_y: int) -> None:
        # C++ awardComboScore: shared across all kill types (stomp, star, shell).
        idx = min(self.stomp_combo - 1, len(STOMP_COMBO_SCORES) - 1)
        bonus = STOMP_COMBO_SCORES[idx]
        self.score += bonus
        self._popup(str(bonus), popup_x, popup_y)
        self.stomp_combo += 1
        self.stomp_combo_timer = 0.67  # C++ kComboWindow

    def sync_to_session(self) -> None:
        if not self.sessions:
            return
        session = self.sessions[self.active_player_index]
        session.score = self.score
        session.coins = self.coins
        session.lives = self.lives
        if hasattr(self, "player"):
            session.state = self.player.state

    def apply_from_session(self) -> None:
        if not self.sessions:
            return
        session = self.sessions[self.active_player_index]
        self.score = session.score
        self.coins = session.coins
        self.lives = session.lives

    def _kill_player(self, force: bool = False) -> None:
        if self.state is not WorldState.PLAYING and not force:
            return
        self.lives -= 1
        self.sync_to_session()
        
        self.state = WorldState.DYING
        self.respawn_timer = RESPAWN_DELAY
        self.player.death_timer = 0.0
        self.player.velocity.update(0.0, -480.0)
        self.events.append("death")

        if self.player_count == 2:
            other_index = (self.active_player_index + 1) % 2
            if self.sessions[other_index].lives > 0:
                self.active_player_index = other_index
                # Update current lives to reflect the next player so Game Over check is correct
                self.lives = self.sessions[self.active_player_index].lives


def _approach(current: float, target: float, amount: float) -> float:
    if current < target:
        return min(current + amount, target)
    if current > target:
        return max(current - amount, target)
    return target


def _upfire_speed(covered: float, total: float) -> float:
    # C++ UpFireSystem stepped speed profile (px/s); thresholds in pixels.
    # Original C++ thresholds in tiles × TILE_SIZE: <2t→7.5, <4t→15, <8t→18.75, else 22.5 t/s
    remaining = total - covered
    if remaining < 64.0:    # < 2 tiles
        return 7.5 * 32.0   # 240 px/s
    if remaining < 128.0:   # < 4 tiles
        return 15.0 * 32.0  # 480 px/s
    if remaining < 256.0:   # < 8 tiles
        return 18.75 * 32.0 # 600 px/s
    return 22.5 * 32.0      # 720 px/s
