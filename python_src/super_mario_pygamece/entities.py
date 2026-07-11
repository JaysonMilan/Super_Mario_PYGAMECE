from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import pygame


@dataclass(slots=True)
class Body:
    pos: pygame.Vector2
    size: pygame.Vector2
    velocity: pygame.Vector2
    on_ground: bool = False
    facing: int = 1
    head_hit: bool = False

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(round(self.pos.x), round(self.pos.y), round(self.size.x), round(self.size.y))


class PowerState(Enum):
    SMALL = "small"
    SUPER = "super"
    FIRE = "fire"


class PipeState(Enum):
    NONE = "none"
    ENTERING_DOWN = "entering_down"
    ENTERING_RIGHT = "entering_right"
    ENTERING_LEFT = "entering_left"
    EXITING_UP = "exiting_up"
    EXITING_RIGHT = "exiting_right"
    EXITING_LEFT = "exiting_left"


@dataclass(slots=True)
class Player(Body):
    state: PowerState = PowerState.SMALL
    invincible_timer: float = 0.0
    star_timer: float = 0.0
    fire_cooldown: float = 0.0
    powerup_freeze: float = 0.0
    pending_state: PowerState | None = None
    death_timer: float = 0.0
    crouching: bool = False
    is_shrinking: bool = False
    shrink_timer: float = 0.0
    # Pipe warping
    pipe_state: PipeState = PipeState.NONE
    pipe_timer: float = 0.0
    pipe_dest_x: float = 0.0
    pipe_dest_y: float = 0.0
    pipe_dest_level: str = ""
    pipe_exit_facing_right: bool = True
    pipe_exit_horizontal: bool = False


@dataclass
class PlayerSession:
    character: str  # "MARIO" or "LUIGI"
    score: int = 0
    coins: int = 0
    lives: int = 3
    state: PowerState = PowerState.SMALL


class ShellState(Enum):
    WALKING = "walking"
    SHELL_STILL = "shell_still"
    SHELL_KICKED = "shell_kicked"


@dataclass(slots=True)
class Enemy:
    body: Body
    frames: tuple[str, ...]
    kind: str = "Goomba"
    alive: bool = True
    age: float = 0.0
    death_timer: float = 0.0
    # Per-type traits
    stompable: bool = True
    fire_immune: bool = False
    ledge_aware: bool = False
    gives_shell: bool = False
    ai_type: str = "walker"
    # Shell-state machine (only meaningful when gives_shell is True)
    shell_state: ShellState = ShellState.WALKING
    shell_wake_timer: float = 0.0
    kick_streak: int = 0
    kick_grace: float = 0.0  # freshly kicked shells can't hurt the kicker
    combo_timer: float = 0.0  # C++ ComboState::kComboWindow=0.67s; resets streak when it expires
    stomp_chain: int = 1
    terrain_rebound_armed: bool = False
    stomp_contact_active: bool = False
    level_spawn_active: bool = False
    shell_frames: tuple[str, ...] = ("koopa_shell_feet_0", "koopa_shell_feet_1")
    walk_frames: tuple[str, ...] = ()
    stomp_frame: str = ""
    fireball_hits: int = 0  # Bowser soaks several hits before going down
    star_immune: bool = False  # C++ star_vulnerable=false (Bowser, Podoboo)
    winged: bool = False  # para-koopas hop; first stomp strips the wings
    stomp_kill: bool = False  # squish-in-place death (Goomba); no physics applied
    # Generic AI scratchpad (different enemies repurpose these fields).
    ai_phase: float = 0.0  # generic timer scratch (seconds accumulated or countdown)
    ai_timer: float = 0.0
    home_x: float = 0.0
    home_y: float = 0.0
    spawn_velocity: pygame.Vector2 = field(default_factory=pygame.Vector2)


@dataclass(slots=True)
class Collectible:
    kind: str
    rect: pygame.Rect
    sprite: str
    velocity: pygame.Vector2 = field(default_factory=pygame.Vector2)
    emerge_remaining: float = 0.0
    on_ground: bool = False


@dataclass(slots=True)
class Spring:
    rect: pygame.Rect
    bounce_speed: float
    anim_timer: float = 0.0
    anim_phase: int = 0


@dataclass(slots=True)
class Vine:
    rect: pygame.Rect
    dest_level: str = ""
    dest_world_x: float = 0.0
    dest_world_y: float = 0.0


