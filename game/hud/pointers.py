"""game/hud/pointers.py — общая геометрия указателей: проекция на рамку экрана и треугольник."""
import math
import pygame

from engine import clamp
from ui.ammo_bar import occupied_corner
from ui.upgrade_bar import right_zone

CLEARANCE = 12          # зазор до интерфейса, px

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

def avoid_interface(w, h, px, py, size, inset):
    """Точку px, py на рамке экрана (отступ inset), занятую интерфейсом, сдвигает вдоль рамки.
    Учитываются левый нижний угол (сводка и ряд снарядов) и панель улучшений у правой стороны.
    size: размер самого указателя, нужен для зазора."""
    pad = size + CLEARANCE

    right, top = occupied_corner(h)
    if px < right + pad and py > top - pad:
        free_y = max(inset, top - pad)                      # куда подняться вдоль левой стороны
        free_x = min(w - inset, right + pad)                # куда уехать вдоль нижней стороны
        on_left = px <= inset + 1.0
        on_bottom = py >= h - inset - 1.0
        if on_left and on_bottom:                           # угол: идём туда, где короче
            if py - free_y <= free_x - px:
                py = free_y
            else:
                px = free_x
        elif on_left:
            py = free_y
        elif on_bottom:
            px = free_x

    zone = right_zone((w, h))
    in_x = px > zone.left - pad
    in_y = zone.top - pad < py < zone.bottom + pad
    if in_x and in_y:
        if py >= h - inset - 1.0:                    # на нижней кромке: уезжаем влево от панели
            px = max(inset, zone.left - pad)
        elif px >= w - inset - 1.0:                  # на правой кромке: поднимаемся выше панели
            py = max(inset, zone.top - pad)
    return px, py