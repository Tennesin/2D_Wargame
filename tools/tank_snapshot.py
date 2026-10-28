"""tools/tank_snapshot.py — текстовый «снимок» всего, что игра рисует для техники."""
import contextlib
import dataclasses
import datetime
import functools
import importlib
import inspect
import linecache
import math
import os
import sys
from collections import Counter

from engine import PX_PER_M, Team, point_in_convex
from vehicles.chassis.params import TRACK_LINK_M
from vehicles.gun.params import BARREL_LEN_STEP_M, BARREL_THICK_STEP_M, BARREL_HIDDEN_M
from vehicles.chassis.hulls import ArmorPlate
from vehicles.chassis.hull_noses import screen_pieces
from vehicles.render.base import Pen, SHADOW_HULL_M, SHADOW_TURRET_M, GunVehicleRenderer

try:
    from tools.local_paths import TANK_DATA_DIR as SNAPSHOT_DIR
except ImportError:
    SNAPSHOT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), "2D_Wargame_tank_data")
FORMAT_VERSION = 1

# ==========================================
# УСЛОВНЫЕ ИМЕНА
# ==========================================
# Имя функции, которая рисует деталь -> понятное название.
FUNC_NAMES = {
    "_draw_track_body": "Гусеница (тело)",
    "_draw_skirts": "Бортовой экран",
    "_draw_seams": "Шов палубы / заклёпка",
    "_draw_front_kit": "Накладная броня лба",
    "_draw_pike_kit": "Накладная броня носа (пластина)",
    "_draw_front_screen": "Лобовой экран",
    "_draw_exhaust": "Выхлопной патрубок",
    "_draw_deck": "Моторная крышка палубы",
    "_draw_pike_plate": "Щучий нос (скаты / клин палубы / гребень / V-шов)",
    "_draw_front_engine": "Моторная крышка носа (тяжёлый)",
    "_draw_stowage": "Укладка: ящики ЗИП / трос",
    "_draw_deck_relief": "Рельеф палубы (тяжёлый)",
    "_draw_rear_deck": "Кормовая решётка (тяжёлый)",
    "_turret_hex": "Башня-шестигранник",
    "_turret_oval": "Башня-овал",
    "_turret_cast": "Башня литая",
    "_chevrons": "Эмблема-шеврон",
    "_build_barrel": "Ствол",
    "_build_mantlet": "Маска орудия",
    "_build_hull": "Корпус (деталь, нарисованная прямо в _build_hull)",
    "_build_turret": "Башня (деталь, нарисованная прямо в _build_turret)",
}

LAYER_INFO = {
    "GEAR": ("Ходовая часть (под корпусом)",
             "начало = центр корпуса; +x вправо, +y назад (перёд = −y)"),
    "HULL": ("Корпус",
             "начало = центр корпуса; +x вправо, +y назад (перёд = −y)"),
    "TURRET": ("Башня", "начало = ось башни; перёд = −y"),
    "BARREL": ("Ствол", "начало = середина ствола (видимая часть + скрытая под башней); дульный срез сверху (−y)"),
    "MANTLET": ("Маска орудия (ПТ-САУ)",
                "начало = ось орудия; перёд = −y; вращается вместе с КОРПУСОМ и лежит поверх ствола"),
}

LAYOUT_RU = {
    "key": "ключ раскладки", "cls": "класс корпуса", "outline": "контур корпуса (без гусениц)",
    "track_x": "центр гусеницы от оси, м", "track_w": "ширина гусеницы", "track_top": "передний край гусеницы (y)",
    "track_len": "длина гусеницы", "axis_fwd_m": "ось башни/орудия впереди центра корпуса",
    "coll_half_w_m": "хитбокс: полуширина", "coll_half_l_m": "хитбокс: полудлина",
    "hit_parts": "участки попаданий снарядов", "plates": "плиты брони",
    "ring_r_m": "радиус погона", "turret_style": "стиль башни", "hull_style": "стиль деталей корпуса",
    "skirt_outer_x": "внешний край бортового экрана (x)",
    "skirt_levels": "бортовые экраны: (y_нач, y_кон, ширина) по уровням",
    "skirt_pitch_m": "шаг плит бортового экрана",
    "front_kit_poly": "накладка лба: полигон (уровень 1)", "front_kit_bar": "накладка лба: планка x,y,w,h (уровень 2)",
    "front_kit_wedge": "накладка лба: правый клин (уровень 2)",
    "exhaust_xs": "выхлоп: x", "exhaust_y": "выхлоп: y",
    "fender_rects": "подкрылки x,y,w,h: правый, левый", "front_plate": "лобовая плита (полигон)",
    "deck_rect": "палуба x,y,w,h", "canvas_half_m": "половина холста спрайта",
    "scale_range": "диапазон масштаба корпуса", "scale_step": "шаг масштаба",
    "hatch": "люк механика x,y,r", "grill_rect": "решётка МТО x,y,w,h", "rear_plate": "кормовая плита x,y,w,h",
    "base_skirt": "постоянный уровень бортового экрана", "turret_front_m": "выход ствола из башни, м",
    "nose": "вариант лба", "area_k": "множители площадей брони (лоб, борт, корма)",
    "turret_scale_range": "диапазон масштаба башни", "turret_k": "размер башни относительно корпуса",
    "heavy_detail": "доп. детали тяжёлого",
}

