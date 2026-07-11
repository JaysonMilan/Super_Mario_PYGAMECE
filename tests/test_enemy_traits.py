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

    def test_dormant_enemy_stays_inert_until_player_is_near(self) -> None:
        world = GameWorld(_level(EntitySpawn(type="Goomba", x=20, y=13)))
        goomba = world.enemies[0]
        start = pygame.Vector2(goomba.body.pos)

        world.update(_no_keys(), jump_pressed=False, jump_held=False, jump_released=False, dt=1 / 60)

        self.assertFalse(goomba.level_spawn_active)
        self.assertEqual(goomba.body.pos, start)

        world.player.pos.x = 15 * TILE_SIZE
        world.update(_no_keys(), jump_pressed=False, jump_held=False, jump_released=False, dt=0.0)
        self.assertTrue(goomba.level_spawn_active)

    def test_shell_stomp_reverses_and_awards_after_visible_bounce(self) -> None:
        world = GameWorld(_level(EntitySpawn(type="GreenKoopa", x=10, y=13)))
        shell = world.enemies[0]
        shell.level_spawn_active = True
        world._convert_to_shell(shell)
        shell.shell_state = ShellState.SHELL_KICKED
        shell.body.velocity.x = SHELL_KICK_SPEED
        shell.body.facing = 1
        shell.terrain_rebound_armed = True
        world.player.pos.x = shell.body.pos.x
        world.player.pos.y = shell.body.pos.y - world.player.size.y + 2
        world.player.velocity.y = 200.0

        world._handle_entity_collisions()

        self.assertEqual(shell.shell_state, ShellState.SHELL_KICKED)
        self.assertLess(shell.body.velocity.x, 0)
        self.assertIsNotNone(world.pending_shell_stomp)

        world.player.on_ground = False
        world.player.pos.y -= 16
        world.player.velocity.y = -20
        world._process_pending_shell_stomp_award()

        self.assertEqual(world.score, 100)
        self.assertEqual(shell.stomp_chain, 2)

    def test_shell_stomp_award_times_out_without_a_visible_bounce(self) -> None:
        world = GameWorld(_level(EntitySpawn(type="GreenKoopa", x=10, y=13)))
        shell = world.enemies[0]
        shell.terrain_rebound_armed = True
        world._begin_pending_shell_stomp_award(shell)
        world.player.on_ground = False
        world.player.velocity.y = -20

        for _ in range(21):
            world._process_pending_shell_stomp_award()

        self.assertIsNone(world.pending_shell_stomp)
        self.assertEqual(world.score, 0)

    def test_kicking_and_waking_shell_reset_stomp_chain(self) -> None:
        world = GameWorld(_level(EntitySpawn(type="GreenKoopa", x=10, y=13)))
        shell = world.enemies[0]
        shell.stomp_chain = 5
        shell.terrain_rebound_armed = True
        world._kick_shell(shell, 1)
        self.assertEqual(shell.stomp_chain, 1)
        self.assertFalse(shell.terrain_rebound_armed)

        shell.stomp_chain = 5
        shell.terrain_rebound_armed = True
        shell.stomp_contact_active = True
        world._wake_shell(shell)
        self.assertEqual(shell.stomp_chain, 1)
        self.assertFalse(shell.terrain_rebound_armed)
        self.assertFalse(shell.stomp_contact_active)

    def test_level_theme_selects_goomba_squash_and_clamped_green_koopa_frames(self) -> None:
        castle = GameWorld(
            LevelData(
                meta=LevelMeta(name="Test", width=32, height=15, level_type="Castle"),
                foreground=(),
                background=(),
                entities=(EntitySpawn(type="PlayerSpawn", x=3, y=13), EntitySpawn(type="Goomba", x=10, y=13)),
            )
        )
        underground = GameWorld(
            LevelData(
                meta=LevelMeta(name="Test", width=32, height=15, level_type="Underground"),
                foreground=(),
                background=(),
                entities=(
                    EntitySpawn(type="PlayerSpawn", x=3, y=13),
                    EntitySpawn(type="GreenKoopa", x=10, y=13),
                ),
            )
        )

        self.assertEqual(castle.enemies[0].stomp_frame, "goombas2_ded")
        self.assertEqual(underground.enemies[0].frames, ("koopa1_0", "koopa1_1"))
        self.assertNotIn("koopa2", underground.enemies[0].frames)


if __name__ == "__main__":
    unittest.main()
