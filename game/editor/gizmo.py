"""game/editor/gizmo.py — «рукоятка» объекта."""
import math

import pygame

from engine import shortest_angle_diff

DOT_R = 6                    # радиус белой точки
DOT_HIT_PX = 12              # в этом радиусе точку можно схватить
ARC_MIN_R = 30               # дуги не ближе этого к центру
ARC_GAP = 14                 # зазор между габаритом и дугами
ARC_SPAN_DEG = 70            # угловая длина одной дуги
ARC_HIT_PX = 9               # допуск захвата дуги по радиусу
ARC_W = 3

WHITE = (255, 255, 255)
EDGE = (30, 30, 34)
HOT = (255, 220, 80)

def arc_radius(extent_px):
    """Радиус дуг для объекта, у которого половина диагонали габарита extent_px."""
    return max(ARC_MIN_R, extent_px + ARC_GAP)

def hit(cx, cy, radius, angle_deg, pos):
    """Что под курсором: "move" (точка), "rotate" (одна из двух дуг) или None.
    angle_deg: направление объекта по часовой, как в игре; дуги лежат справа и слева от него."""
    dx, dy = pos[0] - cx, pos[1] - cy
    d = math.hypot(dx, dy)
    if d <= DOT_HIT_PX:
        return "move"
    if abs(d - radius) <= ARC_HIT_PX:
        phi = math.degrees(math.atan2(dy, dx))
        for base in (angle_deg, angle_deg + 180.0):
            if abs(shortest_angle_diff(phi, base)) <= ARC_SPAN_DEG / 2.0 + 4.0:
                return "rotate"
    return None

def _arc_points(cx, cy, radius, center_deg, n=12):
    pts = []
    for i in range(n + 1):
        a = math.radians(center_deg - ARC_SPAN_DEG / 2.0 + ARC_SPAN_DEG * i / n)
        pts.append((cx + radius * math.cos(a), cy + radius * math.sin(a)))
    return pts

def draw(screen, cx, cy, radius, angle_deg, hover=None, active=None):
    """Рисует точку и дуги. Подсвечивается то, над чем курсор или что сейчас тянут."""
    mode = active or hover
    for base in (angle_deg, angle_deg + 180.0):
        pts = _arc_points(cx, cy, radius, base)
        pygame.draw.lines(screen, EDGE, False, pts, ARC_W + 3)
        pygame.draw.lines(screen, HOT if mode == "rotate" else WHITE, False, pts, ARC_W)
    center = (round(cx), round(cy))
    pygame.draw.circle(screen, HOT if mode == "move" else WHITE, center, DOT_R)
    pygame.draw.circle(screen, EDGE, center, DOT_R, 1)