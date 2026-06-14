"""Bitmap UI font shared with the SDL3 game (ui_atlas "font" strip).

Mirrors HUDSystem/MenuSystem: 8x8 glyphs in a horizontal strip, mapped via
assets/processed/atlases/ui_font.json (fallback: chars 43-90 -> index 1+,
118-122 -> index 49+). Punctuation ,.:; advances the pen less.
"""
from __future__ import annotations

import json
from pathlib import Path

import pygame

WHITE = (255, 255, 255)
SHADOW = (0, 0, 0)

_DEFAULT_RANGES = ((43, 90, 1), (118, 122, 49))
_DEFAULT_EXTRA = (",", ".", ":", ";")


class BitmapFont:
    def __init__(self, strip: pygame.Surface | None, mapping_path: Path | None = None) -> None:
        if strip is None:
            strip = pygame.Surface((512, 8), pygame.SRCALPHA)
        self._strip = strip
        self._glyph_size = 8
        self._glyph_x = [0] * 256
        self._extra: set[str] = set()
        self._cache: dict[tuple[int, int, tuple[int, int, int]], pygame.Surface] = {}
        self._load_mapping(mapping_path)

    def _load_mapping(self, mapping_path: Path | None) -> None:
        ranges = _DEFAULT_RANGES
        extra = _DEFAULT_EXTRA
        if mapping_path is not None and mapping_path.exists():
            try:
                data = json.loads(mapping_path.read_text(encoding="utf-8-sig"))
                self._glyph_size = int(data.get("glyph_size", 8))
                ranges = tuple(
                    (int(r["start"]), int(r["end"]), int(r["start_index"]))
                    for r in data.get("ranges", [])
                ) or _DEFAULT_RANGES
                extra = tuple(data.get("extra_spacing", _DEFAULT_EXTRA))
            except (ValueError, KeyError, TypeError):
                pass
        for start, end, start_index in ranges:
            for ch in range(start, end + 1):
                self._glyph_x[ch & 0xFF] = (start_index + ch - start) * self._glyph_size
        self._extra = {value[0] for value in extra if value}

    def _glyph(self, glyph_x: int, size: int, color: tuple[int, int, int]) -> pygame.Surface:
        key = (glyph_x, size, color)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        source = self._strip.subsurface((glyph_x, 0, self._glyph_size, self._glyph_size))
        scaled = pygame.transform.scale(source, (size, size)).copy()
        if color != WHITE:
            scaled.fill(color, special_flags=pygame.BLEND_RGB_MULT)
        self._cache[key] = scaled
        return scaled

    def draw(
        self,
        surface: pygame.Surface,
        text: str,
        x: float,
        y: float,
        size: int,
        color: tuple[int, int, int] = WHITE,
    ) -> None:
        extra_spacing = max(1, size // 4)
        extra_left = 0
        for i, ch in enumerate(text):
            glyph_x = self._glyph_x[ord(ch) & 0xFF]
            surface.blit(
                self._glyph(glyph_x, size, color),
                (round(x + i * size - extra_left), round(y)),
            )
            if ch in self._extra:
                extra_left += extra_spacing

    def draw_shadow(
        self,
        surface: pygame.Surface,
        text: str,
        x: float,
        y: float,
        size: int,
        color: tuple[int, int, int] = WHITE,
    ) -> None:
        self.draw(surface, text, x - 1, y + 1, size, SHADOW)
        self.draw(surface, text, x + 1, y - 1, size, color)

    def width(self, text: str, size: int) -> int:
        extra_spacing = max(1, size // 4)
        extra = sum(extra_spacing for ch in text if ch in self._extra)
        return len(text) * size - extra


__all__ = ["BitmapFont"]
