from __future__ import annotations

import json
import os
import shutil
import unittest
import warnings
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
warnings.filterwarnings("ignore", message="pkg_resources is deprecated.*", category=UserWarning)

import pygame

from super_mario_pygamece.atlas import SpriteBank


class SpriteBankTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls) -> None:
        pygame.quit()

    def test_alias_resolves_to_real_sprite(self) -> None:
        root = _fixture_root("atlas_alias")
        self.addCleanup(shutil.rmtree, root.parent, True)
        atlas_path = root / "atlas.png"
        metadata_path = root / "atlases.json"

        surface = pygame.Surface((4, 4), pygame.SRCALPHA)
        surface.fill((10, 20, 30, 255))
        pygame.image.save(surface, atlas_path)
        metadata_path.write_text(
            json.dumps(
                {
                    "atlases": {
                        "items_atlas": {
                            "texture": "atlas.png",
                            "sprites": {"coin_0": {"x": 0, "y": 0, "w": 4, "h": 4}},
                        }
                    }
                }
            ),
            encoding="utf-8",
        )

        sprites = SpriteBank(metadata_path, root, tile_size=8)
        sprite = sprites.get("coin")

        self.assertEqual(sprite.get_size(), (8, 8))
        self.assertEqual(sprites.missing_sprites(), ())

    def test_missing_sprite_is_recorded(self) -> None:
        root = _fixture_root("atlas_missing")
        self.addCleanup(shutil.rmtree, root.parent, True)
        metadata_path = root / "atlases.json"
        metadata_path.write_text('{"atlases": {}}', encoding="utf-8")

        sprites = SpriteBank(metadata_path, root, tile_size=8)
        sprites.get("missing")

        self.assertEqual(sprites.missing_sprites(), ("missing",))


def _fixture_root(name: str) -> Path:
    root = Path.cwd() / ".test_tmp" / name
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True)
    return root


if __name__ == "__main__":
    unittest.main()
