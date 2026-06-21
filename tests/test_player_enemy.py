from __future__ import annotations

import unittest

from super_mario_pygamece.enemy import create_enemy, is_enemy_spawn
from super_mario_pygamece.level import EntitySpawn
from super_mario_pygamece.player import SMALL_SIZE, create_player
from super_mario_pygamece.settings import ENEMY_SPEED, TILE_SIZE


class PlayerEnemyTests(unittest.TestCase):
    def test_create_player_places_feet_near_spawn_tile(self) -> None:
        player = create_player(3, 13)

        self.assertEqual(player.pos.x, 3 * TILE_SIZE)
        self.assertEqual(player.facing, 1)
        self.assertEqual(player.size.y, SMALL_SIZE.y)

    def test_create_enemy_sets_walking_defaults(self) -> None:
        spawn = EntitySpawn(type="Goomba", x=8, y=13)
        enemy = create_enemy(spawn)

        self.assertTrue(is_enemy_spawn(spawn))
        self.assertEqual(enemy.body.velocity.x, -ENEMY_SPEED)
        self.assertEqual(enemy.body.facing, -1)
        self.assertEqual(enemy.frames, ("goombas_0", "goombas_1"))

    def test_is_enemy_spawn_rejects_non_enemy_entities(self) -> None:
        self.assertFalse(is_enemy_spawn(EntitySpawn(type="Coin", x=1, y=1)))


if __name__ == "__main__":
    unittest.main()
