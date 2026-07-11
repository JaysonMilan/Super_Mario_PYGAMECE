from __future__ import annotations

import unittest

import pygame

from super_mario_pygamece.entities import PipeState
from super_mario_pygamece.entities import PowerState
from super_mario_pygamece.level import EntitySpawn, LevelData, LevelMeta, Tile
from super_mario_pygamece.level import WarpDefinition
from super_mario_pygamece.settings import DEATH_ANIM_DURATION, JUMP_SPEED, RESPAWN_DELAY, TILE_SIZE
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

    def test_hidden_block_reveals_when_hit_from_below(self) -> None:
        hidden = Tile(x=3, y=11, type="HiddenBlock", sprite="blockq", item_content=0)
        world = GameWorld(
            LevelData(
                meta=LevelMeta(name="Test", width=32, height=15),
                foreground=(
                    *(Tile(x=x, y=14, type="Ground", sprite="gnd_red_1") for x in range(32)),
                    hidden,
                ),
                background=(),
                entities=(EntitySpawn(type="PlayerSpawn", x=3, y=13),),
            )
        )
        key = (hidden.x * TILE_SIZE, hidden.y * TILE_SIZE)
        self.assertIn(key, world.hidden_block_contents)
        self.assertNotIn(key, world.solid_tile_lookup)

        world.player.pos.x = hidden.x * TILE_SIZE
        world.player.pos.y = (hidden.y + 1) * TILE_SIZE + 2
        world.player.velocity.y = -200.0
        world.update(keys=_no_keys(), jump_pressed=False, jump_held=False, jump_released=False, dt=1 / 60)

        self.assertNotIn(key, world.hidden_block_contents)
        self.assertEqual(world.tile_types[key], "UsedBlock")
        self.assertIn(key, world.solid_tile_lookup)
        self.assertEqual(world.coins, 1)

    def test_multi_coin_block_exhausts_on_final_hit(self) -> None:
        block = Tile(x=3, y=11, type="QuestionBlock", sprite="blockq_0", item_content=0, hits_remaining=3)
        world = GameWorld(
            LevelData(
                meta=LevelMeta(name="Test", width=32, height=15),
                foreground=(
                    *(Tile(x=x, y=14, type="Ground", sprite="gnd_red_1") for x in range(32)),
                    block,
                ),
                background=(),
                entities=(EntitySpawn(type="PlayerSpawn", x=3, y=13),),
            )
        )
        rect = pygame.Rect(block.x * TILE_SIZE, block.y * TILE_SIZE, TILE_SIZE, TILE_SIZE)
        key = rect.topleft

        world._handle_block_hit(rect)
        self.assertEqual(world.coins, 1)
        self.assertEqual(world.tile_types[key], "QuestionBlock")

        world._handle_block_hit(rect)
        self.assertEqual(world.coins, 2)
        self.assertEqual(world.tile_types[key], "QuestionBlock")

        world._handle_block_hit(rect)
        self.assertEqual(world.coins, 3)
        self.assertEqual(world.tile_types[key], "UsedBlock")

    def test_big_mario_breaks_brick_and_removes_solid_tile(self) -> None:
        brick = Tile(x=3, y=11, type="Brick", sprite="brick1")
        world = GameWorld(
            LevelData(
                meta=LevelMeta(name="Test", width=32, height=15),
                foreground=(
                    *(Tile(x=x, y=14, type="Ground", sprite="gnd_red_1") for x in range(32)),
                    brick,
                ),
                background=(),
                entities=(EntitySpawn(type="PlayerSpawn", x=3, y=13),),
            )
        )
        key = (brick.x * TILE_SIZE, brick.y * TILE_SIZE)
        rect = pygame.Rect(key[0], key[1], TILE_SIZE, TILE_SIZE)
        world.player.state = PowerState.SUPER

        world._handle_block_hit(rect)

        self.assertNotIn(key, world.tile_types)
        self.assertNotIn(key, world.tile_sprites)
        self.assertNotIn(key, world.solid_tile_lookup)
        self.assertNotIn(rect, world.solid_tiles)
        self.assertEqual(world.score, 50)
        self.assertIn("blockbreak", world.events)

    def test_down_pipe_starts_same_level_warp(self) -> None:
        level = LevelData(
            meta=LevelMeta(name="Test", width=32, height=15),
            foreground=(
                *(Tile(x=x, y=14, type="Ground", sprite="gnd_red_1") for x in range(32)),
                Tile(x=5, y=13, type="Pipe", sprite="pipe_left_top"),
                Tile(x=6, y=13, type="Pipe", sprite="pipe_right_top"),
            ),
            background=(),
            entities=(EntitySpawn(type="PlayerSpawn", x=5, y=13),),
            warps=(
                WarpDefinition(
                    entry_tile_x=5,
                    entry_tile_y=13,
                    dest_level="",
                    dest_world_x=18,
                    dest_world_y=12,
                    exit_facing_right=True,
                ),
            ),
        )
        world = GameWorld(level)
        world.player.pos.x = 5 * TILE_SIZE
        world.player.pos.y = 12 * TILE_SIZE
        world.player.on_ground = True

        world.update(keys=_keys(pygame.K_DOWN), jump_pressed=False, jump_held=False, jump_released=False, dt=0)

        self.assertEqual(world.player.pipe_state, PipeState.ENTERING_DOWN)
        self.assertEqual(world.player.pipe_dest_x, 18 * TILE_SIZE)
        self.assertEqual(world.player.pipe_dest_y, 12 * TILE_SIZE)

        world.update(keys=_no_keys(), jump_pressed=False, jump_held=False, jump_released=False, dt=1.0)

        self.assertEqual(world.player.pipe_state, PipeState.EXITING_UP)
        self.assertEqual(world.player.pos.x, 18 * TILE_SIZE)
        self.assertEqual(world.player.pos.y, 12 * TILE_SIZE)

    def test_spring_locks_then_launches_player(self) -> None:
        world = GameWorld(
            _level_with_entities(EntitySpawn(type="Spring", x=5, y=13))
        )
        spring = world.springs[0]
        world.player.pos.x = spring.rect.x
        world.player.pos.y = spring.rect.top - world.player.size.y
        world.player.velocity.y = 0.0
        world.player.on_ground = True

        world.update(keys=_no_keys(), jump_pressed=False, jump_held=False, jump_released=False, dt=0)
        self.assertEqual(spring.anim_phase, 1)
        self.assertEqual(world.player.velocity.y, 0.0)

        for _ in range(3):
            world.update(keys=_no_keys(), jump_pressed=False, jump_held=False, jump_released=False, dt=4 / 60)

        self.assertEqual(spring.anim_phase, 0)
        self.assertEqual(world.player.velocity.y, -26.0 * TILE_SIZE)
        self.assertFalse(world.player.on_ground)

    def test_vine_climb_locks_player_to_vine(self) -> None:
        world = GameWorld(_level_with_entities(EntitySpawn(type="Vine", x=5, y=10)))
        vine = world.vines[0]
        world.player.pos.x = vine.rect.centerx - world.player.size.x * 0.5
        world.player.pos.y = vine.rect.centery - world.player.size.y * 0.5

        world.update(keys=_keys(pygame.K_UP), jump_pressed=False, jump_held=False, jump_released=False, dt=0)
        self.assertIs(world.active_vine, vine)

        start_y = world.player.pos.y
        world.update(keys=_keys(pygame.K_UP), jump_pressed=False, jump_held=False, jump_released=False, dt=0.25)

        self.assertLess(world.player.pos.y, start_y)
        self.assertEqual(world.player.velocity.y, 0.0)
        self.assertAlmostEqual(world.player.rect.centerx, vine.rect.centerx, delta=1)

    def test_vine_top_can_warp_within_level(self) -> None:
        world = GameWorld(
            _level_with_entities(
                EntitySpawn(type="Vine", x=5, y=10, dest_world_x=18, dest_world_y=12)
            )
        )
        vine = world.vines[0]
        world.active_vine = vine
        world.player.pos.x = vine.rect.centerx - world.player.size.x * 0.5
        world.player.pos.y = vine.rect.top - world.player.size.y * 0.5

        world.update(keys=_keys(pygame.K_UP), jump_pressed=False, jump_held=False, jump_released=False, dt=0.25)

        self.assertIsNone(world.active_vine)
        self.assertEqual(world.player.pos.x, 18 * TILE_SIZE)
        self.assertEqual(world.player.pos.y, 12 * TILE_SIZE)

    def test_goal_completion_runs_flagpole_sequence(self) -> None:
        world = GameWorld(_level_with_entities(EntitySpawn(type="Goal", x=4, y=13)))
        world.player.pos.x = 4 * TILE_SIZE
        world.player.pos.y = 8 * TILE_SIZE
        world.time_remaining = 0.5

        # First tick: enter the flagpole slide.
        world.update(keys=_no_keys(), jump_pressed=False, jump_held=False, jump_released=False, dt=1 / 60)
        self.assertEqual(world.state, WorldState.FLAGPOLE)
        self.assertGreaterEqual(world.score, 500)

        # Drive the sequence forward until COMPLETE (~5 seconds is plenty).
        for _ in range(600):
            world.update(keys=_no_keys(), jump_pressed=False, jump_held=False, jump_released=False, dt=1 / 60)
            if world.state is WorldState.COMPLETE:
                break

        self.assertEqual(world.state, WorldState.COMPLETE)
        self.assertGreaterEqual(world.score, 500)

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
            dt=DEATH_ANIM_DURATION + RESPAWN_DELAY + 0.05,
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
            dt=DEATH_ANIM_DURATION + RESPAWN_DELAY + 0.05,
        )

        self.assertEqual(world.state, WorldState.GAMEOVER)
        self.assertGreater(world.gameover_timer, 0)

    def test_jump_release_cuts_upward_velocity(self) -> None:
        world = GameWorld(_level_with_entities())
        world.player.on_ground = True

        world.update(keys=_no_keys(), jump_pressed=True, jump_held=True, jump_released=False, dt=0)
        full_jump_velocity = world.player.velocity.y
        world.update(keys=_no_keys(), jump_pressed=False, jump_held=False, jump_released=True, dt=1 / 60)

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

    def test_grounded_player_resets_stomp_combo_immediately(self) -> None:
        world = GameWorld(_level_with_entities())
        world.stomp_combo = 4
        world.player.on_ground = True

        world.update(keys=_no_keys(), jump_pressed=False, jump_held=False, jump_released=False, dt=0)

        self.assertEqual(world.stomp_combo, 1)

    def test_combo_past_table_awards_capped_oneup(self) -> None:
        world = GameWorld(_level_with_entities())
        world.stomp_combo = 11
        world.lives = 128

        world._award_combo_score(0, 0)

        self.assertEqual(world.lives, 128)
        self.assertEqual(world.popups[-1].text, "1UP")
        self.assertIn("oneup", world.events)

    def test_plain_solid_ceiling_plays_blockbump(self) -> None:
        ceiling = Tile(x=3, y=11, type="Ground", sprite="gnd_red_1")
        world = GameWorld(
            LevelData(
                meta=LevelMeta(name="Test", width=32, height=15),
                foreground=(ceiling,),
                background=(),
                entities=(EntitySpawn(type="PlayerSpawn", x=3, y=13),),
            )
        )

        world._handle_block_hit(pygame.Rect(3 * TILE_SIZE, 11 * TILE_SIZE, TILE_SIZE, TILE_SIZE))

        self.assertIn("blockbump", world.events)

    def test_timer_does_not_drain_while_dying(self) -> None:
        world = GameWorld(_level_with_entities())
        world.state = WorldState.DYING
        world.respawn_timer = 1.0
        world.time_remaining = 123.0

        world.update(keys=_no_keys(), jump_pressed=False, jump_held=False, jump_released=False, dt=0.5)

        self.assertEqual(world.time_remaining, 123.0)


class _NoKeys:
    def __getitem__(self, _key: int) -> bool:
        return False


class _Keys:
    def __init__(self, *pressed: int) -> None:
        self._pressed = set(pressed)

    def __getitem__(self, key: int) -> bool:
        return key in self._pressed


def _no_keys() -> _NoKeys:
    return _NoKeys()


def _keys(*pressed: int) -> _Keys:
    return _Keys(*pressed)


if __name__ == "__main__":
    unittest.main()
