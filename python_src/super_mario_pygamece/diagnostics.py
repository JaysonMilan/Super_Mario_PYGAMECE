from __future__ import annotations

from importlib import metadata
import re

from .paths import ProjectPaths

REQUIRED_PYGAME_CE = "2.5.7"


def build_diagnostic_report(paths: ProjectPaths) -> str:
    levels = paths.available_levels()
    sounds = tuple(paths.sounds_dir.glob("*.wav")) if paths.sounds_dir.exists() else ()
    try:
        pygame_ce_version = metadata.version("pygame-ce")
    except metadata.PackageNotFoundError:
        pygame_ce_version = "not installed"
    pygame_status = _version_status(pygame_ce_version, REQUIRED_PYGAME_CE)

    lines = [
        f"Project root: {paths.project_root}",
        f"SDL3 root: {paths.sdl3_root}",
        f"Pygame CE: {pygame_ce_version} ({pygame_status})",
        f"Atlas metadata: {_status(paths.atlas_metadata.exists())} {paths.atlas_metadata}",
        f"Atlas directory: {_status(paths.atlas_dir.exists())} {paths.atlas_dir}",
        f"Levels found: {len(levels)}",
        f"Sounds found: {len(sounds)}",
    ]
    if levels:
        lines.append(f"Default level candidate: {levels[0]}")
    return "\n".join(lines)


def _status(ok: bool) -> str:
    return "OK" if ok else "MISSING"


def _version_status(installed: str, required: str) -> str:
    installed_tuple = _version_tuple(installed)
    required_tuple = _version_tuple(required)
    if installed_tuple is None:
        return f"MISSING, required >= {required}"
    if installed_tuple < required_tuple:
        return f"OUTDATED, required >= {required}"
    return "OK"


def _version_tuple(version: str) -> tuple[int, int, int] | None:
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)", version)
    if match is None:
        return None
    return tuple(int(part) for part in match.groups())
