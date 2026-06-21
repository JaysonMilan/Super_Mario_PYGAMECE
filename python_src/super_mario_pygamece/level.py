from __future__ import annotations

import json
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import Any

import pygame

from .entities import Collectible
from .paths import ProjectPaths
from .settings import TILE_SIZE


# Foreground tile types that are solid — matches the C++ isSolid() rule.
SOLID_TYPES = {
    "Ground",
    "Brick",
    "Pipe",
    "PipeBody",
    "PipeTop",
    "QuestionBlock",
    "Question",
    "UsedBlock",
}

# Non-solid foreground tiles rendered as scenery (C++ TileType decorations).
DECORATION_TYPES = {"Cloud", "Bush", "Hill", "Castle"}

QUESTION_TYPES = {"Question", "QuestionBlock"}
BRICK_TYPES = {"Brick"}

COLLECTIBLE_TYPES = {"Coin", "Mushroom", "FireFlower", "Flower", "Star", "OneUp"}


class WarpDirection(IntEnum):
    DOWN = 0
    RIGHT = 1
    LEFT = 2


@dataclass(frozen=True, slots=True)
class WarpDefinition:
    entry_tile_x: int
    entry_tile_y: int
    dest_level: str
    dest_world_x: float
    dest_world_y: float
    exit_facing_right: bool = True
    entry_dir: WarpDirection = WarpDirection.DOWN
    exit_horizontal: bool = False


@dataclass(frozen=True, slots=True)
class MovingPlatformDef:
    start_x: float
    start_y: float
    end_x: float
    end_y: float
    speed: float = 2.0
    width: float = 3.0
    ease_endpoints: bool = False
    ease_distance: float = 2.0


@dataclass(frozen=True, slots=True)
class FallingPlatformDef:
    x: float
    y: float
    width: float = 3.0
    fall_speed: float = 7.5


@dataclass(frozen=True, slots=True)
class SeesawPlatformPairDef:
    ax: float
    ay: float
    bx: float
    by: float
    width: float = 3.0
    drop_threshold: float = 4.0


@dataclass(frozen=True, slots=True)
class UpFireDef:
    x: float
    origin_y: float
    rise_height: float = 8.0


@dataclass(frozen=True, slots=True)
class FireBarDef:
    center_x: float
    center_y: float
    segments: int = 3
    radius: float = 1.25
    angular_speed: float = 2.4
    start_angle: float = 0.0


@dataclass(frozen=True, slots=True)
class CheepSpawnerDef:
    entry_x: float
    exit_x: float
    spawn_y: float
    interval_min: float = 0.675
    interval_max: float = 1.700


@dataclass(frozen=True, slots=True)
class LevelMeta:
    name: str
    width: int
    height: int
    time_limit: int = 400
    level_type: str = "Overworld"  # Overworld | Underground | Underwater | Castle
    camera_min_x: float = 0.0   # tile units (C++ camera_bounds.min_x)
    camera_max_x: float = 0.0   # tile units; 0 means use full level width


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
    hits_remaining: int = 1


@dataclass(frozen=True, slots=True)
class EntitySpawn:
    type: str
    x: float
    y: float
    dest_level: str = ""
    dest_world_x: float = 0.0
    dest_world_y: float = 0.0


@dataclass(frozen=True, slots=True)
class LevelData:
    meta: LevelMeta
    foreground: tuple[Tile, ...]
    background: tuple[Tile, ...]
    entities: tuple[EntitySpawn, ...]
    warps: tuple[WarpDefinition, ...] = ()
    moving_platforms: tuple[MovingPlatformDef, ...] = ()
    falling_platforms: tuple[FallingPlatformDef, ...] = ()
    seesaw_pairs: tuple[SeesawPlatformPairDef, ...] = ()
    upfires: tuple[UpFireDef, ...] = ()
    firebars: tuple[FireBarDef, ...] = ()
    cheep_spawners: tuple[CheepSpawnerDef, ...] = ()


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
    warps = tuple(_parse_warp(warp) for warp in _dict_items(raw.get("warps")))
    moving = tuple(_parse_moving(p) for p in _dict_items(raw.get("moving_platforms")))
    falling = tuple(_parse_falling(p) for p in _dict_items(raw.get("falling_platforms")))
    seesaws = tuple(_parse_seesaw(p) for p in _dict_items(raw.get("seesaw_pairs")))
    upfires = tuple(_parse_upfire(p) for p in _dict_items(raw.get("upfires")))
    firebars = tuple(_parse_firebar(p) for p in _dict_items(raw.get("firebars")))
    cheep_spawners = tuple(_parse_cheep_spawner(p) for p in _dict_items(raw.get("cheep_spawners")))

    width = int(raw_level.get("width", _infer_width(foreground, entities)))
    height = int(raw_level.get("height", _infer_height(foreground, background, entities)))

    name = str(raw_level.get("name") or name_hint or "Pygame 1-1")

    bounds = raw_level.get("camera_bounds", {})
    cam_min_x = float(bounds.get("min_x", 0.0))
    cam_max_x = float(bounds.get("max_x", 0.0))
    return LevelData(
        meta=LevelMeta(
            name=name,
            width=max(width, 32),
            height=max(height, 15),
            time_limit=int(raw_level.get("time_limit", 400)),
            level_type=str(raw_level.get("level_type", "Overworld")),
            camera_min_x=cam_min_x,
            camera_max_x=cam_max_x,
        ),
        foreground=foreground,
        background=background,
        entities=entities,
        warps=warps,
        moving_platforms=moving,
        falling_platforms=falling,
        seesaw_pairs=seesaws,
        upfires=upfires,
        firebars=firebars,
        cheep_spawners=cheep_spawners,
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
        warps=(),
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
        hits_remaining=max(1, int(raw.get("hits_remaining", 1) or 1)),
    )


