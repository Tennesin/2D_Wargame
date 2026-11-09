"""vehicles/parts/library.py — типы деталей и функции их рисования."""
from vehicles.render.pen import (
    apply_paint, OUTLINE, HULL_DARK, GRILL, GRILL_LINE,
    TURRET_MAIN, TURRET_DARK, GUN_LIGHT, GUN_DARK, EMBLEM_COLOR,
)
from .model import SURFACE_HULL, SURFACE_TURRET, SURFACE_BARREL
from .registry import part_type

TOOLBOX = (132, 124, 106)           # ящики ЗИП
CRATE = (132, 124, 106)             # ящики боекомплекта САУ
CABLE = (66, 60, 52)                # буксирный трос

SEAM_FRACS = (0.30, 0.62)           # где на палубе идут поперечные швы (доли длины палубы)
SEAM_W_M = 0.05                     # толщина шва, м
RIVET_R_M = 0.04                    # радиус заклёпки, м
RIVET_STEP_M = 0.5                  # примерный шаг заклёпок вдоль шва, м

# двойной шеврон острием вперёд (Уничтожитель), метры эталонной башни
CHEVRON = [(0.00, -0.95), (0.40, -0.55), (0.40, -0.38), (0.00, -0.78), (-0.40, -0.38), (-0.40, -0.55)]

HULL = (SURFACE_HULL,)
TURRET = (SURFACE_TURRET,)
BARREL = (SURFACE_BARREL,)
ROOF = (SURFACE_HULL, SURFACE_TURRET)

# ==========================================
# КОРПУС: общие детали
# ==========================================

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

# ==========================================
# КОРПУС: детали ПТ-САУ и САУ (этап 1b)
# ==========================================

@part_type("handle", "Ручка ящика", surfaces=HULL, z=70, h=(0.20, 1.50))
def draw_handle(p, part, ctx):
    """Тонкая линия вдоль корпуса. Начало: передний конец. h: длина."""
    p.line(GRILL_LINE, 0.0, 0.0, 0.0, part.h, 0.04)

@part_type("clamp", "Скоба троса", surfaces=HULL, z=70, w=(0.05, 0.40), h=(0.05, 0.40))
def draw_clamp(p, part, ctx):
    """Маленький прямоугольник без контура. Начало: левый верхний угол."""
    p.rect(GRILL, 0.0, 0.0, part.w, part.h, outline=None)

@part_type("vent_grille", "Решётка МТО с вентиляторами", surfaces=HULL, z=45, w=(0.60, 2.40), h=(0.60, 3.00))
def draw_vent_grille(p, part, ctx):
    """Моторная решётка позади рубки. Начало: левый верхний угол. variant 1: два вентилятора сверху,
    жалюзи ниже них; variant 0: только жалюзи."""
    w, h = part.w, part.h
    p.rect(GRILL, 0.0, 0.0, w, h)
    y = 0.20
    if part.variant == 1:
        for fx in (w / 2.0 - 0.48, w / 2.0 + 0.48):
            p.ellipse(GRILL_LINE, fx, 0.62, 0.34, 0.34)
            p.ellipse(GRILL, fx, 0.62, 0.20, 0.20)
        y = 1.15
    while y < h - 0.10:
        p.line(GRILL_LINE, 0.15, y, w - 0.15, y, 0.05)
        y += 0.25

@part_type("roof_seam", "Шов крыши", surfaces=ROOF, z=25, w=(0.30, 3.00))
def draw_roof_seam(p, part, ctx):
    """Тёмная линия поперёк крыши. Начало: левый конец. w: длина."""
    p.line(apply_paint(TURRET_DARK, ctx.paint), 0.0, 0.0, part.w, 0.0, 0.04)

@part_type("breech_tray", "Лоток казённика", surfaces=HULL, z=61, w=(0.64, 3.00), h=(0.30, 1.50))
def draw_breech_tray(p, part, ctx):
    """Трапеция хода казённика. Начало: середина переднего края. w: ширина заднего края
    (передний всегда 0.64), h: длина вдоль корпуса."""
    t = (part.w - 0.64) / 2.0
    p.poly(apply_paint(TURRET_DARK, ctx.paint),
           [(-0.32, 0.0), (0.32, 0.0), (0.32 + t, part.h), (-0.32 - t, part.h)], outline=None)

@part_type("embrasure", "Амбразура", surfaces=HULL, z=62, w=(0.60, 2.40), h=(0.30, 0.80))
def draw_embrasure(p, part, ctx):
    """Трапеция у передней грани рубки. Начало: середина переднего края. w: ширина переднего края,
    задний уже на 0.4 м. h: глубина."""
    ew = part.w / 2.0
    p.poly(apply_paint(TURRET_DARK, ctx.paint),
           [(-ew, 0.0), (ew, 0.0), (ew - 0.20, part.h), (-(ew - 0.20), part.h)], outline=None)

@part_type("periscope", "Перископ", surfaces=HULL, z=63, w=(0.10, 0.60), h=(0.05, 0.30))
def draw_periscope(p, part, ctx):
    """Начало: левый верхний угол."""
    p.rect(apply_paint(TURRET_DARK, ctx.paint), 0.0, 0.0, part.w, part.h, r=0.02)

