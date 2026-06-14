from __future__ import annotations

from typing import Protocol

import pygame

from .enemy import ENEMY_DEAD_FRAMES, ENEMY_FRAMES
from .entities import (
    Collectible,
    Enemy,
    EnemyProjectile,
    FireBar,
    Fireball,
    FallingPlatform,
    MovingPlatform,
    Player,
    SeesawPlatform,
    ShellState,
    UpFire,
)
from .physics import TileCollider
from .settings import SHELL_WAKE_TIME, TILE_SIZE

__all__ = ["TileCollider", "handle_entity_collisions", "handle_platform_collisions", "update_platforms"]


class CollisionWorld(Protocol):
    player: Player
    enemies: list[Enemy]
    fireballs: list[Fireball]
    enemy_projectiles: list[EnemyProjectile]
    collectibles: list[Collectible]
    upfires: list[UpFire]
    firebars: list[FireBar]
    events: list[str]

    def _award_combo_score(self, x: int, y: int) -> None: ...
    def _collect(self, collectible: Collectible) -> None: ...
    def _convert_to_shell(self, enemy: Enemy) -> None: ...
    def _kick_shell(self, enemy: Enemy, direction: int) -> None: ...
    def _kill_enemy(
        self,
        enemy: Enemy,
        score: int,
        popup_x: int,
        popup_y: int,
        launch_vy: float = ...,
        stomp_squish: bool = ...,
    ) -> None: ...
    def _kill_player(self) -> None: ...
    def _take_damage(self) -> None: ...


def handle_entity_collisions(world: CollisionWorld) -> None:
    player_rect = world.player.rect

    if world.player.invincible_timer <= 0 and world.player.star_timer <= 0:
        for fire in world.upfires:
            if fire.state != 0 and player_rect.colliderect(fire.rect):
                world._kill_player()
                return
        for bar in world.firebars:
            for pos in bar.segment_positions:
                if player_rect.colliderect(pygame.Rect(round(pos.x) - 7, round(pos.y) - 7, 14, 14)):
                    world._kill_player()
                    return

    for enemy in world.enemies:
        if not enemy.alive or not player_rect.colliderect(enemy.body.rect):
            continue
        # C++ isStompingEnemy: vy > 0.5 t/s (16px/s), player bottom above enemy center,
        # and feet within [-0.1t, 0.4t] = [-3.2, 12.8] px of enemy top.
        _feet_to_top = player_rect.bottom - enemy.body.rect.top
        from_above = (
            world.player.velocity.y > 16.0
            and player_rect.bottom < enemy.body.rect.centery
            and -3.2 <= _feet_to_top <= 12.8
        )

        if world.player.star_timer > 0:
            if not enemy.star_immune:
                world._kill_enemy(
                    enemy,
                    score=0,
                    popup_x=enemy.body.rect.x,
                    popup_y=enemy.body.rect.y,
                    launch_vy=-320.0,
                )
                world._award_combo_score(enemy.body.rect.x, enemy.body.rect.y)
                world.events.append("stomp")
            continue

        if enemy.shell_state is ShellState.SHELL_STILL:
            if from_above:
                world.player.velocity.y = -19.0 * TILE_SIZE  # C++ stomp_bounce = 19.0 t/s × 32
                # C++ kickShell: direction = (player_x < enemy_x) ? 1 : -1 (kick away from player)
                world._kick_shell(enemy, direction=1 if world.player.pos.x < enemy.body.pos.x else -1)
            else:
                world._kick_shell(enemy, direction=1 if world.player.pos.x < enemy.body.pos.x else -1)
            continue
        if enemy.shell_state is ShellState.SHELL_KICKED:
            if from_above:
                world.player.velocity.y = -19.0 * TILE_SIZE  # C++ stomp_bounce = 19.0 t/s × 32
                enemy.shell_state = ShellState.SHELL_STILL
                enemy.shell_wake_timer = SHELL_WAKE_TIME
                enemy.body.velocity.update(0.0, 0.0)
                enemy.kick_streak = 0
                world.events.append("stomp")  # C++ enterStationaryShell → PlaySoundEvent "stomp"
            elif enemy.kick_grace <= 0 and world.player.invincible_timer <= 0:
                world._take_damage()
                return
            continue

        if from_above and enemy.stompable:
            world.player.velocity.y = -19.0 * TILE_SIZE  # C++ stomp_bounce = 19.0 t/s × 32
            if enemy.winged:
                enemy.winged = False
                enemy.frames = ENEMY_FRAMES.get(
                    "RedKoopa" if enemy.kind == "RedParaKoopa" else "KoopaTroopa",
                    enemy.frames,
                )
            elif enemy.gives_shell:
                world._convert_to_shell(enemy)
            else:
                dead_frame = ENEMY_DEAD_FRAMES.get(enemy.kind)
                squish = bool(dead_frame)
                launch_vy = 0.0 if squish else -9.0 * TILE_SIZE
                world._kill_enemy(
                    enemy,
                    score=0,
                    popup_x=enemy.body.rect.x,
                    popup_y=enemy.body.rect.y,
                    stomp_squish=squish,
                    launch_vy=launch_vy,
                )
                if squish:
                    # C++ handleStomp: awardComboScore only for EnemyDeath::Stomped (Goomba);
                    # non-flattenable enemies (HammerBro, CheepCheep, etc.) early-return before it.
                    world._award_combo_score(enemy.body.rect.x, enemy.body.rect.y)
            world.events.append("stomp")
        elif world.player.invincible_timer > 0:
            continue
        else:
            world._take_damage()
            return

    for fireball in world.fireballs:
        if not fireball.alive:
            continue
        for enemy in world.enemies:
            if not enemy.alive or not fireball.rect.colliderect(enemy.body.rect):
                continue
            if enemy.fire_immune:
                fireball.alive = False
                fireball.explode_timer = 0.15
                world.events.append("blockhit")
                break
            if enemy.kind == "Bowser":
                fireball.alive = False
                fireball.explode_timer = 0.15
                enemy.fireball_hits += 1
                if enemy.fireball_hits >= 5:
                    world._kill_enemy(enemy, score=5000, popup_x=enemy.body.rect.x, popup_y=enemy.body.rect.y)
                    world.events.append("bowserfall")
                break
            world._kill_enemy(enemy, score=200, popup_x=enemy.body.rect.x, popup_y=enemy.body.rect.y)
            fireball.alive = False
            fireball.explode_timer = 0.15
            world.events.append("fireball")
            break

    for proj in world.enemy_projectiles:
        if not proj.alive or not player_rect.colliderect(proj.rect):
            continue
        if world.player.star_timer > 0:
            if proj.kind == "hammer":
                proj.alive = False
            continue
        if world.player.invincible_timer > 0:
            continue
        proj.alive = False
        world._take_damage()
        return

    kept_collectibles: list[Collectible] = []
    for collectible in world.collectibles:
        if collectible.emerge_remaining <= 0 and player_rect.colliderect(collectible.rect):
            world._collect(collectible)
        else:
            kept_collectibles.append(collectible)
    world.collectibles = kept_collectibles


