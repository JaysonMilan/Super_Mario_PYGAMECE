"""Level themes drive the sky color, music track, and ambient feel."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LevelTheme:
    name: str
    sky: tuple[int, int, int]
    music: str
    music_fast: str | None = None


OVERWORLD = LevelTheme(
    name="overworld", sky=(92, 148, 252),
    music="overworld.wav", music_fast="overworld-fast.wav",
)
UNDERGROUND = LevelTheme(
    name="underground", sky=(0, 0, 0),
    music="underground.wav", music_fast="underground-fast.wav",
)
UNDERWATER = LevelTheme(
    name="underwater", sky=(82, 152, 196),
    music="underwater.wav", music_fast="underwater-fast.wav",
)
CASTLE = LevelTheme(
    name="castle", sky=(0, 0, 0),
    music="castle.wav", music_fast="castle-fast.wav",
)


# Curated mapping for the 32 mainline levels — matches SMB 1.
LEVEL_THEMES: dict[str, LevelTheme] = {
    # World 1
    "1-1": OVERWORLD, "1-2": UNDERGROUND, "1-3": OVERWORLD, "1-4": CASTLE,
    # World 2
    "2-1": OVERWORLD, "2-2": UNDERWATER, "2-3": OVERWORLD, "2-4": CASTLE,
    # World 3
    "3-1": OVERWORLD, "3-2": OVERWORLD, "3-3": OVERWORLD, "3-4": CASTLE,
    # World 4
    "4-1": OVERWORLD, "4-2": UNDERGROUND, "4-3": OVERWORLD, "4-4": CASTLE,
    # World 5
    "5-1": OVERWORLD, "5-2": OVERWORLD, "5-3": OVERWORLD, "5-4": CASTLE,
    # World 6
    "6-1": OVERWORLD, "6-2": OVERWORLD, "6-3": OVERWORLD, "6-4": CASTLE,
    # World 7
    "7-1": OVERWORLD, "7-2": UNDERWATER, "7-3": OVERWORLD, "7-4": CASTLE,
    # World 8
    "8-1": OVERWORLD, "8-2": OVERWORLD, "8-3": OVERWORLD, "8-4": CASTLE,
}


def theme_for(level_name: str, level_type: str = "") -> LevelTheme:
    """Pick a theme, preferring the level JSON's level_type when present."""
    by_type = {
        "overworld": OVERWORLD,
        "underground": UNDERGROUND,
        "underwater": UNDERWATER,
        "castle": CASTLE,
    }.get(level_type.lower())
    if by_type is not None:
        return by_type
    if level_name in LEVEL_THEMES:
        return LEVEL_THEMES[level_name]
    lower = level_name.lower()
    if "castle" in lower or lower.endswith("-4"):
        return CASTLE
    if "underwater" in lower or "water" in lower:
        return UNDERWATER
    if "underground" in lower or "cave" in lower:
        return UNDERGROUND
    return OVERWORLD


__all__ = [
    "CASTLE",
    "LEVEL_THEMES",
    "LevelTheme",
    "OVERWORLD",
    "UNDERGROUND",
    "UNDERWATER",
    "theme_for",
]
