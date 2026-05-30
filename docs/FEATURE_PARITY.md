# Feature Parity Matrix — Super_Mario_SDL3 ↔ Super_Mario_PYGAMECE

This document tracks what the C++ SDL3 reference project ships and what the Python
Pygame-CE port currently implements. Use it as a checklist when porting features.

## How to read this file

- **Status**: ✅ Done · 🟡 Partial / placeholder · ❌ Missing
- **C++ refs** are paths under `F:\C++_Projects\Super_Mario_SDL3\`
- **Python refs** are paths under `F:\C++_Projects\Super_Mario_PYGAMECE\python_src\super_mario_pygamece\`
- **Priority**: P0 = blocking core gameplay · P1 = expected for a full SMB feel · P2 = polish · P3 = optional / advanced

When you implement a row, change the status emoji and update the Python ref to
`module.py:line`. Keep rows sorted within each category by priority.

---

## 1. Player Movement

| Feature | Status | C++ refs | Python refs | Priority | Notes |
|---|---|---|---|---|---|
| Walking with acceleration / friction | ✅ | `src/Systems/PlayerControllerSystem.h:119` | `world.py:_update_player` | — | Constants in `settings.py` (GROUND_ACCEL, FRICTION) |
| Running (Shift) with higher max speed | ✅ | `src/Components/PlayerComponents.h:26` | `world.py:_update_player` | — | `RUN_SPEED` in settings |
| Jump with gravity arc | ✅ | `src/Components/PlayerComponents.h:45` | `world.py:_update_player` | — | `JUMP_SPEED`, `MAX_FALL_SPEED` |
| Jump buffer (~100 ms) | ✅ | `src/Components/PlayerComponents.h:70` | `world.py:_update_player` (`jump_buffer_timer`) | — | `JUMP_BUFFER_TIME` |
| Coyote time (~90 ms) | ✅ | `src/Components/PlayerComponents.h:68` | `world.py:_update_player` (`coyote_timer`) | — | `COYOTE_TIME` |
| Variable-height jump (release-to-cut) | ✅ | `src/Systems/PlayerControllerSystem.h:49` | `world.py:_update_player` | — | `JUMP_CUT_MULTIPLIER` |
| Air control while airborne | ✅ | `src/Systems/PlayerControllerSystem.h:34` | `world.py:_update_player` (`AIR_ACCEL`) | — | |
| Speed-based jump bonus (run = higher jump) | ✅ | `src/Components/PlayerComponents.h:62` | `world.py:_update_player` (`speed_ratio` term) | — | +80 px jump speed at full sprint |
| Crouch (Down) for Big/Fire Mario | ✅ | `src/Systems/PlayerControllerSystem.h:38`, `PlayerStateSystem.h:76` | `world.py:_update_player` (`crouching` branch), `entities.py:Player.crouching` | — | Shrinks hitbox + plays `*_squat` sprite |
| Authentic NES table-driven movement (F6) | ❌ | `src/Systems/PlayerControllerSystem.h:63` | — | P3 | Optional fidelity mode |
| Climbing (vines / flagpole climb) | ❌ | _not surveyed_ | — | P2 | Flagpole slide animation at goal |
| Swim controls (underwater levels) | ❌ | (water levels: 2-2, 7-2) | — | P2 | Replace gravity with water buoyancy + flutter-jump |
| Pipe-entry (Down on pipe top warps) | ❌ | _not in surveyed code_ | — | P1 | Search C++ for "pipe entry" handler |

## 2. Player States (Power-ups)

| Feature | Status | C++ refs | Python refs | Priority | Notes |
|---|---|---|---|---|---|
| Small Mario | ✅ | `src/Components/PlayerComponents.h:84` | `entities.py:PowerState.SMALL`, `player.py` | — | 28 × 30 hitbox |
| Big / Super Mario | ✅ | `src/Components/PlayerComponents.h:80` | `entities.py:PowerState.SUPER` | — | 28 × 60, can break bricks |
| Fire Mario | ✅ | `src/Components/PlayerComponents.h:96` | `entities.py:PowerState.FIRE` | — | Throws fireballs (X / J) |
| Form-change freeze animation | 🟡 | `src/Components/PlayerComponents.h:103` | `world.py` (`POWERUP_FREEZE`) | P2 | We freeze for 0.55 s; C++ plays a multi-frame swap (small→big→small→big) |
| Damage invincibility (~1.5 s flashing) | ✅ | `src/Components/PlayerComponents.h:87` | `world.py:_take_damage`, `renderer.py:_draw_player` | — | Renderer skips frames during `invincible_timer` |
| Star power (9 s rainbow + auto-kill on touch) | ✅ | `src/Components/PlayerComponents.h:92`, `EnemyCollisionSystem.h:68` | `world.py:_collect` (Star), `world.py:_handle_entity_collisions` (star branch), `renderer.py:_star_tint` | — | Spawns from `?` blocks, bounces on ground, auto-kills enemies, RGB tint on player |
| Death animation (3 s bounce + fall) | 🟡 | `src/Components/PlayerComponents.h:98`, `PlayerStateSystem.h:21` | `world.py:update` (DYING branch) | P2 | We do a single bounce; C++ has frozen pose then fall |
| Mario / Luigi character select | ❌ | `src/Components/PlayerComponents.h:7`, `Game/MarioGame.cpp:85` | — | P3 | Two-player turn-based; needs character select screen |

## 3. Enemies (per-type spawn + AI)

> "Spawned" = sprite renders and walker AI applies. "AI" = the C++-specific behavior is faithfully ported.

| Feature | Status | C++ refs | Python refs | Priority | Notes |
|---|---|---|---|---|---|
| Goomba (walker) | ✅ | `src/Entities/EntityFactory.h:99` | `enemy.py:ENEMY_FRAMES`, `world.py:_update_enemies` | — | Stomp + fireball kill |
| Green Koopa Troopa | ✅ | `src/Entities/EntityFactory.h:125` | `enemy.py:ENEMY_TRAITS`, `world.py:_convert_to_shell` | — | Stomp → still shell → kicked shell |
| Red Koopa Troopa (turns at ledges) | ✅ | `src/Entities/EntityFactory.h:135` | `enemy.py:ENEMY_TRAITS["RedKoopa"]`, `world.py` (ledge probe) | — | Walks + ledge-aware turn + shell |
| Para-Koopa (Green) — hops in place | 🟡 | `src/Entities/EntityFactory.h:145`, `EnemyComponents.h:54` | `enemy.py:ENEMY_TRAITS["GreenParaKoopa"]` | P2 | Spawns + can be stomped to a shell; periodic hopping not yet implemented |
| Para-Koopa (Red) — winged red variant | 🟡 | `src/Entities/EntityFactory.h:163` | `enemy.py:ENEMY_TRAITS["RedParaKoopa"]` | P2 | Spawns; treated as ledge-aware Red Koopa |
| Buzzy Beetle (fireproof walker) | ✅ | `src/Entities/EntityFactory.h:220` | `enemy.py:ENEMY_TRAITS["BuzzyBeetle"]` | — | Stompable → shell, fireball-immune |
| Spiny (spiked walker) | ✅ | `src/Entities/EntityFactory.h:377` | `enemy.py:ENEMY_TRAITS["Spiny"]` | — | Stomp-immune + fire-immune + ledge-aware; renders via placeholder (no Spiny sprite in atlas) |
| Piranha Plant (rises from pipe) | ✅ | `src/Entities/EntityFactory.h:181` | `world.py:_update_piranha` | — | 4-phase cycle (hidden→rise→emerge→fall); retracts when Mario is within 3 tiles |
| Venus Fire Trap (Piranha that shoots fire) | ❌ | `src/Entities/EntityFactory.h:208` | — | P2 | Same emerge cycle, plus a fire projectile when up |
| Hammer Bro | ✅ | `src/Entities/EntityFactory.h:246` | `world.py:_update_hammerbro`, `world.py:_throw_hammer` | — | Patrol within ~2 tiles, periodic jump, throws hammer arc projectiles |
| Lakitu (cloud-rider, throws Spiny eggs) | ✅ | `src/Entities/EntityFactory.h:313` | `world.py:_update_lakitu`, `world.py:_spawn_spiny_drop` | — | Tracks camera, drops a Spiny every ~4.5 s |
| Bullet Bill (cannon projectile) | ✅ | `src/Entities/EntityFactory.h:412` | `world.py:_update_bullet` | — | Constant horizontal velocity, no gravity, despawn off-screen |
| Cheep Cheep (flying / swimming fish) | ❌ | `src/Entities/EntityFactory.h:294` | — | P2 | Sinusoidal arc |
| Blooper (squid) | ❌ | `src/Entities/EntityFactory.h:272` | — | P2 | Underwater levels only |
| Podoboo (lava bubble) | ❌ | `src/Entities/EntityFactory.h:354` | — | P2 | Castle levels; jumps on cooldown |
| Bowser (boss) | 🟡 | `src/Entities/EntityFactory.h:569` | `world.py:_update_bowser`, `world.py:_spawn_bowser_fire` | P1 | Patrols ~3 tiles + jumps + breathes fire. No axe-defeat sequence yet |

## 4. Enemy mechanics & shared behaviors

| Feature | Status | C++ refs | Python refs | Priority | Notes |
|---|---|---|---|---|---|
| Stomp kill (jump on head) | ✅ | `src/Systems/EnemyCollisionSystem.h:82` | `world.py:_handle_entity_collisions` | — | +100, small bounce |
| Stomp → shell (Koopa) | ✅ | `src/Components/EnemyComponents.h:30` | `world.py:_convert_to_shell`, `entities.py:ShellState` | — | Wakes after `SHELL_WAKE_TIME` (5 s) |
| Shell kick (sliding shell hits other enemies) | ✅ | `src/Systems/EnemyAISystem.h:145` | `world.py:_kick_shell`, `world.py:_award_combo_points` | — | Combo: 100→200→400→500→800→1k→2k→5k→1up |
| Walker turns at wall (horizontal contact) | ✅ | _implicit_ | `world.py:_update_enemies` | — | Flips on no-progress |
| Walker turns at ledge (Red Koopa, Hammer Bro) | ✅ | `src/Components/EnemyComponents.h` | `world.py:_update_enemies` (ledge probe) | — | Per-enemy `ledge_aware` flag |
| Fireball kills enemy (+100, knock up) | ✅ | `src/Systems/FireballSystem.h` | `world.py:_handle_entity_collisions` | — | |
| Fireball-immune enemies (Buzzy Beetle, Spiny) | ✅ | `src/Components/EnemyComponents.h` | `enemy.py:ENEMY_TRAITS`, `world.py` (`fire_immune` branch) | — | Fireball just dispels |
| Stomp-immune enemies (Piranha, Spiny, Podoboo) | ✅ | _per-enemy_ | `enemy.py:ENEMY_TRAITS`, `world.py` (`stompable` branch) | — | Routes to take_damage |
| Star power kills any enemy on contact (+200) | ✅ | `src/Systems/EnemyCollisionSystem.h:68` | `world.py:_handle_entity_collisions` (star branch) | — | Star pickup itself still missing |
| Frame-based "authentic" timing | ❌ | `src/Systems/EnemyAISystem.h:39` | — | P3 | Quantized counters when authentic mode active |
| Off-screen culling / despawn | ✅ | _implicit_ | `world.py:_update_enemies` (`ENEMY_DESPAWN_MARGIN`) | — | Cull >320 px behind camera |

## 5. Items / Powerups

| Feature | Status | C++ refs | Python refs | Priority | Notes |
|---|---|---|---|---|---|
| Coin (free pickup) | ✅ | `src/Entities/EntityFactory.h:600` | `world.py:_collect`, `level.py:create_collectible` | — | +200 + 1 coin |
| Coin pop (from `?` block) | ✅ | `src/Entities/EntityFactory.h:641`, `BlockSystem.h:94` | `world.py:_spawn_block_coin` | — | Floating coin particle |
| 100 coins → 1-up | ✅ | `src/Components/PlayerComponents.h:112` | `world.py:_maybe_oneup` | — | |
| Mushroom (Small → Super) | ✅ | `src/Entities/EntityFactory.h:682` | `world.py:_collect` | — | |
| Fire Flower (Super → Fire, or Small → Fire?) | 🟡 | `src/Entities/EntityFactory.h:827` | `world.py:_collect` | P2 | Currently always upgrades to FIRE; SMB upgrades Small→Super first |
| Star (10 s invincibility + auto-kill) | 🟡 | `src/Entities/EntityFactory.h:795` | `world.py:_collect` (Star branch) | P1 | Picks up but no rainbow draw, no enemy auto-kill, no music swap |
| 1-Up Mushroom (green) | 🟡 | `src/Entities/EntityFactory.h:713` | `world.py:_collect` (OneUp branch) | P2 | Logic exists but no level spawns it; needs hidden-block content |
| Mushroom drift physics (slides + falls + flips on wall) | ✅ | `src/Entities/EntityFactory.h:682` | `world.py:_update_collectibles` | — | |
| Mushroom emerge animation (rises out of block) | ✅ | _implicit_ | `world.py:_spawn_block_powerup` (`emerge_remaining`) | — | |
| Fire Flower stationary / no-physics | ✅ | _implicit_ | `world.py:_update_collectibles` | — | Doesn't drift |

## 6. Blocks / Tiles

| Feature | Status | C++ refs | Python refs | Priority | Notes |
|---|---|---|---|---|---|
| Solid Ground tile | ✅ | `src/Components/TilemapComponents.h:14` | `level.py:SOLID_TYPES` | — | |
| Brick — bump (Small Mario) | ✅ | `src/Systems/BlockSystem.h:140` | `world.py:_handle_block_hit` | — | |
| Brick — break (Big/Fire Mario) | ✅ | `src/Systems/BlockSystem.h:140` | `world.py:_handle_block_hit` | — | 4 particles, +50 |
| `?` block — coin | ✅ | `src/Systems/BlockSystem.h:35` | `world.py:_handle_block_hit` | — | |
| `?` block — mushroom / fire flower | ✅ | `src/Systems/BlockSystem.h:35` | `world.py:_handle_block_hit`, `level.py:ITEM_CONTENT_BY_ID` | — | Driven by per-tile `item_content` enum from level JSON |
| `?` block — star / 1-up / multi-coin | 🟡 | _per-block contents in level data_ | `world.py:_spawn_block_powerup` | P2 | Star + 1-up land via the same content enum; multi-coin bricks not yet supported |
| Used block (post-hit, solid) | ✅ | `src/Components/TilemapComponents.h:17` | `world.py:_convert_to_used` | — | |
| Block bump animation (12-frame oscillation) | ✅ | `src/Components/TilemapComponents.h:62` | `world.py.bumps`, `renderer.py:_draw_bumps` | — | |
| Multi-coin brick (10 coins from one brick) | ❌ | _SMB classic_ | — | P2 | |
| Hidden 1-up block (invisible until hit) | ❌ | _SMB classic_ | — | P2 | |
| Pipe (solid full-height) | ✅ | `src/Components/TilemapComponents.h:18` | `level.py:SOLID_TYPES` | — | Renders + collides |
| Pipe entry warp (Down at pipe top) | ❌ | _C++ system not surveyed_ | — | P1 | Needs warp destination in level data |
| Cloud / Bush / Hill (decoration) | ✅ | `src/Components/TilemapComponents.h:19-21` | `level.py` (background layer) | — | Non-solid |
| Castle decoration (background) | ✅ | `src/Components/TilemapComponents.h:22` | `level.py` (background layer) | — | |
| Vines from blocks | ❌ | _level skipping_ | — | P3 | |
| Flagpole + slide-down + climb | ❌ | _goal sequence_ | `world.py:_handle_goal` | P1 | We snap to "complete" instantly; SMB has slide + walk-into-castle |

## 7. Projectiles

| Feature | Status | C++ refs | Python refs | Priority | Notes |
|---|---|---|---|---|---|
| Player fireball (8 tile/s, ground bounce, 2-active limit) | ✅ | `src/Entities/EntityFactory.h:850`, `FireballSystem.h:104` | `world.py:_update_fireballs` | — | |
| Fireball explosion sprite on impact | ✅ | _implicit_ | `renderer.py:_draw_fireballs` (`fire_0/1`) | — | |
| Hammer Bro hammer (arc, 4 s lifetime) | ✅ | `src/Entities/EntityFactory.h:437` | `world.py:_throw_hammer`, `entities.py:EnemyProjectile` | — | Arc projectile, bounces off ground |
| Bowser fire breath | ✅ | `src/Entities/EntityFactory.h:488` | `world.py:_spawn_bowser_fire` | — | Straight-line projectile, ignores gravity |
| Venus Fire Trap fireball | ❌ | `src/Entities/EntityFactory.h:517` | — | P2 | Tied to Venus Fire Trap |
| Lakitu Spiny egg → Spiny hatch | 🟡 | `src/Entities/EntityFactory.h:541` | `world.py:_spawn_spiny_drop` | P2 | Spawns Spiny directly; egg-stage + 1.4 s hatch deferred |
| Mario fireball deflects enemy projectile | ✅ | _implicit_ | `world.py:_update_enemy_projectiles` (deflect loop) | — | +50 score |

## 8. Level Flow

| Feature | Status | C++ refs | Python refs | Priority | Notes |
|---|---|---|---|---|---|
| Level select / title screen | ✅ | `src/Systems/MenuSystem.h` | `game.py:AppState.TITLE`, `renderer.py:draw_title` | — | Lists all 39 levels |
| Active gameplay state | ✅ | `src/Game/MarioGame.cpp:199` | `game.py:AppState.PLAYING` | — | |
| Pause | ✅ | `src/Game/MarioGame.cpp` | `game.py:AppState.PAUSED` | — | |
| Goal touch ends level | ✅ | `src/Systems/GoalCollisionSystem.h:56` | `world.py:_handle_goal` | — | |
| Time bonus on level complete | ✅ | _implicit_ | `world.py:_update_level_end_walk` (consumes time × 50/s) | — | Animated tally during castle walk |
| Castle axe → bridge drop → Bowser fall | ❌ | `src/Systems/GoalCollisionSystem.h:61`, `EntityFactory.h:769` | — | P2 | Axe sprite + bridge tile interaction |
| Time limit countdown + low-time warning | ✅ | `src/Components/TilemapComponents.h:166` | `world.py.update`, `lowtime` event | — | |
| Time-up = lose life | ✅ | _implicit_ | `world.py.update` (TIMEOUT branch) | — | |
| Game over (all lives lost) → menu | ✅ | `src/Game/MarioGame.h` | `world.py:_enter_gameover`, `game.py:_update_music` | — | 3 s GAME OVER overlay then auto-return to title |
| Flagpole slide + walk-into-castle | ✅ | `src/Systems/GoalCollisionSystem.h:11` | `world.py:_begin_flagpole_slide`, `world.py:_update_level_end_walk` | — | Score tier from grab height, then auto-walk |
| Level transition cutscene ("WORLD 1-1") | ❌ | _MenuSystem_ | — | P2 | |
| Hub world / overworld map | ❌ | _N/A — SMB1 has none_ | — | P3 | |
| Two-player turns (Mario / Luigi) | ❌ | `src/Game/MarioGame.cpp:85` | — | P3 | |
| Continue prompt after game over | ❌ | _SMB classic_ | — | P3 | |

## 9. Audio

| Feature | Status | C++ refs | Python refs | Priority | Notes |
|---|---|---|---|---|---|
| jump.wav / jumpbig.wav | ✅ | `assets/sounds/` | `assets.py:AudioManager._EVENT_SOUNDS` | — | |
| coin.wav | ✅ | | `assets.py` | — | |
| mushroomappear.wav / mushroomeat.wav | ✅ | | `assets.py` | — | |
| fireball.wav | ✅ | | `assets.py` | — | |
| blockhit.wav / blockbreak.wav | ✅ | | `assets.py` | — | |
| stomp.wav (also kick) | ✅ | | `assets.py` | — | |
| death.wav | ✅ | | `assets.py` | — | |
| oneup.wav | ✅ | | `assets.py` | — | |
| levelend.wav | ✅ | | `assets.py` | — | |
| shrink.wav (damage) | ✅ | | `assets.py` | — | |
| lowtime.wav | ✅ | | `assets.py` (warns once at 100s) | — | |
| pause.wav | 🟡 | | `assets.py` (mapped) | P2 | Mapped but not triggered on pause |
| gameover.wav | 🟡 | | `assets.py` (mapped) | P2 | Mapped but not triggered |
| bowserfall.wav / bridgebreak.wav | ✅ | | `assets.py:AudioManager._EVENT_SOUNDS` | — | Mapped, fired by future axe-defeat sequence |
| rainboom.wav (star pickup) | ✅ | | `world.py:_collect` (Star branch) | — | |
| Music: overworld / underground / underwater / castle / star (+ fast variants) | ✅ | `assets/sounds/*.wav` | `audio.py:MusicManager`, `theme.py`, `game.py:_update_music` | — | Track selected per level theme; swaps to fast variant under low-time, star track during invincibility |
| Underwater audio swap (when in water level) | ✅ | _per-level_ | `theme.py:UNDERWATER`, `LEVEL_THEMES` | — | Theme-driven track |
| Pipe travel sfx | 🟡 | | `assets.py` (mapped, no event) | P2 | Tied to pipe-warp work |

## 10. HUD / UI

| Feature | Status | C++ refs | Python refs | Priority | Notes |
|---|---|---|---|---|---|
| MARIO score (6 digits) | ✅ | `src/Systems/HUDSystem.h:20` | `renderer.py:_draw_hud` | — | |
| Coin counter | ✅ | `src/Components/PlayerComponents.h:113` | `renderer.py:_draw_hud` | — | |
| World name (e.g., 1-1) | ✅ | `src/Systems/HUDSystem.h:43` | `renderer.py:_draw_hud` | — | |
| Time remaining | ✅ | _implicit_ | `renderer.py:_draw_hud` | — | |
| Lives counter | ✅ | `src/Systems/HUDSystem.h:24` | `renderer.py:_draw_hud` | — | |
| Score popup ("+100", "+200") | ✅ | _implicit_ | `world.py.popups`, `renderer.py:_draw_popups` | — | |
| Custom 8 px font from atlas | ❌ | `src/Systems/HUDSystem.h:28` | — | P2 | We use pygame default font; atlas has `ui_font.json` |
| GAME OVER screen | ✅ | `src/Systems/HUDSystem.h:24` | `renderer.py:_draw_hud` (GAMEOVER branch) | — | Black overlay + 3 s timer |
| Two-player split HUD | ❌ | _two-player_ | — | P3 | |
| Pause overlay | 🟡 | _implicit_ | `renderer.py:_draw_center_overlay` | — | Works; could use atlas font |
| Coin tally on level-end ("× 12 = 1200") | ❌ | _implicit_ | — | P2 | |

## 11. Editor

| Feature | Status | C++ refs | Python refs | Priority | Notes |
|---|---|---|---|---|---|
| Tile place / erase (LMB / RMB) | ❌ | `src/Systems/EditorSystem.h:33` | — | P3 | Whole editor not ported |
| Rectangle fill tool | ❌ | `src/Systems/EditorSystem.h:80` | — | P3 | |
| Entity placement mode | ❌ | `src/Systems/EditorSystem.h:43` | — | P3 | |
| Pipe drag-to-connect tool | ❌ | `src/Systems/EditorSystem.h:78` | — | P3 | |
| `?` block content selector (Ctrl+RMB) | ❌ | `src/Systems/EditorSystem.h:89` | — | P3 | |
| Undo / redo | ❌ | `src/Components/EditorComponents.h` | — | P3 | |
| Level browser (load / save / delete) | ❌ | `src/Systems/LevelBrowserUI.h` | — | P3 | |
| Tile palette panel | ❌ | `src/Systems/EditorUISystemImGui.h` | — | P3 | |
| Camera pan + grid snap | ❌ | `src/Components/EditorComponents.h` | — | P3 | |

## 12. Camera

| Feature | Status | C++ refs | Python refs | Priority | Notes |
|---|---|---|---|---|---|
| Follow player horizontally | ✅ | `src/Game/MarioGame.cpp` | `world.py:_update_camera` | — | |
| Camera bounds (min/max x clamp) | ✅ | `src/Components/TilemapComponents.h:167` | `world.py:_update_camera` | — | |
| One-way (no scrolling backward) | ✅ | _implicit_ | `world.py:_update_camera` | — | We clamp `target ≥ camera_x` |
| Vertical scrolling (vertical pipe rooms, 1-2 etc.) | ❌ | _level-driven_ | — | P1 | Y-axis stays at 0 |
| Boss-arena lock (8-4 castle stops scroll at axe) | ❌ | _implicit_ | — | P1 | |
| Deadzone smoothing | 🟡 | _docs reference_ | `world.py:_update_camera` (lerp) | P2 | We lerp towards target; no dedicated deadzone |

## 13. Background / parallax

| Feature | Status | C++ refs | Python refs | Priority | Notes |
|---|---|---|---|---|---|
| Background tile layer (clouds / hills / bushes) | ✅ | `src/Components/TilemapComponents.h:60` | `level.py.background`, `renderer.py:_draw_background` | — | |
| Parallax (slower scroll than foreground) | ❌ | `src/Systems/TilemapRenderSystem.h` | — | P2 | We draw bg at world coords, not parallax-shifted |
| Sky color per level (overworld vs cave vs castle) | ✅ | `src/Game/MarioGame.cpp` | `theme.py`, `world.py:GameWorld.theme`, `renderer.py:draw` | — | Castle/underground = black, underwater = teal, overworld = blue |

## 14. Misc / Infrastructure

| Feature | Status | C++ refs | Python refs | Priority | Notes |
|---|---|---|---|---|---|
| 60 Hz fixed timestep | ✅ | `src/Core/Application.h`, `ARCHITECTURE.md` | `game.py:run`, `settings.py:FIXED_DT` | — | |
| AABB tile collision | ✅ | `src/Systems/TileCollisionSystem.h` | `physics.py:TileCollider` | — | |
| Spatial hash for tiles | ✅ | _grid_ | `physics.py:TileCollider._cells` | — | |
| Atlas-packed sprite loading | ✅ | `src/Utils/AtlasLoader.h` | `assets.py:SpriteBank` | — | |
| JSON level format (foreground/background/entities) | ✅ | `src/Utils/TilemapSerializer.h` | `level.py:parse_level` | — | |
| Per-`?`-block contents in level JSON | ✅ | `src/Utils/TilemapSerializer.h` | `level.py:Tile.item_content`, `level.py:ITEM_CONTENT_BY_ID` | — | Reads `item_content` integer (0=Coin, 1=Mushroom, 2=Flower, 3=Star, 4=1-Up) |
| Gamepad input (8BitDo, Pro Controller) | ❌ | `src/Systems/InputSystem.h`, `test_8bitdo.cpp` | — | P2 | Pygame supports `pygame.joystick` |
| ECS architecture | N/A | `src/Game/MarioGame.cpp:53` (EnTT) | _OOP, not ECS_ | — | Architectural choice |
| Authentic / classic mode toggle | ❌ | `src/Components/GameplaySettings.h` | — | P3 | |
| Headless smoke test (`--smoke-test-frames`) | ✅ | _N/A_ | `cli.py`, `game.py` | — | Python-only addition |
| `--doctor` diagnostics | ✅ | _N/A_ | `cli.py`, `diagnostics.py` | — | Python-only addition |

---

## Priority roadmap (suggested next sprints)

### Sprint 1 — "make enemies feel right" (P1)
1. Per-enemy flags: `stompable`, `fire_immune`, `ledge_aware` (covers Spiny, Buzzy Beetle, Red Koopa, Piranha Plant, Podoboo).
2. Koopa shell state (stomp → shell → kick) + cascading combo points.
3. Walker ledge-aware turn-around.
4. Off-screen horizontal despawn / out-of-frame culling.

### Sprint 2 — "iconic powerups" (P1)
1. Star powerup: spawn entity, rainbow draw, auto-kill on contact, music swap.
2. `?`-block contents from level JSON (currently every-7th heuristic).
3. Hidden 1-up blocks + multi-coin bricks.

### Sprint 3 — "level-end & flow" (P1)
1. Flagpole slide animation + walk-into-castle finale.
2. GAME OVER screen with prompt.
3. Pipe-entry warps (Down on pipe top).
4. Castle axe → bridge break → Bowser fall (8-4).

### Sprint 4 — "audio & atmosphere" (P1)
1. Background music (overworld / castle / underwater / underground), with fast variant when time < 100.
2. Star music swap during invincibility.
3. Per-level sky color (overworld blue / castle black / underwater).
4. Parallax background scroll.

### Sprint 5 — "advanced enemies" (P1/P2)
1. Piranha Plant (rise / fall, stomp-immune).
2. Lakitu + Spiny egg.
3. Hammer Bro AI (jump pattern + hammer projectile).
4. Bullet Bill spawner.

### Sprint 6 — "boss" (P0 for 8-4)
1. Bowser AI (patrol, fire, hammers, jump).
2. Axe interaction → defeat sequence.

### Sprint 7 — "polish" (P2)
1. Custom 8 px font from `ui_font.json`.
2. Crouch for Big/Fire Mario.
3. Speed-based jump bonus.
4. Vertical scrolling for stages that need it.
5. Score-to-time-bonus tally on level end.

### Sprint 8 — "optional" (P3)
1. In-game editor.
2. Two-player Mario / Luigi.
3. Authentic NES mode toggle.
4. Gamepad bindings.

---

## Recent porting sessions

- **Sprint 1** — per-enemy traits, Koopa shell state, ledge-aware turn, off-screen culling, star auto-kill on contact.
- **Sprint 2** — Star powerup with bouncing physics, level-driven `?-block` contents (`item_content`), `mushroom_1up` spawning, BOM-tolerant level loader.
- **Sprint 3** — Flagpole slide + walk-into-castle finale, GAME OVER screen + auto-return-to-title, time-bonus tally during walk.
- **Sprint 4** — `MusicManager` streaming background music per level theme (`theme.py`), per-level sky color, fast-music swap under low time, star-music swap during invincibility.
- **Sprint 5** — Piranha Plant emerge cycle, Bullet Bill (no-gravity straight-line), Lakitu camera-tracking + Spiny drops.
- **Sprint 6** — Hammer Bro AI with hammer arc projectile (`EnemyProjectile`), player-fireball-deflects-hammer.
- **Sprint 7** — Bowser AI (patrol + jump + fire breath); axe-defeat sequence still pending.
- **Sprint 8** — Crouch for Big/Fire Mario, speed-based jump bonus, animated time tally on level end.

Deferred (P2/P3): Castle axe sequence, multi-coin bricks, hidden 1-up blocks, parallax scroll, vertical scroll, Venus Fire Trap fireball, Lakitu egg-stage, custom 8-px atlas font, two-player Mario/Luigi, in-game editor, gamepad bindings, authentic NES mode.

## How to update this file

When you finish a feature:
1. Change the status emoji from ❌ / 🟡 to ✅.
2. Replace the empty Python ref column with `module.py:line` (the function/class entry point).
3. If the feature shipped in a different shape than C++, note the divergence in the Notes column.
4. Cross-check the C++ ref still points at relevant code (the SDL3 project is also evolving).

Run a parity audit by spawning an Explore agent against either project with a prompt
like _"verify rows X–Y of `docs/FEATURE_PARITY.md` are still accurate"_ — this keeps
the doc honest as both codebases drift.
