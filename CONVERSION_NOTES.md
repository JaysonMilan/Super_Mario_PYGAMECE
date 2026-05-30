# C++ to Python Conversion Notes

## Source Project Analysis

The C++ project is a C++20 SDL3 game using EnTT ECS. The runtime entry point is tiny:

- `src/main.cpp` calls `mario::runMarioGame`.
- `src/Game/MarioGame.cpp` owns the high-level game lifecycle.
- Systems under `src/Systems` implement input, movement, collision, rendering, audio, enemies, HUD, editor, and level flow.
- Components under `src/Components` hold ECS data such as `Position`, `Velocity`, `AABB`, player state, enemy traits, sprites, tilemaps, and audio events.
- Assets are packed into atlas PNG files with JSON metadata under `assets/processed/atlases`.
- Levels are JSON files with `foreground`, `background`, and `entities`.

## Conversion Mapping

The Python port keeps the architecture simpler than the C++ ECS version:

- C++ `InputSystem` -> Pygame event/key handling in `app.py`.
- C++ `PlayerControllerSystem` -> `world.py` player update logic, with acceleration, friction, coyote time, jump buffering, and variable jump height.
- C++ `TileCollisionSystem` -> `physics.py` tile collider with axis-separated AABB collision.
- C++ enemy walker behavior -> `enemy.py` / `world.py` simplified walking enemies with gravity, wall turn-around, and stomp checks.
- C++ atlas/audio loading -> `assets.py`.
- C++ tilemap serializer/loader -> `level.py`.
- C++ render systems -> `renderer.py`.
- C++ sound events -> optional `audio.py` event-to-wav hooks.

## Python Project Structure

- `main.py`: package entry point.
- `game.py`: app state, Pygame lifecycle, fixed-step game loop.
- `player.py`: player construction.
- `enemy.py`: enemy construction and enemy spawn classification.
- `level.py`: level dataclasses and JSON parsing.
- `physics.py`: tile collision and movement resolution.
- `assets.py`: sprite atlas and optional audio loading.
- `settings.py`: constants.

`app.py`, `atlas.py`, `collision.py`, and `audio.py` remain as compatibility shims for earlier imports. The main implementation is in the requested beginner-friendly modules plus `world.py`, `renderer.py`, `paths.py`, `diagnostics.py`, and `cli.py`.

## Behavior Differences

This is not a line-by-line ECS port and not a cycle-accurate SMB clone. The Python version intentionally keeps a smaller entity model:

- Advanced C++ enemies such as Bowser, Lakitu, Piranha Plants, Bullet Bills, shells, projectiles, and editor-only behavior are not fully recreated yet.
- The in-game editor is not ported.
- The authenticity profile in the C++ project is approximated only through feel-oriented platformer controls.
- The Python port reuses atlas and level files from the SDL3 project instead of duplicating all assets.

These choices keep the Python code beginner-friendly and maintainable while preserving the main platforming loop.
