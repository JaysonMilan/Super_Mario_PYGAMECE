from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ProjectPaths:
    project_root: Path
    sdl3_root: Path

    @classmethod
    def discover(cls, sdl3_root: Path | None = None) -> "ProjectPaths":
        project_root = Path(__file__).resolve().parents[2]
        if sdl3_root is not None:
            configured_root = sdl3_root
        elif "SUPER_MARIO_SDL3_ROOT" in os.environ:
            configured_root = Path(os.environ["SUPER_MARIO_SDL3_ROOT"])
        else:
            configured_root = project_root.parent / "Super_Mario_SDL3"
        return cls(project_root=project_root, sdl3_root=configured_root.resolve())

    @property
    def local_assets(self) -> Path:
        return self.project_root / "assets"

    @property
    def assets(self) -> Path:
        return self.sdl3_root / "assets"

    @property
    def atlas_metadata(self) -> Path:
        local = self.local_assets / "processed" / "atlases" / "atlases.json"
        if local.exists():
            return local
        return self.assets / "processed" / "atlases" / "atlases.json"

    @property
    def atlas_dir(self) -> Path:
        local = self.local_assets / "processed" / "atlases"
        if local.exists():
            return local
        return self.assets / "processed" / "atlases"

    @property
    def sounds_dir(self) -> Path:
        local = self.local_assets / "sounds"
        if local.exists():
            return local
        return self.assets / "sounds"

    @property
    def default_level_candidates(self) -> tuple[Path, ...]:
        return (
            self.local_assets / "levels" / "1-1.json",
            self.assets / "levels" / "1-1.json",
            self.sdl3_root / "build" / "Debug" / "assets" / "levels" / "1-1.json",
            self.local_assets / "levels" / "custom_level.json",
            self.sdl3_root / "build" / "Debug" / "assets" / "levels" / "custom_level.json",
        )

    @property
    def level_dirs(self) -> tuple[Path, ...]:
        return (
            self.local_assets / "levels",
            self.assets / "levels",
            self.sdl3_root / "build" / "Debug" / "assets" / "levels",
        )

    def available_levels(self) -> tuple[Path, ...]:
        seen_names: dict[str, Path] = {}
        for level_dir in self.level_dirs:
            if not level_dir.exists():
                continue
            for path in sorted(level_dir.glob("*.json")):
                key = path.name.casefold()
                if key not in seen_names:
                    seen_names[key] = path.resolve()
        return tuple(seen_names.values())

    def find_level(self, name: str) -> Path | None:
        requested = Path(name)
        if requested.exists():
            return requested.resolve()

        wanted = requested.name.casefold()
        wanted_with_suffix = wanted if wanted.endswith(".json") else f"{wanted}.json"
        for path in self.available_levels():
            if path.name.casefold() == wanted_with_suffix or path.stem.casefold() == wanted:
                return path
        return None
