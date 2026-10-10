"""ai/gunnery.py — упреждение, оценка урона по граням, точка фланга."""
import math

from engine import heading_vector

def lead_point(shooter, target, lead_k=1.0):
    """Точка упреждения: где будет цель, когда долетит снаряд. Две итерации."""
    sx, sy = shooter.muzzle_point()
    speed = shooter.spec.SHELL_SPEED_PX
    vx, vy = target.velocity_px()
    px, py = target.x, target.y
    for _ in range(2):
        t = math.hypot(px - sx, py - sy) / speed
        px = target.x + vx * t * lead_k
        py = target.y + vy * t * lead_k
    return px, py

def damage_by_aspect(me, enemy):
    """Доля урона моего снаряда при прямом ударе (cos = 1) по лбу, борту и корме врага."""
    fx, fy = heading_vector(enemy.hull_angle)
    rx, ry = -fy, fx
    pen = me.spec.penetration
    return {
        "front": enemy.hit_result(pen, 1.0, (fx, fy)).damage_frac,
        "side": enemy.hit_result(pen, 1.0, (rx, ry)).damage_frac,
        "rear": enemy.hit_result(pen, 1.0, (-fx, -fy)).damage_frac,
    }

def flank_point(enemy, dist_px, side):
    """Точка за бортом (слегка в сторону кормы) цели на заданной дистанции. side: +1 / -1."""
    fx, fy = heading_vector(enemy.hull_angle)
    rx, ry = -fy, fx
    return (enemy.x + (rx * side * 0.8 - fx * 0.6) * dist_px,
            enemy.y + (ry * side * 0.8 - fy * 0.6) * dist_px)