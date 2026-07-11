from __future__ import annotations

import random
from typing import Any

import pygame

from .entities import Body, Enemy, ShellState
from .level import EntitySpawn
from .settings import ENEMY_SPEED, TILE_SIZE


ENEMY_FRAMES = {
    "Goomba": ("goombas_0", "goombas_1"),
    "KoopaTroopa": ("koopa_0", "koopa_1"),
    "GreenKoopa": ("koopa_0", "koopa_1"),
    "RedKoopa": ("koopa2_0", "koopa2_1"),
    "BuzzyBeetle": ("beetle_0", "beetle_1"),
    "Spiny": ("spikey0_0", "spikey0_1"),
    "PiranhaPlant": ("plant_0", "plant_1"),
    "HammerBro": ("hammerbro_0", "hammerbro_1"),
    "Bowser": ("bowser0",),
    "GreenParaKoopa": ("koopa1_2", "koopa1_3"),
    "RedParaKoopa": ("koopa2_2", "koopa2_3"),
    "Lakitu": ("lakito_0", "lakito_1"),
    "BulletBill": ("bulletbill", "bulletbill"),
    "CheepCheep": ("cheep0", "cheep1"),
    "Blooper": ("squid0", "squid1"),
    "Podoboo": ("lava_0", "lava_1"),
}

# Shell-state sprite per enemy type (matches C++ EnemyVisualSet::shell_static_frame)
SHELL_FRAMES: dict[str, tuple[str, ...]] = {
    "KoopaTroopa":    ("koopa_ded",),
    "GreenKoopa":     ("koopa_ded",),
    "RedKoopa":       ("koopa2_ded",),
    "GreenParaKoopa": ("koopa1_ded",),
    "RedParaKoopa":   ("koopa2_ded",),
    "BuzzyBeetle":    ("beetle_2",),
}

# Stomped/dead sprite shown briefly after killing a non-shell enemy
ENEMY_DEAD_FRAMES: dict[str, str] = {
    "Goomba": "goombas_ded",
}


# Per-enemy traits. Anything not listed defaults to a plain stompable walker.
ENEMY_TRAITS: dict[str, dict[str, Any]] = {
    "Goomba": {},
    "KoopaTroopa": {"gives_shell": True},
    "GreenKoopa": {"gives_shell": True},
    "RedKoopa": {"gives_shell": True, "ledge_aware": True},
    "BuzzyBeetle": {"gives_shell": True, "fire_immune": True},
    "Spiny": {"stompable": False, "ledge_aware": True},
    "PiranhaPlant": {"stompable": False, "ai_type": "piranha"},
    "HammerBro": {"ledge_aware": True, "ai_type": "hammerbro"},
    "Podoboo": {"stompable": False, "fire_immune": True, "star_immune": True, "ai_type": "podoboo"},
    "Bowser": {"stompable": False, "star_immune": True, "ai_type": "bowser"},
    "BulletBill": {"ai_type": "bullet"},
    "GreenParaKoopa": {"gives_shell": True, "winged": True},
    "RedParaKoopa": {"gives_shell": True, "ledge_aware": True, "winged": True},
    "Lakitu": {"ai_type": "lakitu"},
    "Blooper": {"stompable": False, "ai_type": "blooper"},
    "CheepCheep": {"ai_type": "cheep"},
}


# Sprites that are not the default 30 × 28 walker box.
_LARGE_ENEMY_SIZES = {
    "HammerBro": (28, 56),
    "Bowser": (56, 56),
    "PiranhaPlant": (28, 56),
    "BulletBill": (32, 24),
    "Lakitu": (32, 28),
    "Blooper": (28, 42),
}


def is_enemy_spawn(spawn: EntitySpawn) -> bool:
    return spawn.type in ENEMY_FRAMES


