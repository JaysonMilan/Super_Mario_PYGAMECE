from __future__ import annotations

import unittest

from super_mario_pygamece.level import (
    EntitySpawn,
    Tile,
    create_collectible,
    generate_template_level,
    goal_rect,
    is_collectible_spawn,
    parse_level,
    tile_rect,
)
from super_mario_pygamece.settings import TILE_SIZE


class LevelLoadingTests(unittest.TestCase):
    def test_generated_template_has_playable_defaults(self) -> None:
        level = generate_template_level()

        self.assertEqual(level.meta.width, 212)
        self.assertEqual(level.meta.height, 15)
        self.assertTrue(level.foreground)
        self.assertTrue(any(entity.type == "PlayerSpawn" for entity in level.entities))
        self.assertTrue(any(entity.type == "Goal" for entity in level.entities))

    def test_parse_level_infers_missing_metadata(self) -> None:
        level = parse_level(
            {
                "foreground": [{"type": "Ground", "sprite": "gnd_red_1", "x": 1, "y": 13}],
                "entities": [{"type": "PlayerSpawn", "x": 3, "y": 13}],
            }
        )

        self.assertGreaterEqual(level.meta.width, 32)
        self.assertEqual(level.foreground[0].sprite, "gnd_red_1")
        self.assertEqual(level.entities[0].type, "PlayerSpawn")

    def test_parse_level_ignores_malformed_lists(self) -> None:
        level = parse_level(
            {
                "level": [],
                "foreground": [{"type": "Ground", "x": 0, "y": 14}, "bad"],
                "background": "bad",
                "entities": [None, {"type": "Coin", "x": 1, "y": 12}],
            }
        )

        self.assertEqual(len(level.foreground), 1)
        self.assertEqual(len(level.background), 0)
        self.assertEqual(level.entities[0].type, "Coin")

    def test_runtime_rect_helpers_use_tile_size(self) -> None:
        tile = Tile(x=2, y=3, type="Ground", sprite="gnd_red_1")
        entity = EntitySpawn(type="Goal", x=5, y=13)

        self.assertEqual(tile_rect(tile).topleft, (2 * TILE_SIZE, 3 * TILE_SIZE))
        self.assertEqual(goal_rect(entity).height, TILE_SIZE * 6)

    def test_collectible_helpers_create_coin_and_mushroom(self) -> None:
        coin = EntitySpawn(type="Coin", x=4, y=10)
        mushroom = EntitySpawn(type="Mushroom", x=5, y=10)
        goomba = EntitySpawn(type="Goomba", x=6, y=10)

        self.assertTrue(is_collectible_spawn(coin))
        self.assertTrue(is_collectible_spawn(mushroom))
        self.assertFalse(is_collectible_spawn(goomba))
        self.assertEqual(create_collectible(coin).sprite, "coin_0")
        self.assertEqual(create_collectible(mushroom).sprite, "mushroom")


if __name__ == "__main__":
    unittest.main()
