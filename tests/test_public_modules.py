from __future__ import annotations

import unittest


class PublicModuleTests(unittest.TestCase):
    def test_requested_conversion_modules_import(self) -> None:
        from super_mario_pygamece import assets, enemy, game, level, main, physics, player, settings

        self.assertIsNotNone(main.main)
        self.assertIsNotNone(game.PygameMario)
        self.assertIsNotNone(player.create_player)
        self.assertIsNotNone(enemy.create_enemy)
        self.assertIsNotNone(enemy.is_enemy_spawn)
        self.assertIsNotNone(level.LevelData)
        self.assertIsNotNone(level.create_collectible)
        self.assertIsNotNone(physics.TileCollider)
        self.assertIsNotNone(assets.SpriteBank)
        self.assertGreater(settings.TILE_SIZE, 0)


if __name__ == "__main__":
    unittest.main()