def create_enemy(spawn: EntitySpawn) -> Enemy:
    width, height = _LARGE_ENEMY_SIZES.get(spawn.type, (30, 28))
    pos_x = spawn.x * TILE_SIZE
    pos_y = spawn.y * TILE_SIZE - height
    traits = ENEMY_TRAITS.get(spawn.type, {})
    ai_type = traits.get("ai_type", "walker")

    # C++ walk_speed per type (t/s × 32). Goomba = 1.0, Koopa/BuzzyBeetle/Spiny = 1.2.
    _KOOPA_SPEED = 1.2 * TILE_SIZE
    _WALKER_SPEEDS: dict[str, float] = {
        "KoopaTroopa": _KOOPA_SPEED,
        "GreenKoopa": _KOOPA_SPEED,
        "RedKoopa": _KOOPA_SPEED,
        "BuzzyBeetle": _KOOPA_SPEED,
        "Spiny": _KOOPA_SPEED,
        "GreenParaKoopa": _KOOPA_SPEED,
        "RedParaKoopa": _KOOPA_SPEED,
    }
    walk_speed = _WALKER_SPEEDS.get(spawn.type, ENEMY_SPEED)

    # AI-specific spawn tweaks
    velocity = pygame.Vector2(-walk_speed, 0.0)
    facing = -1
    if ai_type == "piranha":
        # Start fully retracted inside the pipe (one tile lower than spawn).
        pos_y = spawn.y * TILE_SIZE
        velocity = pygame.Vector2(0.0, 0.0)
    elif ai_type == "bullet":
        velocity = pygame.Vector2(-208.0, 0.0)  # C++ BulletBillProjectile::speed = 6.5 t/s × 32
    elif ai_type == "lakitu":
        velocity = pygame.Vector2(0.0, 0.0)
    elif ai_type == "hammerbro":
        velocity = pygame.Vector2(-17.6, 0.0)  # C++ HammerBro walk_speed = 0.55 t/s × 32
    elif ai_type == "bowser":
        velocity = pygame.Vector2(-24.0, 0.0)  # C++ Bowser walk_speed = 0.75 t/s × 32
    elif ai_type in {"blooper", "cheep", "podoboo"}:
        # Swimmers and lava fire manage their own velocity; no walk impulse.
        velocity = pygame.Vector2(0.0, 0.0)

    body = Body(
        pos=pygame.Vector2(pos_x, pos_y),
        size=pygame.Vector2(width, height),
        velocity=velocity,
        facing=facing,
    )
    # Initial ai_timer / ai_phase for countdown-based AIs (C++ struct defaults).
    winged = traits.get("winged", False)
    initial_home_x = float(pos_x)
    initial_home_y = float(pos_y)
    if ai_type == "lakitu":
        # home_x repurposed as current_lead_distance (px). C++ start = lead_distance_slow = 21/16 t.
        initial_home_x = 1.3125 * TILE_SIZE
    elif ai_type == "hammerbro":
        initial_ai_timer = 0.5   # C++ HammerBroBehavior.jump_timer = 0.5f
        initial_ai_phase = 48.0 / 60.0 - 0.6  # throw_timer=0.6f; pre-advance so first throw at 0.6s
    elif ai_type == "bowser":
        # C++ EntityFactory: jump_timer = 1.15 + stableSeed*0.12 → [1.15, 1.27]s
        initial_ai_timer = random.uniform(1.15, 1.27)
        # C++ fire_timer = 0.90 + stableSeed*0.10 → [0.90, 1.00]s; Python threshold 1.8 → pre-advance = 1.8 - fire_timer
        initial_ai_phase = random.uniform(0.80, 0.90)
        # home_y repurposed as hammer_timer countdown (Bowser patrol only uses home_x).
        # C++ EntityFactory: hammer_timer = 1.20 + stableSeed*0.10 → [1.20, 1.30]s
        initial_home_y = random.uniform(1.20, 1.30)
    elif ai_type == "podoboo":
        # C++ EntityFactory: cooldown_timer = 0.6 + stableSeed(x,4)*0.2 → range [0.6, 0.8]s
        initial_ai_timer = random.uniform(0.6, 0.8)
        initial_ai_phase = 0.0
    elif winged:
        # C++ KoopaWingedBehavior.jump_timer = 0.4 + stableSeed(x,3)*0.2 (stagger per-position)
        initial_ai_timer = random.uniform(0.4, 0.6)
        initial_ai_phase = 0.0
    else:
        initial_ai_timer = 0.0
        initial_ai_phase = 0.0
    frames = ENEMY_FRAMES.get(spawn.type, ("goombas_0", "goombas_1"))
    return Enemy(
        body=body,
        frames=frames,
        walk_frames=frames,
        kind=spawn.type,
        stompable=traits.get("stompable", True),
        fire_immune=traits.get("fire_immune", False),
        star_immune=traits.get("star_immune", False),
        ledge_aware=traits.get("ledge_aware", False),
        gives_shell=traits.get("gives_shell", False),
        ai_type=ai_type,
        shell_state=ShellState.WALKING,
        home_x=initial_home_x,
        home_y=initial_home_y,
        winged=winged,
        shell_frames=SHELL_FRAMES.get(spawn.type, ("koopa_ded",)),
        ai_timer=initial_ai_timer,
        ai_phase=initial_ai_phase,
        spawn_velocity=pygame.Vector2(velocity),
    )


__all__ = [
    "ENEMY_DEAD_FRAMES",
    "ENEMY_FRAMES",
    "ENEMY_TRAITS",
    "SHELL_FRAMES",
    "Enemy",
    "ShellState",
    "create_enemy",
    "is_enemy_spawn",
]
