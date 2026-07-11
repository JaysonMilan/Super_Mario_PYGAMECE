from __future__ import annotations

import math
import random
from typing import Protocol

import pygame

from .enemy import create_enemy
from .entities import Enemy, EnemyProjectile, Player, ShellState
from .level import EntitySpawn
from .physics import TileCollider
from .settings import (
    ENEMY_DESPAWN_MARGIN,
    GRAVITY,
    GRAVITY_RISING,
    HAMMER_GRAVITY,
    MAX_FALL_SPEED,
    SCREEN_SIZE,
    TILE_SIZE,
)


class EnemyAIWorld(Protocol):
    player: Player
    camera_x: float
    events: list[str]
    collider: TileCollider
    enemies: list[Enemy]
    enemy_projectiles: list[EnemyProjectile]

    def _wake_shell(self, enemy: Enemy) -> None: ...


def update_walker(world: EnemyAIWorld, enemy: Enemy, dt: float) -> None:
    if enemy.frames and enemy.frames[0] == "spikey1_0":
        enemy.ai_timer -= dt
        if enemy.body.on_ground or enemy.ai_timer <= 0:
            enemy.frames = ("spikey0_0", "spikey0_1")
            enemy.body.velocity.x = -1.2 * TILE_SIZE
        else:
            enemy.body.velocity.x = enemy.home_x * 1.7 * TILE_SIZE

    if enemy.shell_state is ShellState.SHELL_STILL:
        enemy.shell_wake_timer -= dt
        if enemy.shell_wake_timer <= 0:
            world._wake_shell(enemy)

    if enemy.winged and enemy.body.on_ground:
        enemy.ai_timer -= dt
        if enemy.ai_timer <= 0:
            enemy.ai_timer = 1.2  # C++ KoopaWingedBehavior::jump_interval = 1.2f
            enemy.body.velocity.y = -8.0 * TILE_SIZE  # C++ jump_speed = 8.0 t/s

    before_x = enemy.body.pos.x
    before_vx = enemy.body.velocity.x
    _egrav = GRAVITY_RISING if enemy.body.velocity.y < 0 else GRAVITY
    enemy.body.velocity.y = min(enemy.body.velocity.y + _egrav * dt, MAX_FALL_SPEED)
    world.collider.move_and_collide(enemy.body, dt)

    if abs(before_vx) > 1.0 and abs(enemy.body.velocity.x) < 0.001:
        if enemy.shell_state is ShellState.SHELL_KICKED:
            enemy.body.velocity.x = -before_vx
            enemy.body.facing = -enemy.body.facing
            enemy.terrain_rebound_armed = True
            world.events.append("blockbump")
        else:
            enemy.body.velocity.x = -before_vx if before_vx else -enemy.body.facing * 70.0
            enemy.body.facing = -enemy.body.facing

    if (
        enemy.ledge_aware
        and enemy.shell_state is ShellState.WALKING
        and enemy.body.on_ground
        and enemy.body.velocity.x
    ):
        probe_x = enemy.body.rect.right if enemy.body.velocity.x > 0 else enemy.body.rect.left - 2
        probe = pygame.Rect(int(probe_x), int(enemy.body.rect.bottom), 2, 4)
        if not any(probe.colliderect(tile) for tile in world.collider.nearby(probe)):
            enemy.body.velocity.x = -enemy.body.velocity.x
            enemy.body.facing = -enemy.body.facing