class PlatformWorld(Protocol):
    player: Player
    moving_platforms: list[MovingPlatform]
    falling_platforms: list[FallingPlatform]
    seesaw_platforms: list[SeesawPlatform]
    on_platform: object


def update_platforms(world: PlatformWorld, dt: float) -> None:
    for p in world.moving_platforms:
        old_pos = pygame.Vector2(p.pos)
        dist = p.start_pos.distance_to(p.end_pos)
        if dist > 0:
            effective_speed = p.speed
            if p.ease_endpoints and p.ease_distance > 0.0:
                t_ease = (p.ease_distance * TILE_SIZE) / dist
                if p.t < t_ease or (1.0 - p.t) < t_ease:
                    effective_speed *= 0.5

            p.t += (effective_speed / dist) * dt * p.direction
            if p.t >= 1.0:
                p.t = 1.0
                p.direction = -1
            elif p.t <= 0.0:
                p.t = 0.0
                p.direction = 1

            p.pos = p.start_pos.lerp(p.end_pos, p.t)

        p.delta_pos = p.pos - old_pos

    for p in world.falling_platforms:
        old_pos = pygame.Vector2(p.pos)
        if p.has_player:
            p.pos.y += p.fall_speed * dt
        p.delta_pos = p.pos - old_pos

    processed_seesaws: set[int] = set()
    for i, p in enumerate(world.seesaw_platforms):
        if i in processed_seesaws:
            continue
        partner = world.seesaw_platforms[p.partner_idx]
        processed_seesaws.add(i)
        processed_seesaws.add(p.partner_idx)

        old_pos_p = pygame.Vector2(p.pos)
        old_pos_partner = pygame.Vector2(partner.pos)

        if p.falling:
            p.pos.y += p.fall_speed * dt
            partner.pos.y += partner.fall_speed * dt
        else:
            if p.has_player and not partner.has_player:
                move = p.tilt_speed * dt
                p.pos.y += move
                partner.pos.y -= move
            elif not p.has_player and partner.has_player:
                move = partner.tilt_speed * dt
                partner.pos.y += move
                p.pos.y -= move

            if abs(p.pos.y - p.y_neutral) > p.drop_threshold:
                p.falling = True
                partner.falling = True

        p.delta_pos = p.pos - old_pos_p
        partner.delta_pos = partner.pos - old_pos_partner


def handle_platform_collisions(world: PlatformWorld) -> None:
    player_rect = world.player.rect

    for p in world.falling_platforms:
        p.has_player = False
    for p in world.seesaw_platforms:
        p.has_player = False

    new_on_platform: object = None
    all_platforms = (*world.moving_platforms, *world.falling_platforms, *world.seesaw_platforms)

    for p in all_platforms:
        plat_rect = p.rect
        if (
            world.player.velocity.y >= 0
            and player_rect.right > plat_rect.left
            and player_rect.left < plat_rect.right
            and player_rect.bottom <= plat_rect.top + 10
            and player_rect.bottom >= plat_rect.top - 5
        ):
            world.player.pos.y = plat_rect.top - world.player.size.y
            world.player.velocity.y = 0
            world.player.on_ground = True
            new_on_platform = p

            if isinstance(p, (FallingPlatform, SeesawPlatform)):
                p.has_player = True
            break

    world.on_platform = new_on_platform
