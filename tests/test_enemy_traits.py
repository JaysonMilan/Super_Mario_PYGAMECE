from __future__ import annotations

import unittest

import pygame

from super_mario_pygamece.entities import PowerState, ShellState
from super_mario_pygamece.level import EntitySpawn, LevelData, LevelMeta, Tile
from super_mario_pygamece.settings import (
    SHELL_KICK_SPEED,
    SHELL_WAKE_TIME,
    TILE_SIZE,
)
from super_mario_pygamece.world import GameWorld, WorldState


class _NoKeys:
    def __getitem__(self, _key: int) -> bool:
        return False


def _no_keys() -> _NoKeys:
    return _NoKeys()


def _level(*entities: EntitySpawn) -> LevelData:
    return LevelData(
        meta=LevelMeta(name="Test", width=64, height=15),
        foreground=tuple(Tile(x=x, y=14, type="Ground", sprite="gnd_red_1") for x in range(64)),
        background=(),
        entities=(EntitySpawn(type="PlayerSpawn", x=3, y=13), *entities),
    )


class EnemyTraitTests(unittest.TestCase):
    def test_stomping_koopa_creates_still_shell(self) -> None:
        world = GameWorld(_level(EntitySpawn(type="GreenKoopa", x=10, y=13)))
        koopa = world.enemies[0]
        self.assertTrue(koopa.gives_shell)
        # Place player landing on top with a small overlap.
        world.player.pos.x = koopa.body.pos.x
        world.player.pos.y = koopa.body.pos.y - world.player.size.y + 2
        world.player.velocity.y = 200.0

        world.update(_no_keys(), jump_pressed=False, jump_held=False, jump_released=False, dt=0.0)

        self.assertEqual(koopa.shell_state, ShellState.SHELL_STILL)
        self.assertGreaterEqual(koopa.shell_wake_timer, SHELL_WAKE_TIME - 0.01)
        self.assertEqual(world.player.velocity.y, -19.0 * TILE_SIZE)

    def test_kicking_a_still_shell_sends_it_flying(self) -> None:
        world = GameWorld(_level(EntitySpawn(type="GreenKoopa", x=10, y=13)))
        koopa = world.enemies[0]
        # Pre-stomp: convert to still shell directly via helper.
        world._convert_to_shell(koopa)
        # Player overlaps the shell from the left.
        world.player.pos.x = koopa.body.pos.x - world.player.size.x + 4
        world.player.pos.y = koopa.body.pos.y
        world.player.velocity.y = 0

        world.update(_no_keys(), jump_pressed=False, jump_held=False, jump_released=False, dt=0.0)

        self.assertEqual(koopa.shell_state, ShellState.SHELL_KICKED)
        self.assertGreater(koopa.body.velocity.x, 0)
        self.assertAlmostEqual(abs(koopa.body.velocity.x), SHELL_KICK_SPEED, delta=1)

    def test_kicked_shell_kills_other_enemy(self) -> None:
        world = GameWorld(
            _level(
                EntitySpawn(type="GreenKoopa", x=10, y=13),
                EntitySpawn(type="Goomba", x=12, y=13),
            )
        )
        koopa = next(enemy for enemy in world.enemies if enemy.kind == "GreenKoopa")
        goomba = next(enemy for enemy in world.enemies if enemy.kind == "Goomba")
        # Put the kicked shell right against the goomba.
        koopa.shell_state = ShellState.SHELL_KICKED
        koopa.body.velocity.x = SHELL_KICK_SPEED
        koopa.body.facing = 1
        koopa.body.pos = pygame.Vector2(goomba.body.pos.x - 4, goomba.body.pos.y)
        prior_score = world.score

        world.update(_no_keys(), jump_pressed=False, jump_held=False, jump_released=False, dt=1 / 60)

        self.assertFalse(goomba.alive)
        self.assertGreater(world.score, prior_score)

    def test_spiny_is_not_stompable(self) -> None:
        world = GameWorld(_level(EntitySpawn(type="Spiny", x=10, y=13)))
        spiny = world.enemies[0]
        self.assertFalse(spiny.stompable)
        world.player.state = PowerState.SUPER  # so we survive the first damage tick
        world.player.size = pygame.Vector2(28, 60)
        world.player.pos.x = spiny.body.pos.x
        world.player.pos.y = spiny.body.pos.y - world.player.size.y + 4
        world.player.velocity.y = 200.0

        world.update(_no_keys(), jump_pressed=False, jump_held=False, jump_released=False, dt=0.0)

        self.assertTrue(spiny.alive)  # spiny survives the stomp
        self.assertTrue(world.player.is_shrinking)
        self.assertEqual(world.player.pending_state, PowerState.SMALL)

        for _ in range(60):
            world.update(_no_keys(), jump_pressed=False, jump_held=False, jump_released=False, dt=1 / 60)
            if not world.player.is_shrinking:
                break

        self.assertEqual(world.player.state, PowerState.SMALL)

    def test_buzzy_beetle_is_fire_immune(self) -> None:
        world = GameWorld(_level(EntitySpawn(type="BuzzyBeetle", x=10, y=13)))
        buzzy = world.enemies[0]
        self.assertTrue(buzzy.fire_immune)
        world.player.state = PowerState.FIRE
        world.player.fire_cooldown = 0.0
        world.player.pos.x = buzzy.body.pos.x - 60
        world.player.pos.y = buzzy.body.pos.y
        world.player.facing = 1

        world.update(_no_keys(), jump_pressed=False, jump_held=False, jump_released=False, dt=0.0, fire_pressed=True)
        for _ in range(20):
            world.update(_no_keys(), jump_pressed=False, jump_held=False, jump_released=False, dt=1 / 60)

        self.assertTrue(buzzy.alive)

    def test_off_screen_enemy_is_culled(self) -> None:
        world = GameWorld(_level(EntitySpawn(type="Goomba", x=10, y=13)))
        goomba = world.enemies[0]
        # Pretend the camera moved far past the goomba.
        world.camera_x = goomba.body.pos.x + 1000

        world.update(_no_keys(), jump_pressed=False, jump_held=False, jump_released=False, dt=1 / 60)

        self.assertFalse(goomba.alive)

    def test_red_koopa_is_ledge_aware(self) -> None:
        from super_mario_pygamece.enemy import ENEMY_TRAITS, create_enemy

        red = create_enemy(EntitySpawn(type="RedKoopa", x=10, y=13))
        green = create_enemy(EntitySpawn(type="GreenKoopa", x=10, y=13))
        self.assertTrue(red.ledge_aware)
        self.assertFalse(green.ledge_aware)
        # Sanity: traits dict drives the difference.
        self.assertIn("ledge_aware", ENEMY_TRAITS["RedKoopa"])


if __name__ == "__main__":
    unittest.main()