def update_piranha(world: EnemyAIWorld, enemy: Enemy, dt: float) -> None:
    cycle_speed = 60.0
    rise_distance = 1.5 * TILE_SIZE
    player_dx = abs(world.player.pos.x - enemy.home_x)
    retract_threshold = TILE_SIZE * 2.06
    enemy.ai_timer += dt
    if enemy.ai_phase == 0:
        if enemy.ai_timer > 64.0 / 60.0 and player_dx > retract_threshold:
            enemy.ai_phase = 1
            enemy.ai_timer = 0.0
    elif enemy.ai_phase == 1:
        enemy.body.pos.y -= cycle_speed * dt
        if enemy.home_y - enemy.body.pos.y >= rise_distance:
            enemy.body.pos.y = enemy.home_y - rise_distance
            enemy.ai_phase = 2
            enemy.ai_timer = 0.0
    elif enemy.ai_phase == 2:
        if enemy.ai_timer > 64.0 / 60.0:
            enemy.ai_phase = 3
            enemy.ai_timer = 0.0
    elif enemy.ai_phase == 3:
        enemy.body.pos.y += cycle_speed * dt
        if enemy.body.pos.y >= enemy.home_y:
            enemy.body.pos.y = enemy.home_y
            enemy.ai_phase = 0
            enemy.ai_timer = 0.0


def update_blooper(world: EnemyAIWorld, enemy: Enemy, dt: float) -> None:
    rise_speed = 1.5 * TILE_SIZE
    dive_speed = 0.65 * TILE_SIZE
    h_speed = 0.45 * TILE_SIZE
    upper = enemy.home_y - 0.9375 * TILE_SIZE
    if enemy.ai_phase == 1:
        enemy.frames = ("squid0",)
        enemy.body.velocity.update(enemy.body.facing * h_speed, -rise_speed)
        enemy.ai_timer -= dt
        if enemy.ai_timer <= 0:
            enemy.ai_timer = 0.35
            enemy.body.facing = -1 if world.player.pos.x < enemy.body.pos.x else 1
        if enemy.body.pos.y <= upper:
            enemy.ai_phase = 2
            enemy.ai_timer = 0.5
    elif enemy.ai_phase == 2:
        enemy.frames = ("squid1",)
        enemy.body.velocity.update(enemy.body.facing * h_speed * 0.25, 0.0)
        enemy.ai_timer -= dt
        if enemy.ai_timer <= 0:
            enemy.ai_phase = 0
    else:
        enemy.frames = ("squid1",)
        enemy.body.velocity.update(enemy.body.facing * h_speed * 0.2, dive_speed)
        if enemy.body.pos.y >= enemy.home_y:
            enemy.ai_phase = 1
            enemy.ai_timer = 0.0
    enemy.body.pos += enemy.body.velocity * dt


def update_cheep(world: EnemyAIWorld, enemy: Enemy, dt: float) -> None:
    h_speed = 1.8 * TILE_SIZE
    v_speed = 1.05 * TILE_SIZE
    span = 30.0
    if enemy.body.pos.y <= enemy.home_y - span:
        enemy.ai_phase = 1
    elif enemy.body.pos.y >= enemy.home_y + span:
        enemy.ai_phase = 0
    enemy.body.velocity.x = enemy.body.facing * h_speed
    enemy.body.velocity.y = v_speed if enemy.ai_phase == 1 else -v_speed
    enemy.body.pos += enemy.body.velocity * dt


def update_cheep_spawned(world: EnemyAIWorld, enemy: Enemy, dt: float) -> None:
    jd = enemy.ai_timer
    if enemy.ai_phase == 0.0:
        if   jd > 10.0: vy = 15.0
        elif jd >  9.0: vy = 14.0625
        elif jd >  8.0: vy = 13.125
        elif jd >  6.0: vy = 12.1875
        elif jd >  5.0: vy = 10.3125
        elif jd >  4.0: vy =  8.4375
        elif jd >  2.0: vy =  6.5625
        elif jd >  0.0: vy =  4.6875
        else:
            enemy.ai_phase = 1.0
            enemy.ai_timer = 13.0
            vy = 0.0
        enemy.body.velocity.y = -vy * TILE_SIZE
        enemy.ai_timer -= vy * dt
    else:
        if   jd > 11.0: vy =  4.6875
        elif jd >  9.0: vy =  6.5625
        elif jd >  8.0: vy =  8.4375
        elif jd >  7.0: vy = 10.3125
        elif jd >  6.0: vy = 12.1875
        elif jd >  4.0: vy = 13.125
        elif jd >  3.0: vy = 14.0625
        else:            vy = 15.0
        enemy.body.velocity.y = vy * TILE_SIZE
        enemy.ai_timer -= vy * dt
    enemy.body.velocity.x = enemy.home_x * 1.875 * TILE_SIZE
    enemy.body.pos += enemy.body.velocity * dt
    if enemy.body.pos.y > 20.0 * TILE_SIZE:
        enemy.alive = False


