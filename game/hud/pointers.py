"""game/hud/pointers.py — общая геометрия указателей: проекция на рамку экрана и треугольник."""
import math
import pygame

def edge_point(width, height, sx, sy, inset):
    """Точка на рамке экрана (с отступом inset), в которую упирается луч от центра экрана к (sx, sy).
    Работает и для точки внутри экрана: указатель всё равно ставится у рамки по направлению.
    Возвращает (x, y, угол в радианах)."""
    cx, cy = width / 2.0, height / 2.0
    hx, hy = max(1.0, cx - inset), max(1.0, cy - inset)
    dx, dy = sx - cx, sy - cy
    if not dx and not dy:
        dx = 1.0
    kx = hx / abs(dx) if dx else float("inf")
    ky = hy / abs(dy) if dy else float("inf")
    k = min(kx, ky)
    return cx + dx * k, cy + dy * k, math.atan2(dy, dx)

def draw_triangle(screen, x, y, ang, size, fill, outline, width=2):
    """Равнобедренный треугольник с остриём в направлении ang (радианы, экранные оси)."""
    ux, uy = math.cos(ang), math.sin(ang)
    vx, vy = -uy, ux
    tip = (x + ux * size, y + uy * size)
    b1 = (x - ux * size * 0.6 + vx * size * 0.7, y - uy * size * 0.6 + vy * size * 0.7)
    b2 = (x - ux * size * 0.6 - vx * size * 0.7, y - uy * size * 0.6 - vy * size * 0.7)
    pygame.draw.polygon(screen, fill, (tip, b1, b2))
    pygame.draw.polygon(screen, outline, (tip, b1, b2), width)

def marker_lift_px(tank, zoom):
    """На сколько экранных px выше центра техники стоит её указатель.
    Общая высота для синего маркера бота и для линии оглушения."""
    return (tank.spec.COLLISION_HALF_L_PX + 60.0) * zoom + 10.0