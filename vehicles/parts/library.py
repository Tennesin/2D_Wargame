"""vehicles/parts/library.py — типы деталей и функции их рисования (код перенесён из HullPartsMixin и TankRenderer).
Каждая функция рисует в локальных метрах: начало в (part.x, part.y).
ВРЕМЕННО: константы швов дублируют vehicles/render/hull_parts.py; после этапа 1б там их удалим."""
from vehicles.render.pen import apply_paint, HULL_DARK, GRILL, GRILL_LINE
from .model import SURFACE_HULL
from .registry import part_type

TOOLBOX = (132, 124, 106)           # ящики ЗИП
CABLE = (66, 60, 52)                # буксирный трос

SEAM_FRACS = (0.30, 0.62)           # где на палубе идут поперечные швы (доли длины палубы)
SEAM_W_M = 0.05                     # толщина шва, м
RIVET_R_M = 0.04                    # радиус заклёпки, м
RIVET_STEP_M = 0.5                  # примерный шаг заклёпок вдоль шва, м

HULL = (SURFACE_HULL,)

@part_type("hatch", "Люк", surfaces=HULL, z=70, w=(0.12, 0.50))
def draw_hatch(p, part, ctx):
    """w: радиус."""
    r = part.w
    p.ellipse(apply_paint(HULL_DARK, ctx.paint), 0.0, 0.0, r, r)

@part_type("grill", "Решётка МТО", surfaces=HULL, z=70, w=(0.30, 2.40), h=(0.20, 2.00))
def draw_grill(p, part, ctx):
    """Решётка с жалюзи. Начало: левый верхний угол."""
    p.rect(GRILL, 0.0, 0.0, part.w, part.h)
    y = 0.30
    while y < part.h - 0.10:
        p.line(GRILL_LINE, 0.15, y, part.w - 0.15, y, 0.05)
        y += 0.25

@part_type("plate", "Плита", surfaces=HULL, z=70, w=(0.20, 3.00), h=(0.10, 1.00))
def draw_plate(p, part, ctx):
    """Прямоугольная плита цвета корпуса (кормовая). Начало: левый верхний угол."""
    p.rect(apply_paint(HULL_DARK, ctx.paint), 0.0, 0.0, part.w, part.h)

@part_type("exhaust", "Выхлоп", surfaces=HULL, z=70, w=(0.06, 0.30))
def draw_exhaust(p, part, ctx):
    """w: радиус патрубка."""
    p.ellipse(GRILL, 0.0, 0.0, part.w, part.w)

@part_type("seam", "Шов", surfaces=HULL, z=30, w=(0.30, 3.00))
def draw_seam(p, part, ctx):
    """Поперечный шов с рядом заклёпок. Начало: левый конец. w: длина."""
    color = apply_paint(HULL_DARK, ctx.paint)
    p.line(color, 0.0, 0.0, part.w, 0.0, SEAM_W_M)
    n = max(2, round(part.w / RIVET_STEP_M))
    for i in range(1, n):
        p.ellipse(color, part.w * i / n, 0.11, RIVET_R_M, RIVET_R_M, outline=None)

@part_type("engine_cover", "Моторная крышка", surfaces=HULL, z=50, w=(0.60, 3.00), h=(0.60, 4.00))
def draw_engine_cover(p, part, ctx):
    """Рама, решётка, жалюзи и (у длинной) поперечная перегородка. Начало: левый верхний угол."""
    w, h = part.w, part.h
    dark = apply_paint(HULL_DARK, ctx.paint)
    p.rect(dark, 0.0, 0.0, w, h, r=0.05)
    p.rect(GRILL, 0.15, 0.12, w - 0.30, h - 0.24)
    y = 0.32
    while y < h - 0.20:
        p.line(GRILL_LINE, 0.29, y, w - 0.29, y, 0.05)
        y += 0.26
    if h >= 2.2:
        p.rect(dark, 0.15, h / 2.0 - 0.05, w - 0.30, 0.10, outline=None)

@part_type("toolbox", "Ящик ЗИП", surfaces=HULL, z=70, w=(0.15, 0.60), h=(0.20, 1.20))
def draw_toolbox(p, part, ctx):
    """Начало: левый верхний угол."""
    p.rect(apply_paint(TOOLBOX, ctx.paint), 0.0, 0.0, part.w, part.h, r=0.04)

@part_type("cable", "Трос", surfaces=HULL, z=70, h=(0.30, 5.00))
def draw_cable(p, part, ctx):
    """Вертикальная линия вдоль корпуса. Начало: передний конец. h: длина."""
    p.line(CABLE, 0.0, 0.0, 0.0, part.h, 0.07)