def update_podoboo(world: EnemyAIWorld, enemy: Enemy, dt: float) -> None:
    jump_speed = 12.0 * TILE_SIZE   # C++ PodobooBehavior::jump_speed = 12.0 t/s
    gravity = 32.0 * TILE_SIZE      # C++ PodobooBehavior::gravity = 32.0 t/s²
    if enemy.ai_phase == 0:
        enemy.body.pos.y = enemy.home_y
        enemy.ai_timer -= dt
        if enemy.ai_timer <= 0:
            enemy.ai_phase = 1
            enemy.body.velocity.y = -jump_speed
    else:
        enemy.body.velocity.y += gravity * dt
        enemy.body.pos.y += enemy.body.velocity.y * dt
        if enemy.body.velocity.y > 0 and enemy.body.pos.y >= enemy.home_y:
            enemy.body.pos.y = enemy.home_y
            enemy.body.velocity.y = 0.0
            enemy.ai_phase = 0
            enemy.ai_timer = 1.8  # C++ PodobooBehavior::cooldown_duration = 1.8


def update_bullet(world: EnemyAIWorld, enemy: Enemy, dt: float) -> None:
    enemy.body.pos.x += enemy.body.velocity.x * dt
    if (
        enemy.body.pos.x + enemy.body.size.x < world.camera_x - ENEMY_DESPAWN_MARGIN
        or enemy.body.pos.x > world.camera_x + SCREEN_SIZE[0] + ENEMY_DESPAWN_MARGIN
    ):
        enemy.alive = False


def spawn_spiny_drop(world: EnemyAIWorld, lakitu: Enemy) -> None:
    direction = -1 if world.player.pos.x < lakitu.body.pos.x else 1
    spawn_x = (lakitu.body.pos.x + 0.20 * TILE_SIZE * direction) / TILE_SIZE
    spawn_y = (lakitu.body.pos.y + 0.55 * TILE_SIZE) / TILE_SIZE
    spiny = create_enemy(EntitySpawn(type="Spiny", x=spawn_x, y=spawn_y))
    spiny.frames = ("spikey1_0", "spikey1_1")
    spiny.body.velocity.update(direction * 1.7 * TILE_SIZE, -2.0 * TILE_SIZE)
    spiny.ai_timer = 1.4
    spiny.home_x = float(direction)
    world.enemies.append(spiny)


