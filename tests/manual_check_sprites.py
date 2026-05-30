"""Quick check that referenced sprites resolve in the atlas metadata."""
from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame  # noqa: E402

from super_mario_pygamece.assets import SpriteBank  # noqa: E402
from super_mario_pygamece.paths import ProjectPaths  # noqa: E402
from super_mario_pygamece.settings import TILE_SIZE  # noqa: E402


SPRITES_TO_CHECK = [
    # Player states
    "mario_st", "mario_jump", "mario_move0", "mario_move1", "mario_move2",
    "mario1_st", "mario1_jump", "mario1_move0", "mario1_move1", "mario1_move2",
    "mario2_st", "mario2_jump", "mario2_move0", "mario2_move1", "mario2_move2",
    # Enemies
    "goombas_0", "goombas_1", "koopa_0", "koopa_1", "beetle_0", "beetle_1",
    # Items
    "coin_0", "coin_1", "coin_2", "mushroom", "mushroom_1up",
    "flower0", "flower1", "flower2", "flower3", "star_0", "star_1", "star_2", "star_3",
    # Effects
    "fireball_0", "fireball_1", "fireball_2", "fireball_3", "fire_0", "fire_1",
    "coin_an0",
    # Tiles
    "blockq_0", "blockq_used", "brick1", "brickred", "gnd_red_1", "end0_flag",
]


def main() -> int:
    pygame.init()
    pygame.display.set_mode((1, 1))
    paths = ProjectPaths.discover()
    bank = SpriteBank(paths.atlas_metadata, paths.atlas_dir, TILE_SIZE)
    print(f"Atlas dir: {paths.atlas_dir}")
    missing = []
    for name in SPRITES_TO_CHECK:
        bank.get(name)
        if name in bank.missing_sprites():
            missing.append(name)
    if missing:
        print("MISSING:", missing)
        return 1
    print(f"All {len(SPRITES_TO_CHECK)} sprites resolved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