@part_type("dome", "Купол командира", surfaces=HULL, z=64, w=(0.10, 0.50), h=(0.05, 0.40))
def draw_dome(p, part, ctx):
    """w: радиус тёмного кольца, h: радиус светлой середины."""
    p.ellipse(apply_paint(TURRET_DARK, ctx.paint), 0.0, 0.0, part.w, part.w)
    p.ellipse(apply_paint(TURRET_MAIN, ctx.paint), 0.0, 0.0, part.h, part.h, outline=None)

@part_type("roof_hatch", "Люк заряжающего", surfaces=HULL, z=65, w=(0.15, 0.80), h=(0.15, 0.80))
def draw_roof_hatch(p, part, ctx):
    """Начало: левый верхний угол."""
    p.rect(apply_paint(TURRET_DARK, ctx.paint), 0.0, 0.0, part.w, part.h, r=0.03)

@part_type("vent", "Вентрешётка", surfaces=HULL, z=66, w=(0.30, 1.20), h=(0.30, 0.60))
def draw_vent(p, part, ctx):
    """Решётка с двумя щелями. Начало: левый верхний угол."""
    p.rect(GRILL, 0.0, 0.0, part.w, part.h)
    for y in (0.12, 0.24):
        p.line(GRILL_LINE, 0.07, y, part.w - 0.07, y, 0.04)

@part_type("ammo_crate", "Ящик боекомплекта", surfaces=HULL, z=66, w=(0.20, 1.00), h=(0.20, 1.00))
def draw_ammo_crate(p, part, ctx):
    """Начало: левый верхний угол."""
    p.rect(apply_paint(CRATE, ctx.paint), 0.0, 0.0, part.w, part.h, r=0.04)

@part_type("antenna", "Антенна", surfaces=ROOF, z=68, w=(0.04, 0.20), h=(0.30, 2.50))
def draw_antenna(p, part, ctx):
    """Штырь с шариком в основании. Начало: основание. h: длина штыря (по умолчанию к корме),
    angle поворачивает его. w: радиус шарика."""
    p.line(OUTLINE, 0.0, 0.0, 0.0, part.h, 0.04)
    p.ellipse(apply_paint(TURRET_DARK, ctx.paint), 0.0, 0.0, part.w, part.w)

# ==========================================
# БАШНЯ (этап 1b)
# ==========================================

@part_type("chevron", "Шеврон", surfaces=TURRET, z=30, w=(0.50, 1.50))
def draw_chevron(p, part, ctx):
    """Двойной шеврон острием вперёд. Начало: ось шеврона, w: масштаб."""
    s = part.w
    for k in (0.0, 0.25 * s):
        p.poly(EMBLEM_COLOR, [(x * s, y * s + k) for x, y in CHEVRON], outline=None)

@part_type("turret_hatch", "Люк командира", surfaces=TURRET, z=65, w=(0.15, 0.60), h=(0.10, 0.50))
def draw_turret_hatch(p, part, ctx):
    """w: радиус тёмного кольца, h: радиус круга цвета команды внутри."""
    p.ellipse(apply_paint(TURRET_DARK, ctx.paint), 0.0, 0.0, part.w, part.w)
    if ctx.team is not None:
        p.ellipse(ctx.team, 0.0, 0.0, part.h, part.h)

@part_type("loader_hatch", "Люк заряжающего (башня)", surfaces=TURRET, z=66, w=(0.10, 0.50))
def draw_loader_hatch(p, part, ctx):
    """w: радиус."""
    p.ellipse(apply_paint(TURRET_DARK, ctx.paint), 0.0, 0.0, part.w, part.w)

# ==========================================
# СТВОЛ: координаты от середины спрайта, дульный срез сверху
# ==========================================

@part_type("ejector", "Эжектор", surfaces=BARREL, z=30, w=(0.20, 0.80), h=(0.10, 0.60))
def draw_ejector(p, part, ctx):
    """Начало: левый верхний угол."""
    p.rect(GUN_LIGHT, 0.0, 0.0, part.w, part.h, r=0.05)

@part_type("muzzle_band", "Дульный поясок", surfaces=BARREL, z=40, w=(0.20, 0.80), h=(0.10, 0.50))
def draw_muzzle_band(p, part, ctx):
    """Начало: левый верхний угол."""
    p.rect(GUN_DARK, 0.0, 0.0, part.w, part.h)

@part_type("muzzle_brake", "Дульный тормоз", surfaces=BARREL, z=50, w=(0.20, 0.90), h=(0.20, 0.80))
def draw_muzzle_brake(p, part, ctx):
    """Тёмная коробка с двумя рёбрами. Начало: левый верхний угол."""
    p.rect(GUN_DARK, 0.0, 0.0, part.w, part.h, r=0.04)
    for y in (0.13, 0.27):
        p.line(GUN_LIGHT, 0.03, y, part.w - 0.03, y, 0.04)