def update_lakitu(world: EnemyAIWorld, enemy: Enemy, dt: float) -> None:
    enemy.ai_phase += dt
    bob_target_y = enemy.home_y + math.sin(enemy.ai_phase * 2.5) * 8.0
    enemy.body.pos.y += (bob_target_y - enemy.body.pos.y) * min(1.0, dt * 7.2)

    player_speed_t = abs(world.player.velocity.x) / TILE_SIZE
    _LEAD_SLOW = 1.3125 * TILE_SIZE
    _LEAD_MEDIUM = 3.0 * TILE_SIZE
    _LEAD_FAST = 4.0 * TILE_SIZE
    slow_t = min(1.0, player_speed_t / 1.0)
    fast_t = min(1.0, max(0.0, (player_speed_t - 1.0) / 3.0))
    target_lead = _LEAD_SLOW + (_LEAD_MEDIUM - _LEAD_SLOW) * slow_t + (_LEAD_FAST - _LEAD_MEDIUM) * fast_t
    enemy.home_x += (target_lead - enemy.home_x) * min(1.0, dt * 4.0)

    if world.player.velocity.x > 0.2 * TILE_SIZE:
        follow_side = 1
    elif world.player.velocity.x < -0.2 * TILE_SIZE:
        follow_side = -1
    else:
        follow_side = 1 if world.player.pos.x >= enemy.body.pos.x else -1

    target_x = world.player.pos.x + follow_side * enemy.home_x
    dx = target_x - enemy.body.pos.x
    abs_dx = abs(dx)

    _DEAD_ZONE = 0.18 * TILE_SIZE
    _CATCHUP_DIST = 4.0 * TILE_SIZE
    _MAX_FOLLOW = 11.0 * TILE_SIZE
    if abs_dx > _DEAD_ZONE:
        base_speed = max(2.2 * TILE_SIZE, abs(world.player.velocity.x) + 0.8 * TILE_SIZE)
        catchup_speed = max(8.0 * TILE_SIZE, abs(world.player.velocity.x) + 2.0 * TILE_SIZE)
        catchup_t = min(1.0, max(0.0, (abs_dx - TILE_SIZE) / (_CATCHUP_DIST - TILE_SIZE)))
        travel_speed = min(base_speed + (catchup_speed - base_speed) * catchup_t, _MAX_FOLLOW)
        desired_vx = travel_speed if dx > 0 else -travel_speed
    else:
        desired_vx = 0.0
    enemy.body.velocity.x += (desired_vx - enemy.body.velocity.x) * min(1.0, dt * 12.0)
    enemy.body.facing = -1 if world.player.pos.x < enemy.body.pos.x else 1
    enemy.body.pos.x += enemy.body.velocity.x * dt

    enemy.ai_timer += dt
    if enemy.ai_timer > 128.0 / 60.0:
        enemy.ai_timer = 0.0
        spawn_spiny_drop(world, enemy)


def throw_hammer(world: EnemyAIWorld, enemy: Enemy) -> None:
    direction = -1 if world.player.pos.x < enemy.body.pos.x else 1
    world.enemy_projectiles.append(
        EnemyProjectile(
            pos=pygame.Vector2(
                enemy.body.pos.x + 0.30 * TILE_SIZE * direction,
                enemy.body.pos.y - 0.45 * TILE_SIZE,
            ),
            velocity=pygame.Vector2(direction * 121.6, -262.4),
            kind="hammer",
            affected_by_gravity=True,
            lifetime=4.0,
        )
    )


def update_hammerbro(world: EnemyAIWorld, enemy: Enemy, dt: float) -> None:
    update_walker(world, enemy, dt)
    if enemy.body.pos.x < enemy.home_x - 0.65 * TILE_SIZE:
        enemy.body.velocity.x = abs(enemy.body.velocity.x or 17.6)
        enemy.body.facing = 1
    elif enemy.body.pos.x > enemy.home_x + 0.65 * TILE_SIZE:
        enemy.body.velocity.x = -abs(enemy.body.velocity.x or 17.6)
        enemy.body.facing = -1
    enemy.ai_timer -= dt
    if enemy.body.on_ground and enemy.ai_timer <= 0:
        js = (12.5 if random.random() < 0.22 else 8.5) * TILE_SIZE
        enemy.body.velocity.y = -js
        enemy.ai_timer = random.uniform(0.9, 1.4)
    enemy.ai_phase += dt
    if enemy.ai_phase > 48.0 / 60.0:
        enemy.ai_phase -= 48.0 / 60.0 + random.uniform(-6.0 / 60.0, 10.0 / 60.0)
        if enemy.ai_phase < 0.0:
            enemy.ai_phase = 0.0
        throw_hammer(world, enemy)