SPEC_ATTRS = [
    ("cal", "Калибр, мм"), ("front", "Лоб, мм"), ("side", "Борт, мм"), ("rear", "Корма, мм"),
    ("screen_mm", "Лобовые экраны, мм"), ("power", "Мощность, л.с."), ("nose", "Нос"),
    ("damage", "Урон"), ("penetration", "Пробитие, мм"), ("mass", "Масса, т"), ("size_k", "size_k"),
    ("HULL_SCALE", "HULL_SCALE (масштаб корпуса)"), ("TURRET_SCALE", "TURRET_SCALE (масштаб башни/ствола)"),
    ("GUN_FRONT_M", "GUN_FRONT_M (передний край маски / выход ствола)"),
    ("BARREL_LEN_M", "BARREL_LEN_M (видимая длина ствола)"), ("BARREL_THICK_M", "BARREL_THICK_M"),
    ("MUZZLE_DIST_PX", "MUZZLE_DIST_PX (центр -> дульный срез, мировые px)"),
    ("COLLISION_HALF_W_PX", "Хитбокс: полуширина, px мира"), ("COLLISION_HALF_L_PX", "Хитбокс: полудлина, px мира"),
    ("COLLISION_SHIFT_PX", "Хитбокс: сдвиг центра назад, px мира"),
    ("TURRET_ARC_DEG", "Сектор наводки, °"), ("MOUNT_FWD_M", "Ось орудия от центра корпуса, м (ПТ-САУ)"),
    ("SUPPORT", "Уровень задней опоры (ПТ-САУ)"), ("CASE_K", "Размер рубки/маски (ПТ-САУ)"),
    ("hull_index", "Индекс корпуса (ОБТ)"), ("HULL_CLASS", "Класс корпуса (ОБТ)"),
    ("HULL_VARIANT", "HULL_VARIANT (ключ кэша спрайта)"),
]

# ==========================================
# ФОРМАТИРОВАНИЕ
# ==========================================
def _f(v, d=3):
    s = f"{v:.{d}f}".rstrip("0").rstrip(".")
    return "0" if s in ("", "-0") else s

def _fmt(v):
    """Компактная запись значения (числа, кортежи, плиты, перечисления)."""
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, float):
        return _f(v)
    if isinstance(v, ArmorPlate):
        return f"плита {v.zone}: a={_fmt(v.a)} b={_fmt(v.b)} k={_f(v.k)} нормаль={_fmt(v.normal)}"
    if isinstance(v, (tuple, list)):
        return "(" + ", ".join(_fmt(x) for x in v) + ")"
    if hasattr(v, "name") and hasattr(v, "value") and not isinstance(v, str):
        return v.name
    return str(v)

def _short_path(path):
    return "/".join(path.replace("\\", "/").split("/")[-2:])

def _find_comment(filename, lineno):
    """Комментарий на строке вызова; если нет, ближайший выше (до 3 строк), с пометкой «~»."""
    for back in range(4):
        line = linecache.getline(filename, lineno - back)
        if "#" in line:
            text = line.split("#", 1)[1].strip()
            if text:
                return text if back == 0 else "~ " + text
    return ""

def _color_table():
    """RGB -> имена констант цветов из модулей рисовки."""
    table = {}
    for modname in ("vehicles.render.pen", "vehicles.tank.sprites", "vehicles.td.sprites"):
        mod = importlib.import_module(modname)
        for name, val in vars(mod).items():
            if (name.isupper() and isinstance(val, tuple) and len(val) in (3, 4)
                    and all(isinstance(c, int) and not isinstance(c, bool) for c in val)):
                table.setdefault(val[:3], set()).add(name)
    return {rgb: sorted(names) for rgb, names in table.items()}

