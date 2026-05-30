"""Drive the world forward without keyboard input to exercise gameplay code paths."""
from __future__ import annotations

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame  # noqa: E402

from super_mario_pygamece.entities import PowerState  # noqa: E402
from super_mario_pygamece.level import load_level  # noqa: E402
from super_mario_pygamece.paths import ProjectPaths  # noqa: E402
from super_mario_pygamece.settings import FIXED_DT, TILE_SIZE  # noqa: E402
from super_mario_pygamece.world import GameWorld, WorldState  # noqa: E402


class FakeKeys:
    def __init__(self, right: bool = True) -> None:
        self.right = right

    def __getitem__(self, key: int) -> bool:
        if key in (pygame.K_RIGHT, pygame.K_d):
            return self.right
        if key == pygame.K_LSHIFT:
            return self.right
        return False


def main() -> int:
    pygame.init()
    paths = ProjectPaths.discover()
    level_arg = sys.argv[1] if len(sys.argv) > 1 else "1-1"
    level = load_level(paths.find_level(level_arg) or paths.default_level_candidates[0])
    world = GameWorld(level)
    world.player.state = PowerState.FIRE  # exercise fireball path
    keys = FakeKeys(right=True)
    print(f"Level={level.meta.name}  start_x={world.player.pos.x:.0f}  lives={world.lives}")
    print(f"Enemies={len(world.enemies)}  walkers={[e.kind for e in world.enemies][:8]}")
    for tick in range(900):
        jump = (tick % 40) == 0
        fire = (tick % 50) == 0
        world.update(keys, jump_pressed=jump, jump_held=jump, jump_released=False, dt=FIXED_DT, fire_pressed=fire)
        events = world.pop_events()
        if events:
            shells = sum(1 for e in world.enemies if e.alive and e.shell_state.value != "walking")
            print(f"t={tick} events={events} state={world.state.value} score={world.score} coins={world.coins} shells={shells}")
        if world.state in (WorldState.COMPLETE, WorldState.DYING, WorldState.TIMEOUT):
            print(f"Final: state={world.state.value} x={world.player.pos.x:.0f} score={world.score}")
            return 0
    print(f"Final: state={world.state.value} x={world.player.pos.x:.0f} score={world.score}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
