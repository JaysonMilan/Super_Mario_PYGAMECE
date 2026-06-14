from __future__ import annotations

# Matches the SDL3 game window (Application("Super Mario SDL3", 800, 600)).
SCREEN_SIZE = (800, 600)
TILE_SIZE = 32
FIXED_DT = 1.0 / 60.0

GRAVITY = 2560.0           # C++ gravity_falling = 80.0 t/s² × 32 (general falling entities)
GRAVITY_RISING = 1760.0   # C++ gravity_rising = 55.0 t/s² × 32 (player while rising)
GRAVITY_CUT = 3840.0      # C++ gravity_cut = 120.0 t/s² × 32 (player jump-release)
WALK_SPEED = 144.0        # C++ max_walk_speed = 4.5 t/s × 32
RUN_SPEED = 352.0         # C++ max_run_speed = 11.0 t/s × 32
JUMP_SPEED = 704.0        # C++ base_jump_speed = 22.0 t/s × 32
ENEMY_SPEED = 32.0        # C++ goomba walk_speed = 1.0 t/s × 32
GROUND_ACCELERATION = 800.0   # C++ walk_accel = 25.0 t/s² × 32
RUN_ACCELERATION = 1120.0     # C++ run_accel = 35.0 t/s² × 32 (run button held)
AIR_ACCELERATION = 256.0      # C++ air_accel = 8.0 t/s² × 32
GROUND_FRICTION = 800.0       # C++ ground_decel = 25.0 t/s² × 32
MAX_FALL_SPEED = 640.0    # C++ terminal_velocity = 20.0 t/s × 32
COYOTE_TIME = 0.12        # C++ coyote_time = 0.12
JUMP_BUFFER_TIME = 0.20   # C++ buffer_time = 0.20
CAMERA_FOLLOW_SPEED = 8.0
RESPAWN_DELAY = 2.0       # C++ respawn_delay_timer_ < 2.0
PIPE_ANIM_DURATION = 0.60  # C++ PipeEntry::kAnimDuration = 0.6
STARTING_LIVES = 3

# Powerups
POWERUP_FREEZE = 0.55
INVINCIBILITY_TIME = 2.5  # ~150 frames @ 60fps, matches SDL3/SMB1
MUSHROOM_SPEED = 120.0    # C++ ItemSpawnRise::rise_speed = 3.75 t/s × 32
HAMMER_GRAVITY = 1344.0   # C++ hammer projectile gravity_rising/falling = 42 t/s² × 32

# Fireballs
FIREBALL_SPEED = 384.0    # C++ speed = 12.0 t/s × 32
FIREBALL_GRAVITY = 1536.0  # C++ gravity = 48.0 t/s² × 32
FIREBALL_VBOUNCE = 320.0  # C++ bounce_speed = 10.0 t/s × 32
FIREBALL_COOLDOWN = 0.10  # matches SDL3 fireball_cooldown_duration
FIREBALL_TERMINAL = 576.0  # C++ terminal_velocity = 18.0 t/s × 32 (fireballs only)

# Timer
LOW_TIME_THRESHOLD = 100.0

# Enemies
ENEMY_DESPAWN_MARGIN = 320.0  # px behind camera before an enemy is culled
SHELL_KICK_SPEED = 272.0      # C++ EnemyShell::speed = 8.5 t/s × 32
SHELL_WAKE_TIME = 248.0 / 60.0  # C++ wake_up_delay = 248/60 ≈ 4.13 s
# Cascading shell-combo scores; clamps at the final tier (matches SDL3 ComboState).
STOMP_COMBO_SCORES = (100, 200, 400, 800, 1000, 2000, 4000, 8000)

SPRITEBANK_SCALED_CACHE_MAX = 512

# HUD layout (HUDSystem.cpp)
HUD_ROW1 = 8
HUD_ROW2 = 26
HUD_X_MARIO = 16
HUD_X_COINS = 170
HUD_X_WORLD = 320
HUD_X_TIME = 470
HUD_X_LIVES = 600
FS_HUD = 16
FS_TITLE = 24
FS_MED = 18
FS_SUB = 14

SKY_COLOR = (92, 148, 252)
