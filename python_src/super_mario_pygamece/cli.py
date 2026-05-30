from __future__ import annotations

import argparse
import os
import warnings
from pathlib import Path
from collections.abc import Callable
from typing import NoReturn

from .paths import ProjectPaths


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the standalone Super Mario Pygame CE port.")
    level_group = parser.add_mutually_exclusive_group()
    level_group.add_argument("--level", type=Path, help="Path to a C++/SDL3 level JSON file.")
    level_group.add_argument("--level-name", help="Level filename or stem discovered from the SDL3 project.")
    parser.add_argument("--sdl3-root", type=Path, help="Path to the Super_Mario_SDL3 project root.")
    parser.add_argument("--list-levels", action="store_true", help="Print available SDL3 JSON levels and exit.")
    parser.add_argument("--doctor", action="store_true", help="Print environment and asset diagnostics and exit.")
    parser.add_argument("--no-audio", action="store_true", help="Disable optional sound effects.")
    parser.add_argument(
        "--smoke-test-frames",
        type=int,
        help="Run a bounded number of frames, useful for CI/headless verification.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    paths = ProjectPaths.discover(sdl3_root=args.sdl3_root)
    if args.doctor:
        from .diagnostics import build_diagnostic_report

        print(build_diagnostic_report(paths))
        return 0

    if args.list_levels:
        for level_path in paths.available_levels():
            print(level_path)
        return 0

    if not paths.atlas_metadata.exists():
        parser.error(
            f"Atlas metadata not found at {paths.atlas_metadata}. "
            "Pass --sdl3-root or set SUPER_MARIO_SDL3_ROOT."
        )

    level_path = resolve_level_path(paths, args.level, args.level_name, parser.error)

    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    warnings.filterwarnings("ignore", message="pkg_resources is deprecated.*", category=UserWarning)

    from .app import PygameMario

    game = PygameMario(level_path=level_path, paths=paths, audio_enabled=not args.no_audio)
    return game.run(max_frames=args.smoke_test_frames)


def resolve_level_path(
    paths: ProjectPaths,
    explicit_level: Path | None,
    level_name: str | None,
    error: Callable[[str], NoReturn],
) -> Path | None:
    if explicit_level is not None:
        return explicit_level
    if level_name is None:
        return None

    level_path = paths.find_level(level_name)
    if level_path is None:
        error(f"Level not found: {level_name}")
    return level_path
