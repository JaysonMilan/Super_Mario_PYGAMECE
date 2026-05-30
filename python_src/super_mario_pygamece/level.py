from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pygame

from .entities import Collectible
from .paths import ProjectPaths
from .settings import TILE_SIZE


# Foreground tile types that should remain solid for the player and enemies.
SOLID_TYPES = {
    "Ground",
    "Brick",
    "BrickFloor",
    "Pipe",
    "PipeBody",
    "PipeTop",
    "QuestionBlock",
    "Question",
    "UsedBlock",
    "MetalBlock",
    "Stone",
    "Castle",
    "Bridge",
    "Hill",
    "Stair",
    "Block",
}

QUESTION_TYPES = {"Question", "QuestionBlock"}
BRICK_TYPES = {"Brick"}

COLLECTIBLE_TYPES = {"Coin", "Mushroom", "FireFlower", "Flower", "Star", "OneUp"}


@dataclass(frozen=True, slots=True)
class LevelMeta:
    name: str
    width: int
    height: int
    time_limit: int = 400


ITEM_CONTENT_BY_ID: dict[int, str] = {
    0: "Coin",
    1: "Mushroom",
    2: "FireFlower",
    3: "Star",
    4: "OneUp",
}


@dataclass(frozen=True, slots=True)
class Tile:
    x: int
    y: int
    type: str
    sprite: str
    item_content: int = 0


@dataclass(frozen=True, slots=True)
class EntitySpawn:
    type: str
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class LevelData:
    meta: LevelMeta
    foreground: tuple[Tile, ...]
    background: tuple[Tile, ...]
    entities: tuple[EntitySpawn, ...]


def find_default_level(paths: ProjectPaths) -> Path | None:
    return next((path for path in paths.default_level_candidates if path.exists()), None)


def load_level(path: Path) -> LevelData:
    # utf-8-sig tolerates the byte-order-mark used by some Windows-saved JSON files.
    with path.open("r", encoding="utf-8-sig") as file:
        raw = json.load(file)
    return parse_level(raw, name_hint=path.stem)


def parse_level(raw: dict[str, Any], name_hint: str | None = None) -> LevelData:
    raw_level = raw.get("level", {})
    if not isinstance(raw_level, dict):
        raw_level = {}
    foreground = tuple(_parse_tile(tile) for tile in _dict_items(raw.get("foreground")))
    background = tuple(_parse_tile(tile) for tile in _dict_items(raw.get("background")))
    entities = tuple(_parse_entity(entity) for entity in _dict_items(raw.get("entities")))

    width = int(raw_level.get("width", _infer_width(foreground, entities)))
    height = int(raw_level.get("height", _infer_height(foreground, background, entities)))

    name = str(raw_level.get("name") or name_hint or "Pygame 1-1")

    return LevelData(
        meta=LevelMeta(
            name=name,
            width=max(width, 32),
            height=max(height, 15),
            time_limit=int(raw_level.get("time_limit", 400)),
        ),
        foreground=foreground,
        background=background,
        entities=entities,
    )


def generate_template_level() -> LevelData:
    width = 212
    height = 15
    foreground_list = [
        Tile(x=x, y=y, type="Ground", sprite="gnd_red_1")
        for y in (13, 14)
        for x in range(width)
    ]
    foreground_list.extend(
        [
            Tile(x=16, y=9, type="QuestionBlock", sprite="blockq_0"),
            Tile(x=20, y=9, type="Brick", sprite="brick1"),
            Tile(x=21, y=9, type="QuestionBlock", sprite="blockq_0"),
            Tile(x=22, y=9, type="Brick", sprite="brick1"),
            Tile(x=23, y=5, type="Brick", sprite="brick1"),
            Tile(x=24, y=5, type="QuestionBlock", sprite="blockq_0"),
            Tile(x=25, y=5, type="Brick", sprite="brick1"),
        ]
    )
    entities = (
        EntitySpawn(type="PlayerSpawn", x=3, y=13),
        EntitySpawn(type="Goomba", x=18, y=13),
        EntitySpawn(type="Goomba", x=24, y=13),
        EntitySpawn(type="Coin", x=19, y=10),
        EntitySpawn(type="Coin", x=20, y=10),
        EntitySpawn(type="Mushroom", x=26, y=12),
        EntitySpawn(type="Goal", x=200, y=13),
    )
    return LevelData(
        meta=LevelMeta(name="Generated 1-1", width=width, height=height),
        foreground=tuple(foreground_list),
        background=(),
        entities=entities,
    )


def tile_rect(tile: Tile) -> pygame.Rect:
    return pygame.Rect(tile.x * TILE_SIZE, tile.y * TILE_SIZE, TILE_SIZE, TILE_SIZE)


def goal_rect(entity: EntitySpawn) -> pygame.Rect:
    return pygame.Rect(round(entity.x * TILE_SIZE), round((entity.y - 5) * TILE_SIZE), TILE_SIZE, TILE_SIZE * 6)


def is_collectible_spawn(entity: EntitySpawn) -> bool:
    return entity.type in COLLECTIBLE_TYPES


def is_solid_tile(tile: Tile) -> bool:
    return tile.type in SOLID_TYPES


def create_collectible(entity: EntitySpawn) -> Collectible:
    sprite = _collectible_sprite(entity.type)
    return Collectible(
        kind=entity.type,
        rect=pygame.Rect(
            round(entity.x * TILE_SIZE),
            round(entity.y * TILE_SIZE - TILE_SIZE),
            TILE_SIZE,
            TILE_SIZE,
        ),
        sprite=sprite,
        velocity=pygame.Vector2(0.0, 0.0),
    )


def _collectible_sprite(kind: str) -> str:
    match kind:
        case "Coin":
            return "coin_0"
        case "Mushroom":
            return "mushroom"
        case "OneUp":
            return "mushroom_1up"
        case "FireFlower" | "Flower":
            return "flower0"
        case "Star":
            return "star_0"
        case _:
            return "coin_0"


def _parse_tile(raw: dict[str, Any]) -> Tile:
    tile_type = str(raw.get("type", "Ground"))
    return Tile(
        x=int(raw.get("x", 0)),
        y=int(raw.get("y", 0)),
        type=tile_type,
        sprite=str(raw.get("sprite") or _default_tile_sprite(tile_type)),
        item_content=int(raw.get("item_content", 0) or 0),
    )


def _parse_entity(raw: dict[str, Any]) -> EntitySpawn:
    return EntitySpawn(
        type=str(raw.get("type", "Unknown")),
        x=float(raw.get("x", 0)),
        y=float(raw.get("y", 0)),
    )


def _dict_items(value: Any) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, dict))


def _default_tile_sprite(tile_type: str) -> str:
    match tile_type:
        case "Brick":
            return "brick1"
        case "Question" | "QuestionBlock":
            return "blockq_0"
        case "UsedBlock":
            return "blockq_used"
        case "Pipe":
            return "pipe1_left_top"
        case _:
            return "gnd_red_1"


def _infer_width(tiles: tuple[Tile, ...], entities: tuple[EntitySpawn, ...]) -> int:
    tile_width = max((tile.x + 1 for tile in tiles), default=32)
    entity_width = max((int(entity.x) + 10 for entity in entities), default=32)
    return max(tile_width, entity_width)


def _infer_height(
    foreground: tuple[Tile, ...],
    background: tuple[Tile, ...],
    entities: tuple[EntitySpawn, ...],
) -> int:
    tile_height = max((tile.y + 1 for tile in (*foreground, *background)), default=15)
    entity_height = max((int(entity.y) + 2 for entity in entities), default=15)
    return max(tile_height, entity_height)
