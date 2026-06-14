from __future__ import annotations

import pygame

from .entities import Player, PowerState
from .settings import TILE_SIZE


SMALL_SIZE = pygame.Vector2(26, 32)   # C++: AABB 0.8t × 1.0t = 25.6×32 px
BIG_SIZE = pygame.Vector2(26, 64)     # C++: AABB 0.8t × 2.0t = 25.6×64 px


def create_player(spawn_x_tiles: float = 3.0, spawn_y_tiles: float = 13.0) -> Player:
    return Player(
        pos=pygame.Vector2(spawn_x_tiles * TILE_SIZE, spawn_y_tiles * TILE_SIZE - SMALL_SIZE.y),
        size=pygame.Vector2(SMALL_SIZE),
        velocity=pygame.Vector2(),
        facing=1,
        state=PowerState.SMALL,
    )


def player_size_for(state: PowerState) -> pygame.Vector2:
    if state is PowerState.SMALL:
        return pygame.Vector2(SMALL_SIZE)
    return pygame.Vector2(BIG_SIZE)