# ==========================================
# ЗАПИСЬ ВЫЗОВОВ Pen
# ==========================================
class _Recorder:
    def __init__(self, team_color):
        self.layer = None
        self.items = []
        self.origins = {}            # слой -> (ox, oy) у Pen
        self._count = {}
        self.team = tuple(team_color)[:3]
        self.table = _color_table()

    def cname(self, col):
        if col is None:
            return "нет"
        c = tuple(int(v) for v in col)[:3]
        if c == self.team:
            return f"TEAM{c}"
        names = self.table.get(c)
        return f"{'/'.join(names)}{c}" if names else f"смесь{c}"

    def add(self, kind, pen, args, frame):
        n = self._count[self.layer] = self._count.get(self.layer, 0) + 1
        self.origins.setdefault(self.layer, (pen.ox, pen.oy))
        code = frame.f_code
        self.items.append({
            "id": f"{self.layer}-{n:03d}", "layer": self.layer, "kind": kind, "args": args,
            "func": code.co_name, "file": _short_path(code.co_filename), "line": frame.f_lineno,
            "comment": _find_comment(code.co_filename, frame.f_lineno),
        })

def _wrap(kind, orig, rec):
    sig = inspect.signature(orig)

    @functools.wraps(orig)
    def wrapper(self, *args, **kwargs):
        bound = sig.bind(self, *args, **kwargs)
        bound.apply_defaults()
        if kind == "poly":
            bound.arguments["pts"] = [tuple(p) for p in bound.arguments["pts"]]
        params = dict(bound.arguments)
        params.pop("self")
        rec.add(kind, self, params, sys._getframe(1))
        return orig(*bound.args, **bound.kwargs)

    return wrapper

@contextlib.contextmanager
def _patched_pen(rec):
    originals = {}
    for name in ("poly", "rect", "ellipse", "line"):
        originals[name] = getattr(Pen, name)
        setattr(Pen, name, _wrap(name, originals[name], rec))
    try:
        yield
    finally:
        for name, fn in originals.items():
            setattr(Pen, name, fn)

def _barrel_steps(spec):
    bl = int(round(spec.BARREL_LEN_M / BARREL_LEN_STEP_M))
    bt = int(round(spec.BARREL_THICK_M / BARREL_THICK_STEP_M))
    return bl, bt

def _run_builders(renderer, vehicle, rec):
    """Строит каждый слой заново (мимо кэшей), пока Pen записывает вызовы."""
    spec = vehicle.spec
    look = spec.LOOK
    team = vehicle.team_color
    paint = None if vehicle.team is Team.PLAYER else team
    bl, bt = _barrel_steps(spec)
    steps = [("GEAR", lambda: renderer._build_gear(spec, False, False)),
             ("HULL", lambda: renderer._build_hull(paint, look, spec))]
    if renderer.HAS_TURRET_SPRITE:
        steps.append(("TURRET", lambda: renderer._build_turret(team, paint, look, vehicle.emblem, spec)))
    steps.append(("BARREL", lambda: renderer._build_barrel(bl, bt, look)))
    if hasattr(renderer, "_build_mantlet"):
        steps.append(("MANTLET", lambda: renderer._build_mantlet(team, paint, look, spec)))
    with _patched_pen(rec):
        for layer, build in steps:
            rec.layer = layer
            build()

# ==========================================
# ГЕОМЕТРИЯ ФИГУР
# ==========================================
def _shape(kind, a):
    """-> (габарит x0,y0,x1,y1; контрольные точки; текстовое описание)."""
    if kind == "poly":
        pts = [(float(x), float(y)) for x, y in a["pts"]]
        bbox = (min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts))
        geom = f"polygon, вершин {len(pts)}: " + " ".join(f"({_f(x)};{_f(y)})" for x, y in pts)
        return bbox, pts, geom
    if kind == "rect":
        x, y, w, h, r = (float(a[k]) for k in ("x", "y", "w", "h", "r"))
        geom = f"rect: левый-верхний=({_f(x)};{_f(y)}) w={_f(w)} h={_f(h)}" + (f" скругл.={_f(r)}" if r else "")
        return (x, y, x + w, y + h), [(x, y), (x + w, y), (x + w, y + h), (x, y + h)], geom
    if kind == "ellipse":
        cx, cy, rx, ry = (float(a[k]) for k in ("cx", "cy", "rx", "ry"))
        geom = f"ellipse: центр=({_f(cx)};{_f(cy)}) rx={_f(rx)} ry={_f(ry)}"
        return ((cx - rx, cy - ry, cx + rx, cy + ry),
                [(cx - rx, cy), (cx + rx, cy), (cx, cy - ry), (cx, cy + ry)], geom)
    x1, y1, x2, y2, w = (float(a[k]) for k in ("x1", "y1", "x2", "y2", "w"))
    geom = (f"line: ({_f(x1)};{_f(y1)}) -> ({_f(x2)};{_f(y2)}) "
            f"длина={_f(math.hypot(x2 - x1, y2 - y1))} толщина={_f(w)}")
    return (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)), [(x1, y1), (x2, y2)], geom

