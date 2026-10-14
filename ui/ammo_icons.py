"""ui/ammo_icons.py — процедурные иконки снарядов для кнопок выбора."""
import pygame

from engine import AmmoKind, AMMO_COLORS

SS = 4                      # рисуем в SS раз крупнее, затем smoothscale
OUTLINE = (30, 26, 22)

def make_ammo_icon(kind, size):
    """Готовая поверхность size = (w, h) с иконкой снаряда kind (остриём вправо)."""
    w, h = size
    W, H = w * SS, h * SS
    cy = H / 2.0
    big = pygame.Surface((W, H), pygame.SRCALPHA)
    body, light, tip = AMMO_COLORS[kind]

    def poly(color, pts):
        pygame.draw.polygon(big, color, pts)
        pygame.draw.polygon(big, OUTLINE, pts, SS)

    def rect(color, x0, x1, half):
        """Прямоугольник от x0 до x1 (доли ширины), полутолщина half (доли высоты)."""
        r = pygame.Rect(round(x0 * W), round(cy - half * H), round((x1 - x0) * W), round(2 * half * H))
        pygame.draw.rect(big, color, r)
        pygame.draw.rect(big, OUTLINE, r, SS)

    if kind is AmmoKind.AP:                       # тонкий дротик с острым наконечником и оперением
        for s in (-1, 1):
            poly(tip, [(0.06 * W, cy + s * 0.15 * H), (0.02 * W, cy + s * 0.40 * H),
                       (0.22 * W, cy + s * 0.15 * H)])
        rect(body, 0.04, 0.60, 0.15)
        poly(tip, [(0.60 * W, cy - 0.15 * H), (0.97 * W, cy), (0.60 * W, cy + 0.15 * H)])
        pygame.draw.line(big, light, (0.12 * W, cy - 0.06 * H), (0.56 * W, cy - 0.06 * H), SS)
    elif kind is AmmoKind.HEAT:                   # конус с широким основанием и воронкой в носу
        rect(body, 0.06, 0.38, 0.30)
        poly(body, [(0.38 * W, cy - 0.30 * H), (0.90 * W, cy - 0.10 * H),
                    (0.90 * W, cy + 0.10 * H), (0.38 * W, cy + 0.30 * H)])
        rect(tip, 0.90, 0.98, 0.10)               # воронка
        rect(tip, 0.06, 0.12, 0.30)               # донный поясок
        pygame.draw.line(big, light, (0.16 * W, cy - 0.18 * H), (0.70 * W, cy - 0.10 * H), SS)
    else:                                         # фугас: короткий толстый снаряд с поясом
        rect(body, 0.06, 0.70, 0.28)
        poly(body, [(0.70 * W, cy - 0.28 * H), (0.84 * W, cy - 0.20 * H), (0.96 * W, cy),
                    (0.84 * W, cy + 0.20 * H), (0.70 * W, cy + 0.28 * H)])
        rect(tip, 0.40, 0.48, 0.28)               # ведущий поясок
        pygame.draw.line(big, light, (0.12 * W, cy - 0.15 * H), (0.36 * W, cy - 0.15 * H), SS)

    return pygame.transform.smoothscale(big, (w, h))