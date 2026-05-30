from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pygame


SPRITE_ALIASES = {
    "coin": "coin_0",
    "goomba": "goombas_0",
    "small_mario": "mario_st",
    "small_mario_stand": "mario_st",
    "small_mario_jump": "mario_jump",
    "small_mario_walk0": "mario_move0",
    "small_mario_walk1": "mario_move1",
    "small_mario_walk2": "mario_move2",
    "question_block": "blockq_0",
    "used_block": "blockq_used",
    "ground": "gnd_red_1",
    "flag": "end0_flag",
}


class SpriteBank:
    def __init__(self, metadata_path: Path, atlas_dir: Path, tile_size: int) -> None:
        self._atlas_dir = atlas_dir
        self._tile_size = tile_size
        self._atlases: dict[str, pygame.Surface] = {}
        self._sprites: dict[str, tuple[str, pygame.Rect]] = {}
        self._scaled_cache: dict[tuple[str, int, int], pygame.Surface] = {}
        self._missing: set[str] = set()
        self._load_metadata(metadata_path)

    def get(self, name: str, size: tuple[int, int] | None = None) -> pygame.Surface:
        sprite_name = self._resolve_name(name)
        if sprite_name not in self._sprites:
            self._missing.add(name)
            return self.placeholder(size or (self._tile_size, self._tile_size))

        width, height = size or (self._tile_size, self._tile_size)
        cache_key = (sprite_name, width, height)
        if cache_key in self._scaled_cache:
            return self._scaled_cache[cache_key]

        atlas_name, rect = self._sprites[sprite_name]
        sprite = self._atlases[atlas_name].subsurface(rect).copy()
        scaled = pygame.transform.scale(sprite, (width, height))
        self._scaled_cache[cache_key] = scaled
        return scaled

    def missing_sprites(self) -> tuple[str, ...]:
        return tuple(sorted(self._missing))

    def placeholder(self, size: tuple[int, int]) -> pygame.Surface:
        surface = pygame.Surface(size, pygame.SRCALPHA)
        surface.fill((230, 75, 75, 255))
        pygame.draw.rect(surface, (30, 30, 30), surface.get_rect(), 1)
        return surface

    def _load_metadata(self, metadata_path: Path) -> None:
        with metadata_path.open("r", encoding="utf-8") as file:
            metadata: dict[str, Any] = json.load(file)

        for atlas_name, atlas_data in metadata.get("atlases", {}).items():
            texture_path = self._atlas_dir / str(atlas_data["texture"])
            if not texture_path.exists():
                continue

            self._atlases[atlas_name] = pygame.image.load(texture_path).convert_alpha()
            for sprite_name, sprite_data in atlas_data.get("sprites", {}).items():
                self._sprites[sprite_name] = (
                    atlas_name,
                    pygame.Rect(
                        int(sprite_data["x"]),
                        int(sprite_data["y"]),
                        int(sprite_data["w"]),
                        int(sprite_data["h"]),
                    ),
                )

    def _resolve_name(self, name: str) -> str:
        if name in self._sprites:
            return name
        alias = SPRITE_ALIASES.get(name)
        if alias is not None:
            return alias
        return name


class AudioManager:
    _EVENT_SOUNDS = {
        "jump": "jump.wav",
        "jumpbig": "jumpbig.wav",
        "coin": "coin.wav",
        "powerup": "mushroomeat.wav",
        "mushroomappear": "mushroomappear.wav",
        "rainboom": "rainboom.wav",
        "bridgebreak": "bridgebreak.wav",
        "bowserfall": "bowserfall.wav",
        "bulletbill": "bulletbill.wav",
        "swim": "swim.wav",
        "stomp": "stomp.wav",
        "death": "death.wav",
        "complete": "levelend.wav",
        "blockhit": "blockhit.wav",
        "blockbreak": "blockbreak.wav",
        "fireball": "fireball.wav",
        "kick": "stomp.wav",
        "shrink": "shrink.wav",
        "oneup": "oneup.wav",
        "lowtime": "lowtime.wav",
        "pause": "pause.wav",
        "gameover": "gameover.wav",
        "pipe": "pipe.wav",
    }

    def __init__(self, sounds_dir: Path, enabled: bool = True) -> None:
        self._enabled = False
        self._sounds: dict[str, pygame.mixer.Sound] = {}
        if not enabled:
            return

        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            self._enabled = True
        except pygame.error:
            return

        for event_name, filename in self._EVENT_SOUNDS.items():
            path = sounds_dir / filename
            if not path.exists():
                continue
            try:
                self._sounds[event_name] = pygame.mixer.Sound(path)
            except pygame.error:
                continue

    def play_events(self, events: tuple[str, ...]) -> None:
        if not self._enabled:
            return
        for event_name in events:
            sound = self._sounds.get(event_name)
            if sound is not None:
                sound.play()


__all__ = ["AudioManager", "SPRITE_ALIASES", "SpriteBank"]
