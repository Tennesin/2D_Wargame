"""ai/cover.py — укрытия: поиск места, закрытого от врага камнем или стеной, и «куда смотрит игрок»."""
import math

from engine import PX_PER_M, shortest_angle_diff
from .steering import bearing_deg

# --- поиск ---
RINGS_M = (10.0, 18.0, 26.0)      # кольца вокруг бота, на которых пробуем точки
RING_POINTS = 12
MIN_ENEMY_M = 12.0                # ближе к врагу укрытие не ищем
MAX_ENEMY_M = 45.0                # дальше тоже (нам ещё возвращаться в бой)
LATERAL_M = 1.6                   # корпус целиком должен быть закрыт: проверяем центр и оба борта
WALL_MIN_SHOTS = 1.5              # стена слабее полутора выстрелов врага не укрытие
BAD_RADIUS_M = 8.0                # вокруг «плохих» точек не ищем
FAR_PENALTY = 12.0                # штраф за препятствие близко к врагу, а не к нам
CLOSE_ENEMY_M = 16.0
CLOSE_PENALTY = 8.0

# --- внимание игрока ---
ATTN_ME_DEG = 25.0                # башня игрока смотрит на меня, если отклонение не больше
ATTN_OTHER_DEG = 18.0             # то же для другого бота

def _first_block(ctx, enemy, ax, ay, bx, by):
    """Доля пути t до первого препятствия, которое остановит снаряд (камень или живая стена), или None."""
    best = None
    hit = ctx.terrain.raycast(ax, ay, bx, by)
    if hit is not None:
        best = hit[1]
    hit = ctx.walls.raycast(ax, ay, bx, by)
    if hit is not None:
        wall, t, _ = hit
        if wall.alive and wall.hp > enemy.spec.damage * WALL_MIN_SHOTS and (best is None or t < best):
            best = t
    return best

def shield_between(ctx, enemy, x, y, lateral_px=LATERAL_M * PX_PER_M):
    """Закрыта ли точка (x, y) от врага целиком (центр и оба борта).
    Возвращает наименьшую долю пути до препятствия (чем ближе к 1, тем ближе препятствие к нам)
    или None, если хотя бы один луч свободен."""
    dx, dy = x - enemy.x, y - enemy.y
    ln = math.hypot(dx, dy)
    if ln < 1.0:
        return None
    px, py = -dy / ln * lateral_px, dx / ln * lateral_px
    worst = 1.0
    for k in (0.0, 1.0, -1.0):
        t = _first_block(ctx, enemy, enemy.x, enemy.y, x + px * k, y + py * k)
        if t is None:
            return None
        worst = min(worst, t)
    return worst

def find_cover(me, enemy, ctx, avoid=()):
    """Лучшее укрытие рядом с ботом: (x, y) или None. avoid — [[x, y, ttl], ...] плохие точки."""
    best, best_score = None, None
    bad_r2 = (BAD_RADIUS_M * PX_PER_M) ** 2
    for ring in RINGS_M:
        r = ring * PX_PER_M
        for k in range(RING_POINTS):
            a = 2.0 * math.pi * k / RING_POINTS
            px, py = me.x + math.cos(a) * r, me.y + math.sin(a) * r
            if any((px - bx) ** 2 + (py - by) ** 2 < bad_r2 for bx, by, _ in avoid):
                continue
            d_enemy = math.hypot(px - enemy.x, py - enemy.y) / PX_PER_M
            if not (MIN_ENEMY_M <= d_enemy <= MAX_ENEMY_M):
                continue
            heading = bearing_deg(px, py, enemy.x, enemy.y)
            hull = me.footprint_at(px, py, heading)[0]
            if ctx.terrain.blocks_obb(hull) or ctx.walls.blocks_obb(hull):
                continue                                          # место занято
            if ctx.terrain.speed_factor(px, py) < 0.99:
                continue                                          # не прячемся в воде и грязи
            t = shield_between(ctx, enemy, px, py)                # самая дорогая проверка идёт последней
            if t is None:
                continue
            score = ring + FAR_PENALTY * (1.0 - t) + (CLOSE_PENALTY if d_enemy < CLOSE_ENEMY_M else 0.0)
            if best_score is None or score < best_score:
                best, best_score = (px, py), score
    return best

def _off_axis(player, target):
    """Насколько башня игрока отклонена от направления на target, градусы."""
    bearing = bearing_deg(player.x, player.y, target.x, target.y)
    return abs(shortest_angle_diff(bearing, player.turret_angle))

def attention(player, me, others):
    """Куда смотрит башня игрока: "me" (на меня), "other" (на другого бота) или "none"."""
    if _off_axis(player, me) <= ATTN_ME_DEG:
        return "me"
    for t in others:
        if t is not me and t.alive and _off_axis(player, t) <= ATTN_OTHER_DEG:
            return "other"
    return "none"