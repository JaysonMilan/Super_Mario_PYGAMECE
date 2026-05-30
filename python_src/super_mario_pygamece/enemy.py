from __future__ import annotations

from typing import Any

import pygame

from .entities import Body, Enemy, ShellState
from .level import EntitySpawn
from .settings import ENEMY_SPEED, TILE_SIZE


ENEMY_FRAMES = {
    "Goomba": ("goombas_0", "goombas_1"),
    "KoopaTroopa": ("koopa_0", "koopa_1"),
    "GreenKoopa": ("koopa_0", "koopa_1"),
    "RedKoopa": ("koopa1_0", "koopa1_1"),
    "BuzzyBeetle": ("beetle_0", "beetle_1"),
    "Spiny": ("spiny_0", "spiny_1"),
    "PiranhaPlant": ("piranha_0", "piranha_1"),
    "HammerBro": ("hammerbro_0", "hammerbro_1"),
    "Bowser": ("bowser0", "bowser1"),
    "GreenParaKoopa": ("paratroopa_0", "paratroopa_1"),
    "RedParaKoopa": ("paratroopa_0", "paratroopa_1"),
    "Lakitu": ("lakito_0", "lakito_1"),
    "BulletBill": ("bullet_0", "bullet_0"),
    "CheepCheep": ("cheep_0", "cheep_1"),
    "Blooper": ("squid0", "squid0"),
    "Podoboo": ("upfire", "upfire"),
}


# Per-enemy traits. Anything not listed defaults to a plain stompable walker.
ENEMY_TRAITS: dict[str, dict[str, Any]] = {
    "Goomba": {},
    "KoopaTroopa": {"gives_shell": True},
    "GreenKoopa": {"gives_shell": True},
    "RedKoopa": {"gives_shell": True, "ledge_aware": True},
    "BuzzyBeetle": {"gives_shell": True, "fire_immune": True},
    "Spiny": {"stompable": False, "fire_immune": True, "ledge_aware": True},
    "PiranhaPlant": {"stompable": False, "ai_type": "piranha"},
    "HammerBro": {"ledge_aware": True, "ai_type": "hammerbro"},
    "Podoboo": {"stompable": False, "fire_immune": True},
    "Bowser": {"stompable": False, "fire_immune": True, "ai_type": "bowser"},
    "BulletBill": {"fire_immune": True, "ai_type": "bullet"},
    "GreenParaKoopa": {"gives_shell": True},
    "RedParaKoopa": {"gives_shell": True, "ledge_aware": True},
    "Lakitu": {"stompable": False, "fire_immune": True, "ai_type": "lakitu"},
}


# Sprites that are not the default 30 × 28 walker box.
_LARGE_ENEMY_SIZES = {
    "HammerBro": (28, 56),
    "Bowser": (56, 56),
    "PiranhaPlant": (28, 56),
    "BulletBill": (32, 24),
    "Lakitu": (32, 28),
}


def is_enemy_spawn(spawn: EntitySpawn) -> bool:
    return spawn.type in ENEMY_FRAMES


def create_enemy(spawn: EntitySpawn) -> Enemy:
    width, height = _LARGE_ENEMY_SIZES.get(spawn.type, (30, 28))
    pos_x = spawn.x * TILE_SIZE
    pos_y = spawn.y * TILE_SIZE - height
    traits = ENEMY_TRAITS.get(spawn.type, {})
    ai_type = traits.get("ai_type", "walker")

    # AI-specific spawn tweaks
    velocity = pygame.Vector2(-ENEMY_SPEED, 0.0)
    facing = -1
    if ai_type == "piranha":
        # Start fully retracted inside the pipe (one tile lower than spawn).
        pos_y = spawn.y * TILE_SIZE
        velocity = pygame.Vector2(0.0, 0.0)
    elif ai_type == "bullet":
        velocity = pygame.Vector2(-ENEMY_SPEED * 3, 0.0)
    elif ai_type == "lakitu":
        velocity = pygame.Vector2(0.0, 0.0)
    elif ai_type == "hammerbro":
        velocity = pygame.Vector2(-50.0, 0.0)
    elif ai_type == "bowser":
        velocity = pygame.Vector2(-40.0, 0.0)

    body = Body(
        pos=pygame.Vector2(pos_x, pos_y),
        size=pygame.Vector2(width, height),
        velocity=velocity,
        facing=facing,
    )
    return Enemy(
        body=body,
        frames=ENEMY_FRAMES.get(spawn.type, ("goombas_0", "goombas_1")),
        kind=spawn.type,
        stompable=traits.get("stompable", True),
        fire_immune=traits.get("fire_immune", False),
        ledge_aware=traits.get("ledge_aware", False),
        gives_shell=traits.get("gives_shell", False),
        ai_type=ai_type,
        shell_state=ShellState.WALKING,
        home_x=float(pos_x),
        home_y=float(pos_y),
    )


__all__ = ["ENEMY_FRAMES", "ENEMY_TRAITS", "Enemy", "ShellState", "create_enemy", "is_enemy_spawn"]
