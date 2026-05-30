# Texture Atlases

This directory stores generated atlases and metadata used at runtime.

## Files

- `atlases.json`: sprite metadata map
- `*_atlas.png`: atlas textures
- `ui_font.json`: font metadata used by UI/HUD

## Usage

Runtime loads metadata from:
- `assets/processed/atlases/atlases.json`

All sprite lookup in gameplay/editor is validated against this metadata by tests.

## Regeneration

From repo root:

```powershell
cd tools
build_atlases.bat
```

or run the Python builder directly:

```powershell
python tools/build_atlas.py
```

## Validation

Run metadata and level consistency tests:

```powershell
ctest -C Debug --test-dir build --output-on-failure -R "atlas_metadata|level_tile_validation"
```
