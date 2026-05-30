# Super Mario PYGAMECE

Standalone Python/Pygame CE port of the sibling `Super_Mario_SDL3` project.

Sprite atlases, sound effects, and 39 level JSON files have been copied into the
local `assets/` folder, so the project runs **without any reference to the SDL3
project**. If `assets/` is removed, the launcher falls back to:

```text
F:\C++_Projects\Super_Mario_SDL3
```

Override the SDL3 fallback path with `--sdl3-root` or `SUPER_MARIO_SDL3_ROOT`.

See `CONVERSION_NOTES.md` for the C++ structure analysis and Python conversion mapping.

## Run

```powershell
.\run.bat
```

Or manually:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m super_mario_pygamece
```

Install from `requirements.txt` only:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Install optional development tools:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

List levels discovered from the SDL3 project:

```powershell
.\run.bat --list-levels
```

Check asset/environment diagnostics:

```powershell
.\run.bat --doctor
```

Run a specific SDL3 JSON level:

```powershell
.\run.bat --level F:\C++_Projects\Super_Mario_SDL3\build\Debug\assets\levels\custom_level.json
```

Or use a discovered level name:

```powershell
.\run.bat --level-name 1-1
```

Disable optional sound effects:

```powershell
.\run.bat --no-audio
```

## Controls

### Title

- `Up/Down` or `W/S`: select level
- `Enter` or `Space`: start selected level
- `Esc`: quit

### Gameplay

- `Left/Right` or `A/D`: move
- `Space`, `Z`, or `K`: jump (release early for a short hop)
- `X` or `J`: throw fireball (Fire Mario only)
- `Shift`: run
- `R`: restart current level
- `P`: pause
- `Tab`: return to level select
- `Esc`: quit

### Powerups & blocks

- `Mushroom`: small Mario grows into Super Mario (taller, can break bricks).
- `Fire Flower`: Super Mario becomes Fire Mario and can throw fireballs.
- `?` blocks: hit from below to reveal a coin or a powerup.
- Brick blocks: bumped by small Mario, smashed by Super/Fire Mario.
- Getting hit while Super/Fire shrinks Mario back to small with brief invincibility.
- Falling off the map, running out of time, or touching an enemy while small loses a life.
- Every 100 coins grants an extra life.

### Pause

- `P`, `Enter`, or `Space`: resume
- `R`: restart level
- `Esc`: return to level select

## Checks

Run the project check script:

```powershell
.\check.bat
```

`check.bat` runs `ruff` and `mypy` when the optional dev tools are installed; otherwise it skips them and still runs tests, compilation, and smoke checks.

Or run the individual checks:

```powershell
$env:PYTHONPATH = "python_src"
python -m unittest discover -s tests
python -m compileall -q python_src tests
```

Headless smoke test:

```powershell
$env:SDL_VIDEODRIVER = "dummy"
$env:PYTHONPATH = "python_src"
python -m super_mario_pygamece --smoke-test-frames 3
```

## Structure

- `main.py`: package entry point
- `game.py`: app state, Pygame lifecycle, fixed-step loop
- `player.py`: player construction
- `enemy.py`: enemy construction
- `physics.py`: tile collision and movement resolution
- `assets.py`: sprite atlas and optional audio loading
- `settings.py`: constants
- `cli.py`: command-line parsing and asset path validation
- `app.py`: compatibility import for older code
- `world.py`: gameplay state, player/enemy updates, scoring, camera
- `renderer.py`: drawing and HUD rendering
- `audio.py`, `atlas.py`, `collision.py`: compatibility imports
- `atlas.py`: SDL3 atlas metadata loading and sprite extraction
- `level.py`: SDL3 level JSON parsing and fallback template generation