@dataclass(slots=True)
class EnemyProjectile:
    pos: pygame.Vector2
    velocity: pygame.Vector2
    kind: str  # "hammer" | "bowserfire" | "venusfire"
    age: float = 0.0
    alive: bool = True
    affected_by_gravity: bool = True
    lifetime: float = 4.0

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(round(self.pos.x), round(self.pos.y), 16, 16)


@dataclass(slots=True)
class Fireball:
    pos: pygame.Vector2
    velocity: pygame.Vector2
    age: float = 0.0
    alive: bool = True
    explode_timer: float = 0.0

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(round(self.pos.x), round(self.pos.y), 14, 14)


@dataclass(slots=True)
class BlockBump:
    rect: pygame.Rect
    sprite: str
    timer: float = 0.12  # C++ BlockSystem::kBlockBumpDuration = 0.12f


@dataclass(slots=True)
class ScorePopup:
    text: str
    pos: pygame.Vector2
    timer: float = 1.2  # C++ ScorePopup max_lifetime = 1.2f


@dataclass(slots=True)
class Particle:
    pos: pygame.Vector2
    velocity: pygame.Vector2
    sprite: str
    timer: float = 0.6
    age: float = 0.0
    gravity_affected: bool = True


@dataclass(slots=True)
class MovingPlatform:
    pos: pygame.Vector2
    velocity: pygame.Vector2
    width: float
    start_pos: pygame.Vector2
    end_pos: pygame.Vector2
    speed: float
    ease_endpoints: bool = False
    ease_distance: float = 2.0
    loop_mode: bool = False
    # Runtime state
    t: float = 0.0  # 0.0 to 1.0 interpolation
    direction: int = 1
    delta_pos: pygame.Vector2 = field(default_factory=lambda: pygame.Vector2(0, 0))

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(round(self.pos.x), round(self.pos.y), round(self.width * 32), 16)


@dataclass(slots=True)
class FallingPlatform:
    pos: pygame.Vector2
    width: float
    fall_speed: float
    # Runtime state
    falling: bool = False
    has_player: bool = False
    delta_y: float = 0.0
    delta_pos: pygame.Vector2 = field(default_factory=lambda: pygame.Vector2(0, 0))

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(round(self.pos.x), round(self.pos.y), round(self.width * 32), 16)


@dataclass(slots=True)
class SeesawPlatform:
    pos: pygame.Vector2
    width: float
    y_neutral: float
    drop_threshold: float
    # Runtime state
    partner_idx: int = -1
    falling: bool = False
    has_player: bool = False
    delta_y: float = 0.0
    fall_speed: float = 5.0 * 32.0  # px/s  C++ SeesawPlatform::fall_speed = 5.0 t/s
    tilt_speed: float = 1.5 * 32.0  # px/s  C++ SeesawPlatform::tilt_speed = 1.5 t/s
    delta_pos: pygame.Vector2 = field(default_factory=lambda: pygame.Vector2(0, 0))

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(round(self.pos.x), round(self.pos.y), round(self.width * 32), 16)


@dataclass(slots=True)
class UpFire:
    pos: pygame.Vector2
    origin_y: float
    rise_height: float  # pixels (= def.rise_height * TILE_SIZE)
    # Runtime state: 0=resting, 1=rising, 2=descending (C++ UpFireBehavior::State)
    state: int = 0
    progress: float = 0.0   # pixels covered in current rise/descend pass
    rest_timer: float = 1.0  # countdown to next rise (s)

    @property
    def rect(self) -> pygame.Rect:
        # C++ kHW=0.25t=8px, kHH=0.375t=12px half-extents → 16×24 total; pos is top-left in Python.
        return pygame.Rect(round(self.pos.x), round(self.pos.y), 16, 24)


@dataclass(slots=True)
class FireBar:
    center: pygame.Vector2
    segments: int
    radius: float
    angular_speed: float
    angle: float

    @property
    def segment_positions(self) -> list[pygame.Vector2]:
        # C++ createFireBar: spacing = radius / (segments-1), segment i at dist = spacing*i.
        spacing = self.radius / (self.segments - 1) if self.segments > 1 else 0.0
        direction = pygame.math.Vector2(1, 0).rotate_rad(self.angle)
        return [
            pygame.Vector2(
                self.center.x + direction.x * spacing * i,
                self.center.y + direction.y * spacing * i,
            )
            for i in range(self.segments)
        ]


@dataclass(slots=True)
class CheepSpawner:
    entry_x: float
    exit_x: float
    spawn_y: float
    interval_min: float
    interval_max: float
    # Runtime state
    timer: float = 0.0