def _overlap(a, b):
    return (min(a[2], b[2]) - max(a[0], b[0]) > 1e-3) and (min(a[3], b[3]) - max(a[1], b[1]) > 1e-3)

def _zones(layout):
    tl, tr = layout.track_rects
    xs = [p[0] for p in layout.front_plate]
    ys = [p[1] for p in layout.front_plate]
    return [("ГУСЕНИЦА-Л", tl), ("ГУСЕНИЦА-П", tr),
            ("ПЛИТА-ЛБА", (min(xs), min(ys), max(xs), max(ys)))]

def _item_lines(rec, it, with_checks, zones, outline):
    a, kind = it["args"], it["kind"]
    bbox, samples, geom = _shape(kind, a)
    it["bbox"] = bbox
    name = FUNC_NAMES.get(it["func"], it["func"] + "()")
    head = f"{it['id']} | {name}" + (f" — {it['comment']}" if it["comment"] else "")
    cx, cy = (bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0
    if kind == "line":
        paint = f"цвет: {rec.cname(a['color'])}"
    else:
        paint = f"заливка: {rec.cname(a['color'])} | контур: {rec.cname(a['outline'])}"
    lines = [head, f"    {geom}", f"    {paint}",
             f"    габарит: x {_f(bbox[0])}..{_f(bbox[2])}, y {_f(bbox[1])}..{_f(bbox[3])}"
             f" | центр ({_f(cx)};{_f(cy)}) | размер {_f(bbox[2] - bbox[0])}×{_f(bbox[3] - bbox[1])}"]
    tail = f"    источник: {it['file']}:{it['line']} в {it['func']}()"
    flags = {"zones": [], "outside": 0, "name": name}
    if with_checks:
        flags["zones"] = [label for label, zb in zones if _overlap(bbox, zb)]
        flags["outside"] = sum(1 for x, y in samples if not point_in_convex(outline, x, y))
        if flags["zones"]:
            tail += " | задевает рамки: " + ", ".join(flags["zones"])
        if flags["outside"]:
            tail += f" | вне контура корпуса: {flags['outside']} из {len(samples)} точек"
    lines.append(tail)
    return lines, flags

# ==========================================
# ОТЧЁТ
# ==========================================
def _head(title):
    return ["", "=" * 78, title, "=" * 78]

def build_report(vehicle, renderer):
    linecache.checkcache()
    spec = vehicle.spec
    layout = spec.layout
    rec = _Recorder(vehicle.team_color)
    _run_builders(renderer, vehicle, rec)

    zones = _zones(layout)
    ppm = renderer._ppm
    hs = spec.HULL_SCALE
    ts = spec.TURRET_SCALE
    bl, bt = _barrel_steps(spec)
    barrel_len = bl * BARREL_LEN_STEP_M

    # --- фигуры по слоям ---
    layer_lines, flags_by_id = {}, {}
    for layer in rec.origins:
        lines = []
        for it in (i for i in rec.items if i["layer"] == layer):
            ls, fl = _item_lines(rec, it, layer == "HULL", zones, layout.outline)
            lines += ls + [""]
            flags_by_id[it["id"]] = fl
        layer_lines[layer] = lines

    out = ["СНИМОК ТЕХНИКИ — 2D Wargame",
           f"Создан: {datetime.datetime.now():%Y-%m-%d %H:%M:%S}",
           f"Формат снимка: v{FORMAT_VERSION}",
           f"Класс машины: {type(vehicle).__name__} (renderer_key={vehicle.renderer_key}), "
           f"рендерер: {type(renderer).__name__}",
           f"Раскладка корпуса: {layout.key}, нос: {spec.nose}"]

    # --- 0. легенда ---
    out += _head("0. КАК ЧИТАТЬ")
    out += ["Все размеры и координаты фигур даны в МЕТРАХ эталонного спрайта (до масштабирования).",
            "Экранный размер детали (px) = метры × масштаб × ppm, где ppm = PX_PER_M × zoom камеры.",
            "  корпус / ходовая / маска ПТ-САУ: масштаб = HULL_SCALE; башня и ствол: масштаб = TURRET_SCALE.",
            "ID детали = СЛОЙ-номер по порядку рисования (HULL-012). Номера могут сдвинуться после правок кода,",
            "строка «источник: файл:строка» остаётся точной. Пометка «~» в названии = комментарий взят из строк выше.",
            "Системы координат слоёв:"]
    for layer, origin in rec.origins.items():
        title, frame = LAYER_INFO[layer]
        out.append(f"  {layer}: {title}. {frame}. Сдвиг Pen: ox={_f(origin[0])}, oy={_f(origin[1])}")

    # --- 1. параметры ---
    out += _head("1. ПАРАМЕТРЫ ТЕХНИКИ")
    for attr, ru in SPEC_ATTRS:
        if hasattr(spec, attr):
            out.append(f"{ru} [{attr}] = {_fmt(getattr(spec, attr))}")
    look = spec.LOOK
    out.append(f"LOOK: front={look.front} side={look.side} gun={look.gun} speed={look.speed} screen={look.screen}")
    out.append(f"  hull_key={_fmt(look.hull_key)} turret_key={_fmt(look.turret_key)} barrel_key={look.barrel_key}")
    out.append(f"Хитбокс: {_f(2 * spec.COLLISION_HALF_W_PX / PX_PER_M)} × {_f(2 * spec.COLLISION_HALF_L_PX / PX_PER_M)} м")

    # --- 2. масштабы ---
    out += _head("2. МАСШТАБЫ")
    out += [f"PX_PER_M = {_f(PX_PER_M)}; ppm рендерера (экранных px на метр спрайта при масштабе 1) = {_f(ppm)}",
            f"HULL_SCALE = {_f(hs)}  -> 1 м корпуса = {_f(ppm * hs)} экранных px",
            f"TURRET_SCALE = {_f(ts)}  -> 1 м башни/ствола = {_f(ppm * ts)} экранных px"]

    # --- 3. раскладка ---
    out += _head("3. РАСКЛАДКА КОРПУСА (HullLayout, метры корпуса)")
    for f in dataclasses.fields(layout):
        val = getattr(layout, f.name)
        ru = LAYOUT_RU.get(f.name, "")
        text = _fmt(val)
        if (isinstance(val, (tuple, list)) and len(text) > 110
                and all(isinstance(x, (tuple, list, ArmorPlate)) for x in val)):
            out.append(f"{f.name} — {ru}:")
            out += [f"    [{i}] {_fmt(x)}" for i, x in enumerate(val)]
        else:
            out.append(f"{f.name} — {ru} = {text}")
    out.append("--- производные ---")
    out.append(f"coll_shift_m (центр корпуса позади оси) = {_f(layout.coll_shift_m)}")
    out.append(f"front_face_m (самая передняя точка hit_parts) = {_f(layout.front_face_m)}")
    for i, (x0, y0, x1, y1) in enumerate(layout.track_rects):
        out.append(f"track_rects[{i}] ({'левая' if i == 0 else 'правая'}): x {_f(x0)}..{_f(x1)}, y {_f(y0)}..{_f(y1)}")
    for i, (a, b, n) in enumerate(screen_pieces(layout)):
        out.append(f"лобовой экран #{i + 1}: a=({_f(a[0])};{_f(a[1])}) b=({_f(b[0])};{_f(b[1])}) нормаль=({_f(n[0])};{_f(n[1])})")

    # --- 4. то, что рисуется мимо Pen ---
    out += _head("4. ТЕНЬ, ЗВЕНЬЯ ГУСЕНИЦ, ПОЛОЖЕНИЕ СТВОЛА (рисуется не через Pen)")
    out.append(f"Тень корпуса (силуэт ходовая+корпус): смещение {_fmt(SHADOW_HULL_M)} м × ppm × HULL_SCALE")
    out.append(f"Тень башни и ствола: смещение {_fmt(SHADOW_TURRET_M)} м × ppm × TURRET_SCALE")
    k = ppm * hs
    visible = TRACK_LINK_M * k >= 3.0
    y_min, y_max = layout.track_top + 0.05, layout.track_top + layout.track_len - 0.05
    out.append(f"Бегущие звенья: шаг {_f(TRACK_LINK_M)} м, толщина линии 0.06 м, "
               f"{'ВИДНЫ' if visible else 'скрыты (слишком мелко при текущем зуме)'}; "
               f"y {_f(y_min)}..{_f(y_max)}, примерно {int((y_max - y_min) / TRACK_LINK_M)} звеньев на гусеницу")
    for side, name in ((-1, "левая"), (1, "правая")):
        xc = side * layout.track_x
        out.append(f"  {name}: x {_f(xc - layout.track_w / 2 + 0.07)}..{_f(xc + layout.track_w / 2 - 0.07)}")
    out.append(f"Ствол: видимая длина {_f(barrel_len)} м ({bl} шагов по {_f(BARREL_LEN_STEP_M)}), "
               f"толщина {_f(bt * BARREL_THICK_STEP_M)} м, скрыто под башней {_f(BARREL_HIDDEN_M)} м")
    out.append(f"  центр спрайта ствола от оси вдоль орудия = (GUN_FRONT_M + L/2 − скрыто/2) × TURRET_SCALE = "
               f"{_f((spec.GUN_FRONT_M + barrel_len / 2.0 - BARREL_HIDDEN_M / 2.0) * ts)} м экранного масштаба (без отката)")
    out.append(f"  дульный срез от оси = (GUN_FRONT_M + BARREL_LEN_M) × TURRET_SCALE = "
               f"{_f((spec.GUN_FRONT_M + spec.BARREL_LEN_M) * ts)} м")

    # --- 5. порядок слоёв ---
    out += _head("5. ПОРЯДОК СЛОЁВ (снизу вверх)")
    order = ["тень (силуэты)", "GEAR (тело гусениц)", "бегущие звенья гусениц", "HULL (корпус)", "BARREL (ствол)"]
    if renderer.HAS_TURRET_SPRITE:
        order.append("TURRET (башня)")
    if type(renderer)._draw_front_layer is not GunVehicleRenderer._draw_front_layer:
        order.append("MANTLET (передний слой: маска, вращается с корпусом)")
    out += [f"  {i}. {s}" for i, s in enumerate(order, 1)]

    # --- 6. сводка ---
    out += _head("6. СВОДКА")
    for layer in rec.origins:
        items = [i for i in rec.items if i["layer"] == layer]
        bb = [i["bbox"] for i in items]
        out.append(f"{layer}: {len(items)} фигур; общий габарит x {_f(min(b[0] for b in bb))}..{_f(max(b[2] for b in bb))}, "
                   f"y {_f(min(b[1] for b in bb))}..{_f(max(b[3] for b in bb))}")
        cnt = Counter(flags_by_id[i["id"]]["name"] for i in items)
        out += [f"    {name} ×{n}" for name, n in cnt.items()]
    outside, on_track = {}, {}
    for it in (i for i in rec.items if i["layer"] == "HULL"):
        fl = flags_by_id[it["id"]]
        if fl["outside"]:
            outside.setdefault(fl["name"], []).append(it["id"])
        if any(z.startswith("ГУСЕНИЦА") for z in fl["zones"]) and it["func"] != "_draw_skirts":
            on_track.setdefault(fl["name"], []).append(it["id"])
    out.append("Автопроверка корпуса (по габаритным рамкам, косые фигуры могут давать ложные срабатывания):")
    out.append("  Выходят за контур корпуса:" + ("" if outside else " нет"))
    out += [f"    {n}: {', '.join(ids)}" for n, ids in outside.items()]
    out.append("  Задевают рамку гусеницы (кроме бортовых экранов):" + ("" if on_track else " нет"))
    out += [f"    {n}: {', '.join(ids)}" for n, ids in on_track.items()]

    # --- 7. фигуры ---
    for layer in rec.origins:
        out += _head(f"7. ФИГУРЫ СЛОЯ {layer} — {LAYER_INFO[layer][0]} (порядок = порядок рисования)")
        out += layer_lines[layer]
    return "\n".join(out) + "\n"

def save_snapshot(vehicle, renderer):
    """Строит отчёт и пишет его в SNAPSHOT_DIR. Возвращает полный путь к файлу."""
    text = build_report(vehicle, renderer)
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(SNAPSHOT_DIR, f"snapshot_{vehicle.renderer_key}_{stamp}.txt")
    with open(path, "w", encoding="utf-8-sig") as fh:     # BOM: чтобы блокнот Windows не путал кодировку
        fh.write(text)
    return path