def _parse_entity(raw: dict[str, Any]) -> EntitySpawn:
    return EntitySpawn(
        type=str(raw.get("type", "Unknown")),
        x=float(raw.get("x", 0)),
        y=float(raw.get("y", 0)),
        dest_level=str(raw.get("dest_level", "")),
        dest_world_x=float(raw.get("dest_world_x", 0.0)),
        dest_world_y=float(raw.get("dest_world_y", 0.0)),
    )


def _parse_warp(raw: dict[str, Any]) -> WarpDefinition:
    return WarpDefinition(
        entry_tile_x=int(raw.get("entry_tile_x", 0)),
        entry_tile_y=int(raw.get("entry_tile_y", 0)),
        dest_level=str(raw.get("dest_level", "")),
        dest_world_x=float(raw.get("dest_world_x", 0.0)),
        dest_world_y=float(raw.get("dest_world_y", 0.0)),
        exit_facing_right=bool(raw.get("exit_facing_right", True)),
        entry_dir=WarpDirection(int(raw.get("entry_dir", 0))),
        exit_horizontal=bool(raw.get("exit_horizontal", False)),
    )


def _parse_moving(raw: dict[str, Any]) -> MovingPlatformDef:
    return MovingPlatformDef(
        start_x=float(raw.get("start_x", 0.0)),
        start_y=float(raw.get("start_y", 0.0)),
        end_x=float(raw.get("end_x", 0.0)),
        end_y=float(raw.get("end_y", 0.0)),
        speed=float(raw.get("speed", 2.0)),
        width=float(raw.get("width", 3.0)),
        ease_endpoints=bool(raw.get("ease_endpoints", False)),
        ease_distance=float(raw.get("ease_distance", 2.0)),
    )


def _parse_falling(raw: dict[str, Any]) -> FallingPlatformDef:
    return FallingPlatformDef(
        x=float(raw.get("x", 0.0)),
        y=float(raw.get("y", 0.0)),
        width=float(raw.get("width", 3.0)),
        fall_speed=float(raw.get("fall_speed", 7.5)),
    )


def _parse_seesaw(raw: dict[str, Any]) -> SeesawPlatformPairDef:
    return SeesawPlatformPairDef(
        ax=float(raw.get("ax", 0.0)),
        ay=float(raw.get("ay", 0.0)),
        bx=float(raw.get("bx", 0.0)),
        by=float(raw.get("by", 0.0)),
        width=float(raw.get("width", 3.0)),
        drop_threshold=float(raw.get("drop_threshold", 4.0)),
    )


def _parse_upfire(raw: dict[str, Any]) -> UpFireDef:
    return UpFireDef(
        x=float(raw.get("x", 0.0)),
        origin_y=float(raw.get("origin_y", 0.0)),
        rise_height=float(raw.get("rise_height", 8.0)),
    )


def _parse_firebar(raw: dict[str, Any]) -> FireBarDef:
    return FireBarDef(
        center_x=float(raw.get("center_x", 0.0)),
        center_y=float(raw.get("center_y", 0.0)),
        segments=int(raw.get("segments", 3)),
        radius=float(raw.get("radius", 1.25)),
        angular_speed=float(raw.get("angular_speed", 2.4)),
        start_angle=float(raw.get("start_angle", 0.0)),
    )


def _parse_cheep_spawner(raw: dict[str, Any]) -> CheepSpawnerDef:
    return CheepSpawnerDef(
        entry_x=float(raw.get("entry_x", 0.0)),
        exit_x=float(raw.get("exit_x", 0.0)),
        spawn_y=float(raw.get("spawn_y", 0.0)),
        interval_min=float(raw.get("interval_min", 0.675)),
        interval_max=float(raw.get("interval_max", 1.700)),
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
