from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

import pygame

from .entities import Body
from .settings import TILE_SIZE


class TileCollider:
    def __init__(self, solid_tiles: Iterable[pygame.Rect]) -> None:
        self._cells: dict[tuple[int, int], list[pygame.Rect]] = defaultdict(list)
        self.tiles: list[pygame.Rect] = []
        for tile in solid_tiles:
            self._add(tile)

    def _add(self, tile: pygame.Rect) -> None:
        self.tiles.append(tile)
        self._cells[(tile.x // TILE_SIZE, tile.y // TILE_SIZE)].append(tile)

    def add(self, tile: pygame.Rect) -> None:
        self._add(tile)

    def remove(self, tile: pygame.Rect) -> None:
        cell_key = (tile.x // TILE_SIZE, tile.y // TILE_SIZE)
        bucket = self._cells.get(cell_key)
        if bucket is not None:
            bucket[:] = [existing for existing in bucket if existing.topleft != tile.topleft]
        self.tiles[:] = [existing for existing in self.tiles if existing.topleft != tile.topleft]

    def nearby(self, rect: pygame.Rect) -> tuple[pygame.Rect, ...]:
        min_x = max(0, rect.left // TILE_SIZE - 1)
        max_x = rect.right // TILE_SIZE + 1
        min_y = max(0, rect.top // TILE_SIZE - 1)
        max_y = rect.bottom // TILE_SIZE + 1
        tiles: list[pygame.Rect] = []
        seen: set[tuple[int, int]] = set()

        for cell_y in range(min_y, max_y + 1):
            for cell_x in range(min_x, max_x + 1):
                for tile in self._cells.get((cell_x, cell_y), ()):
                    key = tile.topleft
                    if key in seen:
                        continue
                    seen.add(key)
                    tiles.append(tile)
        return tuple(tiles)

    def move_and_collide(self, body: Body, dt: float) -> list[pygame.Rect]:
        head_hits: list[pygame.Rect] = []
        body.head_hit = False

        body.pos.x += body.velocity.x * dt
        rect = body.rect
        for tile in self.nearby(rect):
            if rect.colliderect(tile):
                if body.velocity.x > 0:
                    body.pos.x = tile.left - body.size.x
                elif body.velocity.x < 0:
                    body.pos.x = tile.right
                body.velocity.x = 0
                rect = body.rect

        body.pos.y += body.velocity.y * dt
        body.on_ground = False
        rect = body.rect
        for tile in self.nearby(rect):
            if rect.colliderect(tile):
                if body.velocity.y > 0:
                    body.pos.y = tile.top - body.size.y
                    body.on_ground = True
                elif body.velocity.y < 0:
                    body.pos.y = tile.bottom
                    body.head_hit = True
                    head_hits.append(pygame.Rect(tile))
                body.velocity.y = 0
                rect = body.rect
        return head_hits


__all__ = ["Body", "TileCollider"]
