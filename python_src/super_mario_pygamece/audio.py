from __future__ import annotations

from pathlib import Path

import pygame

from .assets import AudioManager
from .theme import LevelTheme


class MusicManager:
    """Streams background music tracks via pygame.mixer.music.

    Resolves the desired track from level theme + game state (low time,
    star power, level-end fanfare, game over) and only swaps when the
    desired track changes, so it never restarts mid-loop.
    """

    STAR_TRACK = "starmusic.wav"
    LEVEL_END_TRACK = "levelend.wav"
    GAMEOVER_TRACK = "gameover.wav"
    PRINCESS_TRACK = "princessmusic.wav"

    def __init__(self, sounds_dir: Path, enabled: bool = True) -> None:
        self._dir = sounds_dir
        self._enabled = False
        self._current: str | None = None
        if not enabled:
            return
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            self._enabled = True
        except pygame.error:
            self._enabled = False

    def update(
        self,
        theme: LevelTheme,
        *,
        low_time: bool = False,
        star_power: bool = False,
        level_complete: bool = False,
        gameover: bool = False,
    ) -> None:
        if not self._enabled:
            return
        track = self._desired_track(
            theme,
            low_time=low_time,
            star_power=star_power,
            level_complete=level_complete,
            gameover=gameover,
        )
        if track == self._current:
            return
        self._switch(track)

    def stop(self) -> None:
        if self._enabled:
            try:
                pygame.mixer.music.stop()
            except pygame.error:
                pass
        self._current = None

    def _desired_track(
        self,
        theme: LevelTheme,
        *,
        low_time: bool,
        star_power: bool,
        level_complete: bool,
        gameover: bool,
    ) -> str | None:
        if gameover:
            return self.GAMEOVER_TRACK
        if level_complete:
            return self.LEVEL_END_TRACK
        if star_power:
            return self.STAR_TRACK
        if low_time and theme.music_fast:
            return theme.music_fast
        return theme.music

    def _switch(self, track: str | None) -> None:
        try:
            pygame.mixer.music.stop()
        except pygame.error:
            pass
        self._current = track
        if track is None:
            return
        path = self._dir / track
        if not path.exists():
            self._current = None
            return
        try:
            pygame.mixer.music.load(str(path))
            # Game over and level-end fanfares are one-shot, looping music streams.
            loops = 0 if track in {self.LEVEL_END_TRACK, self.GAMEOVER_TRACK} else -1
            pygame.mixer.music.set_volume(0.45)
            pygame.mixer.music.play(loops=loops)
        except pygame.error:
            self._current = None


__all__ = ["AudioManager", "MusicManager"]
