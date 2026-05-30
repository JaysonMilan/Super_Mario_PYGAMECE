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
    shell_frames: tuple[str, ...] = ("koopa_shell_feet_0", "koopa_shell_feet_1")
    # Generic AI scratchpad (different enemies repurpose these fields).
    ai_phase: int = 0
    ai_timer: float = 0.0
    home_x: float = 0.0
    home_y: float = 0.0


@dataclass(slots=True)
class Collectible:
    kind: str
    rect: pygame.Rect
    sprite: str
    velocity: pygame.Vector2 = field(default_factory=pygame.Vector2)
    emerge_remaining: float = 0.0
    on_ground: bool = False


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
    timer: float = 0.18


@dataclass(slots=True)
class ScorePopup:
    text: str
    pos: pygame.Vector2
    timer: float = 0.7


@dataclass(slots=True)
class Particle:
    pos: pygame.Vector2
    velocity: pygame.Vector2
    sprite: str
    timer: float = 0.6
