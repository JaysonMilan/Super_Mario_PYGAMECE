from __future__ import annotations

import unittest

from super_mario_pygamece.collision import TileCollider
from super_mario_pygamece.entities import Body
from super_mario_pygamece.settings import TILE_SIZE

import pygame


class TileColliderTests(unittest.TestCase):
    def test_nearby_ignores_far_tiles(self) -> None:
        near = pygame.Rect(0, TILE_SIZE, TILE_SIZE, TILE_SIZE)
        far = pygame.Rect(40 * TILE_SIZE, TILE_SIZE, TILE_SIZE, TILE_SIZE)
        collider = TileCollider((near, far))

        self.assertEqual(collider.nearby(pygame.Rect(0, 0, TILE_SIZE, TILE_SIZE)), (near,))

    def test_move_and_collide_lands_on_ground(self) -> None:
        ground = pygame.Rect(0, TILE_SIZE * 2, TILE_SIZE, TILE_SIZE)
        body = Body(
            pos=pygame.Vector2(0, TILE_SIZE),
            size=pygame.Vector2(TILE_SIZE, TILE_SIZE),
            velocity=pygame.Vector2(0, TILE_SIZE * 8),
        )

        TileCollider((ground,)).move_and_collide(body, 1 / 8)

        self.assertEqual(body.rect.bottom, ground.top)
        self.assertEqual(body.velocity.y, 0)
        self.assertTrue(body.on_ground)


if __name__ == "__main__":
    unittest.main()
