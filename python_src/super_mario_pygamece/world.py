from __future__ import annotations

import random
from enum import Enum
from typing import Protocol

import pygame

from . import collision as collision_logic
from . import enemy_ai
from .enemy import ENEMY_FRAMES, create_enemy, is_enemy_spawn
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
    COYOTE_TIME,
    DEATH_ANIM_DURATION,
    ENEMY_DESPAWN_MARGIN,
    ENEMY_SPEED,
    FIREBALL_COOLDOWN,
    FIREBALL_GRAVITY,
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
        self._enemy_ai_handlers = {
            "piranha": self._update_piranha,
            "bullet": self._update_bullet,
            "lakitu": self._update_lakitu,
            "hammerbro": self._update_hammerbro,
            "bowser": self._update_bowser,
            "blooper": self._update_blooper,
            "cheep": self._update_cheep,
            "cheep_spawned": self._update_cheep_spawned,
            "podoboo": self._update_podoboo,
        }

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
            # C++ phase 1: physics run for death_duration=3.0s, then 2.0s extra wait before respawn.
            if self.player.death_timer < DEATH_ANIM_DURATION:
                _dgrav = GRAVITY_RISING if self.player.velocity.y < 0 else GRAVITY
                self.player.velocity.y = min(self.player.velocity.y + _dgrav * dt, MAX_FALL_SPEED)
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
            self.respawn_timer = DEATH_ANIM_DURATION + RESPAWN_DELAY  # 3.0s anim + 2.0s delay
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

        self._update_player(keys, jump_pressed, jump_held, fire_pressed, dt)
        if self.player.pipe_state == PipeState.NONE:
            self._try_start_pipe_entry(keys)
        
        self._handle_platform_collisions()
        
        self._update_enemies(dt)
        self._update_fireballs(dt)
        self._update_enemy_projectiles(dt)
        self._update_collectibles(dt)
        self._update_hazards(dt)
        self._handle_entity_collisions()
        self._handle_goal(dt)
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
                    # Leaping cheeps arc ballistically; C++ SpawnedCheep stompable=false.
                    new_cheep.ai_type = "cheep_spawned"
                    new_cheep.stompable = False
                    h_dir = random.choice([-1, 1])
                    new_cheep.body.velocity = pygame.Vector2(h_dir * 1.875 * TILE_SIZE, 0.0)
                    new_cheep.ai_timer = 11.0   # jump_distance budget in tiles (C++ SpawnedCheepBehavior default)
                    new_cheep.ai_phase = 0.0    # 0=rising, 1=falling
                    new_cheep.home_x = float(h_dir)  # horizontal direction scratch
                    self.enemies.append(new_cheep)

    # --------------------------------------------------------------- rendering
    def _update_platforms(self, dt: float) -> None:
        collision_logic.update_platforms(self, dt)

    def _handle_platform_collisions(self) -> None:
        collision_logic.handle_platform_collisions(self)

    def player_frame(self) -> str:
        if self.state is WorldState.DYING:
            return "mario_death"
        if self.player.powerup_freeze > 0 or self.player.is_shrinking:
            return "mario_lvlup"

        prefix = self._mario_prefix()

        if self.state is WorldState.LEVEL_END_WALK:
            phase = int(pygame.time.get_ticks() / 100) % 3
            return f"{prefix}_move{phase}"

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
            handler = self._enemy_ai_handlers.get(enemy.ai_type, self._update_walker)
            handler(enemy, dt)

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
                if other.star_immune:
                    # C++ EnemyShell: shells bounce off star-immune enemies (Bowser, Podoboo).
                    shell.body.velocity.x = -shell.body.velocity.x
                    shell.body.facing = -shell.body.facing
                    break
                other.alive = False
                other.death_timer = 1.0  # C++ DeathType::Hit: death_duration = 1.0s
                other.stomp_kill = False
                other.body.velocity.update(0.0, -256.0)  # C++ markEnemyHitDeath -8 t/s
                self._award_combo_score(other.body.rect.x, other.body.rect.y)
                self.events.append("kick")

        # Prune enemies whose death animation has fully expired.
        self.enemies = [e for e in self.enemies if e.alive or e.death_timer > 0]

    def _update_walker(self, enemy: Enemy, dt: float) -> None:
        enemy_ai.update_walker(self, enemy, dt)

    def _update_piranha(self, enemy: Enemy, dt: float) -> None:
        enemy_ai.update_piranha(self, enemy, dt)

    def _update_blooper(self, enemy: Enemy, dt: float) -> None:
        enemy_ai.update_blooper(self, enemy, dt)

    def _update_cheep(self, enemy: Enemy, dt: float) -> None:
        enemy_ai.update_cheep(self, enemy, dt)

    def _update_cheep_spawned(self, enemy: Enemy, dt: float) -> None:
        enemy_ai.update_cheep_spawned(self, enemy, dt)

    def _update_podoboo(self, enemy: Enemy, dt: float) -> None:
        enemy_ai.update_podoboo(self, enemy, dt)

    def _update_bullet(self, enemy: Enemy, dt: float) -> None:
        enemy_ai.update_bullet(self, enemy, dt)

    def _update_lakitu(self, enemy: Enemy, dt: float) -> None:
        enemy_ai.update_lakitu(self, enemy, dt)

    def _spawn_spiny_drop(self, lakitu: Enemy) -> None:
        enemy_ai.spawn_spiny_drop(self, lakitu)

    def _update_hammerbro(self, enemy: Enemy, dt: float) -> None:
        enemy_ai.update_hammerbro(self, enemy, dt)

    def _update_bowser(self, enemy: Enemy, dt: float) -> None:
        enemy_ai.update_bowser(self, enemy, dt)

    def _throw_hammer(self, enemy: Enemy) -> None:
        enemy_ai.throw_hammer(self, enemy)

    def _throw_bowser_hammer(self, enemy: Enemy) -> None:
        enemy_ai.throw_bowser_hammer(self, enemy)

    def _spawn_bowser_fire(self, enemy: Enemy) -> None:
        enemy_ai.spawn_bowser_fire(self, enemy)

    def _update_enemy_projectiles(self, dt: float) -> None:
        enemy_ai.update_enemy_projectiles(self, dt)

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
                        # C++ TileCollisionSystem: ceiling just snaps position, no dampen.
                        fireball.pos.y = tile.bottom
                        fireball.velocity.y = 0.0
            if fireball.pos.x < self.camera_x - 80 or fireball.pos.x > self.camera_x + SCREEN_SIZE[0] + 80:
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
                self._spawn_block_coin(tile_rect_)
                self._popup("200", tile_rect_.x, tile_rect_.y)
                # C++: plays "oneup" instead of "coin" on the 100th coin (not both).
                if not self._maybe_oneup():
                    self.events.append("coin")
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
        collision_logic.handle_entity_collisions(self)

    def _collect(self, collectible: Collectible) -> None:
        if collectible.kind == "Coin":
            self.coins += 1
            self.score += 200  # SMB1: coin = 200 points
            self._popup("200", collectible.rect.x, collectible.rect.y)
            # C++: plays "oneup" instead of "coin" on the 100th coin (not both).
            if not self._maybe_oneup():
                self.events.append("coin")
        elif collectible.kind == "Mushroom":
            self.score += 1000
            self._popup("1000", collectible.rect.x, collectible.rect.y)
            if self.player.state is PowerState.SMALL:
                # C++: invincible only when form actually changes (Small → Big).
                self.player.invincible_timer = max(self.player.invincible_timer, INVINCIBILITY_TIME)
                self._begin_powerup(PowerState.SUPER)
            self.events.append("powerup")
        elif collectible.kind in {"FireFlower", "Flower"}:
            self.score += 1000
            self._popup("1000", collectible.rect.x, collectible.rect.y)
            if self.player.state is not PowerState.FIRE:
                # C++: invincible + form change only when not already Fire.
                self.player.invincible_timer = max(self.player.invincible_timer, INVINCIBILITY_TIME)
                self._begin_powerup(PowerState.FIRE)
            self.events.append("powerup")
        elif collectible.kind == "Star":
            self.score += 1000
            self._popup("1000", collectible.rect.x, collectible.rect.y)
            self.player.star_timer = 9.17  # 550 frames @ 60fps, matches SDL3
            self.events.append("starpower")
        elif collectible.kind == "OneUp":
            self.lives += 1
            self.score += 1000  # C++ ItemCollectionSystem: OneUp = 1000 pts
            self.player.invincible_timer = max(self.player.invincible_timer, INVINCIBILITY_TIME)
            self.events.append("oneup")
            self._popup("1UP!", collectible.rect.x, collectible.rect.y)

    def _maybe_oneup(self) -> bool:
        if self.coins >= 100:
            self.coins -= 100
            self.lives += 1
            self.player.invincible_timer = max(self.player.invincible_timer, INVINCIBILITY_TIME)
            self.events.append("oneup")
            return True
        return False

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

    def _handle_goal(self, dt: float) -> None:
        player_rect = self.player.rect
        world_end = self.level.meta.width * TILE_SIZE - TILE_SIZE * 2

        # Castle axe: grabbing it drops Bowser and ends the castle level.
        for axe in self.axe_rects:
            if player_rect.colliderect(axe):
                self.axe_rects.remove(axe)
                for enemy in self.enemies:
                    if enemy.kind == "Bowser" and enemy.alive:
                        # C++ knockBowserIntoDefeat: vx=-1.5 t/s, vy=-11.0 t/s; awards 5000; no "bowserfall" sound.
                        self._kill_enemy(enemy, score=5000, popup_x=enemy.body.rect.x, popup_y=enemy.body.rect.y,
                                         launch_vy=-11.0 * TILE_SIZE)
                        enemy.body.velocity.x = -1.5 * TILE_SIZE
                self.player.velocity.update(0.0, 0.0)
                self.events.append("bridgebreak")  # C++ triggerCastleAxeSequence: only "bridgebreak"
                self._enter_complete()
                return

        if any(player_rect.colliderect(goal) for goal in self.goal_rects):
            # Touched the flagpole — score by grab height (top of pole = best).
            goal = next(goal for goal in self.goal_rects if player_rect.colliderect(goal))
            self._begin_flagpole_slide(goal, dt)
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
        self.events.append("castlecomplete" if self.is_castle else "complete")

    def _begin_flagpole_slide(self, goal: pygame.Rect, dt: float) -> None:
        # C++ MarioGame: kPoleHeight=10t, frac=clamp(1-(y-pole_top)/10t, 0,1)
        # kBonusTable={100,200,500,1000,2000,5000}, bonus_idx=int(frac*5) clamped [0,5].
        pole_bottom_px = float(goal.bottom)
        pole_height_px = 10.0 * TILE_SIZE  # C++ kPoleHeight = 10 tiles
        pole_top_px = pole_bottom_px - pole_height_px
        player_center_y = self.player.pos.y + self.player.size.y * 0.5
        frac = max(0.0, min(1.0, 1.0 - (player_center_y - pole_top_px) / pole_height_px))
        bonus_table = (100, 200, 500, 1000, 2000, 5000)
        bonus_idx = min(int(frac * 5.0), 5)
        bonus = bonus_table[bonus_idx]
        self.score += bonus
        self._popup(str(bonus), int(self.player.pos.x), int(self.player.pos.y))
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
        self.respawn_timer = DEATH_ANIM_DURATION + RESPAWN_DELAY  # 3.0s anim + 2.0s delay = 5.0s
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