def throw_bowser_hammer(world: EnemyAIWorld, enemy: Enemy) -> None:
    direction = -1 if world.player.pos.x < enemy.body.pos.x else 1
    world.enemy_projectiles.append(
        EnemyProjectile(
            pos=pygame.Vector2(
                enemy.body.pos.x + 0.45 * TILE_SIZE * direction,
                enemy.body.pos.y - 0.8 * TILE_SIZE,
            ),
            velocity=pygame.Vector2(direction * 121.6, -262.4),
            kind="hammer",
            affected_by_gravity=True,
            lifetime=4.0,
        )
    )


def spawn_bowser_fire(world: EnemyAIWorld, enemy: Enemy) -> None:
    direction = -1 if world.player.pos.x < enemy.body.pos.x else 1
    world.enemy_projectiles.append(
        EnemyProjectile(
            pos=pygame.Vector2(
                enemy.body.pos.x + 0.65 * TILE_SIZE * direction,
                enemy.body.pos.y - 0.2 * TILE_SIZE,
            ),
            velocity=pygame.Vector2(direction * 120.0, 0.0),
            kind="bowserfire",
            affected_by_gravity=False,
            lifetime=4.0,
        )
    )
    world.events.append("bowserfire")


def update_bowser(world: EnemyAIWorld, enemy: Enemy, dt: float) -> None:
    update_walker(world, enemy, dt)
    if enemy.body.pos.x <= enemy.home_x - TILE_SIZE * 3:
        enemy.body.velocity.x = abs(enemy.body.velocity.x or 24.0)
        enemy.body.facing = 1
    elif enemy.body.pos.x >= enemy.home_x + TILE_SIZE * 3:
        enemy.body.velocity.x = -abs(enemy.body.velocity.x or 24.0)
        enemy.body.facing = -1
    else:
        desired = 1 if world.player.pos.x >= enemy.body.pos.x else -1
        if desired != enemy.body.facing:
            enemy.body.facing = desired
            enemy.body.velocity.x = desired * 24.0
    if abs(enemy.body.velocity.x) < 0.1:
        enemy.body.velocity.x = enemy.body.facing * 24.0
    enemy.ai_timer -= dt
    if enemy.body.on_ground and enemy.ai_timer <= 0:
        enemy.body.velocity.y = -304.0
        enemy.ai_timer = random.uniform(1.5, 2.8)
    enemy.ai_phase += dt
    if enemy.ai_phase > 1.8:
        active_fires = sum(1 for p in world.enemy_projectiles if p.kind == "bowserfire" and p.alive)
        if active_fires < 1:
            enemy.ai_phase = 1.8 - random.uniform(1.5, 2.9)
            spawn_bowser_fire(world, enemy)
    enemy.home_y -= dt
    if enemy.home_y <= 0:
        interval = 1.4 + random.uniform(-10.0 / 60.0, 8.0 / 60.0)
        enemy.home_y = max(28.0 / 60.0, interval)
        throw_bowser_hammer(world, enemy)


def update_enemy_projectiles(world: EnemyAIWorld, dt: float) -> None:
    kept: list[EnemyProjectile] = []
    for proj in world.enemy_projectiles:
        if not proj.alive:
            continue
        proj.age += dt
        if proj.affected_by_gravity:
            proj.velocity.y = min(proj.velocity.y + HAMMER_GRAVITY * dt, 14.0 * TILE_SIZE)
        proj.pos.x += proj.velocity.x * dt
        proj.pos.y += proj.velocity.y * dt
        if proj.kind == "hammer":
            for tile in world.collider.nearby(proj.rect):
                if proj.rect.colliderect(tile):
                    if proj.velocity.y > 0:
                        proj.alive = False
                    break
        if proj.age > proj.lifetime:
            proj.alive = False
        elif (
            proj.pos.x < world.camera_x - ENEMY_DESPAWN_MARGIN
            or proj.pos.x > world.camera_x + SCREEN_SIZE[0] + ENEMY_DESPAWN_MARGIN
        ):
            proj.alive = False
        if proj.alive:
            kept.append(proj)
    world.enemy_projectiles = kept
