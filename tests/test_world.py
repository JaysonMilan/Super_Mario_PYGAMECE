from __future__ import annotations

import unittest

from super_mario_pygamece.level import EntitySpawn, LevelData, LevelMeta, Tile
from super_mario_pygamece.settings import JUMP_SPEED, RESPAWN_DELAY, TILE_SIZE
from super_mario_pygamece.world import GameWorld, WorldState


def _level_with_entities(*entities: EntitySpawn) -> LevelData:
    return LevelData(
        meta=LevelMeta(name="Test", width=32, height=15),
        foreground=tuple(Tile(x=x, y=14, type="Ground", sprite="gnd_red_1") for x in range(32)),
        background=(),
        entities=(EntitySpawn(type="PlayerSpawn", x=3, y=13), *entities),
    )


class GameWorldTests(unittest.TestCase):
    def test_restart_recreates_collectibles_and_enemies(self) -> None:
        world = GameWorld(
            _level_with_entities(
                EntitySpawn(type="Coin", x=3, y=13),
                EntitySpawn(type="Goomba", x=8, y=13),
            )
        )
        world.collectibles.clear()
        world.enemies[0].alive = False

        world.restart()

        self.assertEqual(len(world.collectibles), 1)
        self.assertTrue(world.enemies[0].alive)

    def test_collecting_coin_increases_score_and_removes_coin(self) -> None:
        world = GameWorld(_level_with_entities(EntitySpawn(type="Coin", x=3, y=13)))
        coin = world.collectibles[0]
        world.player.pos.x = coin.rect.x
        world.player.pos.y = coin.rect.y

        world.update(keys=_no_keys(), jump_pressed=False, jump_held=False, jump_released=False, dt=0)

        self.assertEqual(world.score, 200)
        self.assertEqual(world.coins, 1)
        self.assertEqual(world.collectibles, [])

    def test_goal_completion_runs_flagpole_sequence(self) -> None:
        world = GameWorld(_level_with_entities(EntitySpawn(type="Goal", x=4, y=13)))
        world.player.pos.x = 4 * TILE_SIZE
        world.player.pos.y = 8 * TILE_SIZE
        world.time_remaining = 0.5

        # First tick: enter the flagpole slide.
        world.update(keys=_no_keys(), jump_pressed=False, jump_held=False, jump_released=False, dt=1 / 60)
        self.assertEqual(world.state, WorldState.FLAGPOLE)
        self.assertGreaterEqual(world.score, 5000)  # top-of-pole tier

        # Drive the sequence forward until COMPLETE (~5 seconds is plenty).
        for _ in range(600):
            world.update(keys=_no_keys(), jump_pressed=False, jump_held=False, jump_released=False, dt=1 / 60)
            if world.state is WorldState.COMPLETE:
                break

        self.assertEqual(world.state, WorldState.COMPLETE)
        self.assertGreaterEqual(world.score, 6000)  # flag tier + base completion

    def test_death_consumes_life_and_respawns_after_delay(self) -> None:
        world = GameWorld(_level_with_entities())
        world.player.pos.y = world.level.meta.height * TILE_SIZE + 300

        world.update(keys=_no_keys(), jump_pressed=False, jump_held=False, jump_released=False, dt=0)

        self.assertEqual(world.state, WorldState.DYING)
        self.assertEqual(world.lives, 2)

        world.update(
            keys=_no_keys(),
            jump_pressed=False,
            jump_held=False,
            jump_released=False,
            dt=RESPAWN_DELAY + 0.05,
        )

        self.assertEqual(world.state, WorldState.PLAYING)
        self.assertEqual(world.lives, 2)

    def test_dying_with_no_lives_enters_gameover(self) -> None:
        world = GameWorld(_level_with_entities())
        world.lives = 1
        world.player.pos.y = world.level.meta.height * TILE_SIZE + 300

        world.update(keys=_no_keys(), jump_pressed=False, jump_held=False, jump_released=False, dt=0)
        self.assertEqual(world.state, WorldState.DYING)

        world.update(
            keys=_no_keys(),
            jump_pressed=False,
            jump_held=False,
            jump_released=False,
            dt=RESPAWN_DELAY + 0.05,
        )

        self.assertEqual(world.state, WorldState.GAMEOVER)
        self.assertGreater(world.gameover_timer, 0)

    def test_jump_release_cuts_upward_velocity(self) -> None:
        world = GameWorld(_level_with_entities())
        world.player.on_ground = True

        world.update(keys=_no_keys(), jump_pressed=True, jump_held=True, jump_released=False, dt=0)
        full_jump_velocity = world.player.velocity.y
        world.update(keys=_no_keys(), jump_pressed=False, jump_held=False, jump_released=True, dt=0)

        self.assertEqual(full_jump_velocity, -JUMP_SPEED)
        self.assertGreater(world.player.velocity.y, -JUMP_SPEED)
        self.assertLess(world.player.velocity.y, 0)

    def test_coyote_time_allows_late_jump(self) -> None:
        world = GameWorld(_level_with_entities())
        world.player.on_ground = False
        world.coyote_timer = 0.05

        world.update(keys=_no_keys(), jump_pressed=True, jump_held=True, jump_released=False, dt=0)

        self.assertEqual(world.player.velocity.y, -JUMP_SPEED)

    def test_jump_buffer_fires_when_landing(self) -> None:
        world = GameWorld(_level_with_entities())
        world.player.on_ground = False
        world.coyote_timer = 0
        world.player.pos.y = 14 * TILE_SIZE - world.player.size.y - 2
        world.player.velocity.y = 120

        world.update(keys=_no_keys(), jump_pressed=True, jump_held=True, jump_released=False, dt=1 / 60)
        world.update(keys=_no_keys(), jump_pressed=False, jump_held=True, jump_released=False, dt=1 / 60)

        self.assertLess(world.player.velocity.y, 0)


class _NoKeys:
    def __getitem__(self, _key: int) -> bool:
        return False


def _no_keys() -> _NoKeys:
    return _NoKeys()


if __name__ == "__main__":
    unittest.main()
