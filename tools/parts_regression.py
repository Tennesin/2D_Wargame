"""tools/parts_regression.py — сверка спрайтов техники до и после выноса деталей в данные.
Запуск из корня проекта:
  python -m tools.parts_regression --save   (ДО правок: сохранить эталонные PNG)
  python -m tools.parts_regression          (ПОСЛЕ правок: сравнить с эталоном)"""
import os
import sys
import json

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")          # окно не нужно

import pygame

from engine import PX_PER_M, VehicleKind
from tools.tank_snapshot import SNAPSHOT_DIR
from vehicles import VEHICLE_TYPES, RENDERERS, NOSE_PIKE
from vehicles.gun.params import BARREL_LEN_STEP_M, BARREL_THICK_STEP_M, BARREL_HIDDEN_M
from vehicles.parts import (
    PartsDesign, freeze_auto, resolve, PART_TYPES,
    new_part, reshaped, center, contains
)

ZOOM = 0.25                       # ppm = 25: зерно включено, спрайты небольшие
BASE_DIR = os.path.join(SNAPSHOT_DIR, "parts_baseline")
MAX_BAD_FRAC = 0.002              # допустимая доля отличающихся пикселей
MAX_DIFF = 70                     # допустимое отличие канала у такого пикселя
DESIGN_MAX_BAD_FRAC = 0.004       # проверка дизайна: допускаем сдвиг тонкой линии на 1 пиксель суперсэмплинга
DESIGN_MAX_DIFF = 140
TEAM = (200, 60, 60)

def _base(kind):
    return {k: p.default for k, p in VEHICLE_TYPES[kind].params.items()}

def cases():
    mbt, td, spg = VehicleKind.MBT, VehicleKind.TD, VehicleKind.SPG
    b = _base(mbt)
    yield "mbt_default", mbt, dict(b)
    yield "mbt_light", mbt, {**b, "front_armor_mm": 40, "side_armor_mm": 30,
                             "rear_armor_mm": 20, "engine_power_hp": 2000}
    yield "mbt_heavy", mbt, {**b, "front_armor_mm": 500, "side_armor_mm": 375,
                             "rear_armor_mm": 250, "engine_power_hp": 800}
    yield "mbt_heavy_pike", mbt, {**b, "front_armor_mm": 500, "side_armor_mm": 375,
                                  "rear_armor_mm": 250, "engine_power_hp": 800,
                                  "front_nose": NOSE_PIKE}
    yield "mbt_medium_pike", mbt, {**b, "front_nose": NOSE_PIKE}
    yield "mbt_screens", mbt, {**b, "front_screen_mm": 45, "side_armor_mm": 200}
    yield "mbt_slab_turret", mbt, {**b, "turret_style": "slab", "turret_size": 1.1}
    yield "mbt_oval_turret", mbt, {**b, "turret_style": "oval", "turret_axis_shift_m": 0.3}
    t = _base(td)
    yield "td_default", td, dict(t)
    yield "td_small", td, {**t, "gun_caliber_mm": 60}
    yield "td_big", td, {**t, "gun_caliber_mm": 175}
    yield "td_pike", td, {**t, "front_armor_mm": 450, "front_nose": NOSE_PIKE}
    yield "td_shift", td, {**t, "mount_shift_m": 1.0}
    s = _base(spg)
    yield "spg_default", spg, dict(s)
    yield "spg_small", spg, {**s, "gun_caliber_mm": 125}
    yield "spg_big", spg, {**s, "gun_caliber_mm": 255}
    light = {**b, "front_armor_mm": 40, "side_armor_mm": 30, "rear_armor_mm": 20, "engine_power_hp": 2000}
    for style in ("hex", "oval", "slab"):
        yield f"mbt_antenna_{style}", mbt, {**light, "turret_style": style}
    yield "td_antenna", td, {**t, "front_armor_mm": 40, "side_armor_mm": 30,
                             "rear_armor_mm": 20, "engine_power_hp": 2000}

def render(kind, values):
    """{имя слоя: Surface} для одной сборки."""
    spec = VEHICLE_TYPES[kind].spec_cls.from_values(values)
    renderer = RENDERERS[kind]()
    renderer.set_zoom(PX_PER_M * ZOOM)
    look = spec.LOOK
    out = {}
    for who, paint in (("player", None), ("bot", TEAM)):
        team = TEAM if paint else (64, 140, 200)
        out[f"hull_{who}"] = renderer._build_hull(paint, look, spec)
        if renderer.HAS_TURRET_SPRITE:
            for emblem in ("", "chevron"):
                out[f"turret_{who}_{emblem or 'none'}"] = renderer._build_turret(
                    team, paint, look, emblem, spec)
        if hasattr(renderer, "_build_mantlet"):
            out[f"mantlet_{who}"] = renderer._build_mantlet(team, paint, look, spec)
    bl = int(round(spec.BARREL_LEN_M / BARREL_LEN_STEP_M))
    bt = int(round(spec.BARREL_THICK_M / BARREL_THICK_STEP_M))
    out["barrel"] = renderer._build_barrel(bl, bt, look, spec)
    return out

def compare(a, b):
    """(число отличающихся пикселей, наибольшее отличие канала) или None, если размеры разные."""
    if a.get_size() != b.get_size():
        return None
    da = pygame.image.tostring(a, "RGBA")
    db = pygame.image.tostring(b, "RGBA")
    if da == db:
        return 0, 0
    bad = worst = 0
    for i in range(0, len(da), 4):
        pa, pb = da[i:i + 4], db[i:i + 4]
        if pa == pb or (pa[3] == 0 and pb[3] == 0):
            continue
        d = max(abs(pa[j] - pb[j]) for j in range(4))
        bad += 1
        worst = max(worst, d)
    return bad, worst

def check_screens():
    """Авто-набор проходит правила, жадная набивка не превышает охват, на корме кромок нет, луч видит лист."""
    from vehicles.chassis.screens import ray_crossings, Screen
    from vehicles.parts.screens import auto_screen_parts, accept, snap_hull, coverage
    failed = 0
    for name, kind, values in cases():
        spec = VEHICLE_TYPES[kind].spec_cls.from_values(values)
        layout = spec.layout
        parts = auto_screen_parts(layout, 30)
        if len(accept(layout, parts)) != len(parts):
            print(f"ЭКРАНЫ авто-набор не проходит правила: {name}")
            failed += 1
        filled = []
        for sx in range(-6, 7):
            for sy in range(-6, 7):
                p = snap_hull(layout, sx * 0.4, sy * 0.6, 3.0)
                if p is not None and any(q is p for q, *_ in accept(layout, filled + [p])):
                    filled.append(p)
        for g, (used, total) in coverage(layout, filled).items():
            cap = 0.9 if g == "front" else 0.8
            if used > cap * total + 0.01:
                print(f"ЭКРАНЫ охват {name}/{g}: {used / total:.2f}")
                failed += 1
        if snap_hull(layout, 0.0, 3.2, 0.6) is not None:
            print(f"ЭКРАНЫ корма: {name}")
            failed += 1
    sheet = Screen((-0.5, -2.0), (0.5, -2.0), (0.0, -1.0), 30.0, "front")
    hits = ray_crossings([sheet], 0.0, -4.0, 0.0, 1.0, 1.0, 5.0)
    if len(hits) != 1 or abs(hits[0][2] - 1.0) > 1e-9:
        print("ЭКРАНЫ луч не нашёл лист")
        failed += 1
    return failed

def check_design():
    """Авто-набор -> «заморозка» -> JSON -> загрузка -> рисунок должен совпасть с авто-рисунком.
    Заодно: все замороженные детали помещаются, а мусор в данных не роняет загрузку."""
    failed = 0
    for name, kind, values in cases():
        if kind is VehicleKind.SPG:                       # у САУ дизайн пока не подключён
            continue
        spec = VEHICLE_TYPES[kind].spec_cls.from_values(values)
        frozen = freeze_auto(RENDERERS[kind].DESIGN_KIND, spec)
        data = json.loads(json.dumps(frozen.to_data()))   # как после записи в файл
        loaded = PartsDesign.from_data(data)
        for surface in ("hull", "turret", "barrel"):
            parts = loaded.get(surface)
            if parts is None:
                continue
            lost = len(parts) - len(resolve(parts, spec, surface))
            if lost:
                print(f"НЕ ПОМЕЩАЕТСЯ {name}/{surface}: {lost} из {len(parts)}")
                failed += 1
        auto = render(kind, values)
        manual = render(kind, {**values, "parts_design": data})
        for layer, surf in auto.items():
            if layer.endswith("chevron"):
                continue
            res = compare(surf, manual[layer])
            if res is None:
                print(f"РАЗМЕР ИЗМЕНИЛСЯ: {name}/{layer}")
                failed += 1
                continue
            bad, worst = res
            total = surf.get_width() * surf.get_height()
            ok = bad <= total * DESIGN_MAX_BAD_FRAC and worst <= DESIGN_MAX_DIFF
            if bad:
                print(f"{'ок ' if ok else 'ОШИБКА'} {name}/{layer}: пикселей {bad} из {total}, макс. отличие {worst}")
            failed += 0 if ok else 1

    junk = [None, 5, "x", [], {"version": 99},
            {"version": 1, "hull": [None, 5, {"k": ["a"]}, {"k": "hatch", "x": "q"},
                                    {"k": "hatch", "x": 1e9, "y": 0.0, "w": 9}]}]
    for item in junk:
        d = PartsDesign.from_data(item)
        print("мусор ->", "Авто" if d.is_auto else f"hull={d.hull}")
    return failed

def check_geometry():
    """Поворот, отражение и размер идут вокруг центра: центр габарита не должен уезжать."""
    failed = 0
    for kind, ptype in PART_TYPES.items():
        p = new_part(kind, ptype.surfaces[0], 0.3, 0.4)
        for change in ({"angle": 37.0}, {"mirror": True}, {"angle": 200.0, "mirror": True}):
            q = reshaped(p, **change)
            cx, cy = center(q)
            if abs(cx - 0.3) > 1e-9 or abs(cy - 0.4) > 1e-9 or not contains(q, cx, cy, 0.0):
                print(f"ГЕОМЕТРИЯ {kind} {change}: центр ({cx:.4f}; {cy:.4f})")
                failed += 1
    return failed

def check_anchors():
    """Деталь у дульного среза остаётся у дульного среза при смене калибра (длина ствола другая)."""
    kind = VehicleKind.MBT
    vt = VEHICLE_TYPES[kind]
    base = _base(kind)
    spec_a = vt.spec_cls.from_values({**base, "gun_caliber_mm": 100})
    data = json.loads(json.dumps(freeze_auto(RENDERERS[kind].DESIGN_KIND, spec_a).to_data()))
    spec_b = vt.spec_cls.from_values({**base, "gun_caliber_mm": 135, "parts_design": data})
    parts = resolve(PartsDesign.from_data(data).barrel, spec_b, "barrel")
    band = next((p for p in parts if p.kind == "muzzle_band"), None)
    if band is None:
        print("АНКЕРЫ: поясок пропал при смене калибра")
        return 1
    half = (spec_b.BARREL_LEN_M + BARREL_HIDDEN_M) / 2.0
    if abs(band.y + half) > 1e-3:
        print(f"АНКЕРЫ: поясок {band.y:.3f}, ожидалось {-half:.3f}")
        return 1
    return 0

def main():
    save = "--save" in sys.argv
    pygame.init()
    pygame.display.set_mode((1, 1))
    if "--design" in sys.argv:
        failed = check_geometry() + check_design() + check_anchors() + check_screens()
        print("Дизайн: всё совпадает." if not failed else f"Дизайн: проблем {failed}")
        pygame.quit()
        return
    os.makedirs(BASE_DIR, exist_ok=True)
    failed = 0
    for name, kind, values in cases():
        for layer, surf in render(kind, values).items():
            path = os.path.join(BASE_DIR, f"{name}__{layer}.png")
            if save:
                pygame.image.save(surf, path)
                continue
            if not os.path.exists(path):
                print(f"НЕТ ЭТАЛОНА: {name}/{layer}")
                failed += 1
                continue
            res = compare(surf, pygame.image.load(path).convert_alpha())
            if res is None:
                print(f"РАЗМЕР ИЗМЕНИЛСЯ: {name}/{layer}")
                failed += 1
                continue
            bad, worst = res
            total = surf.get_width() * surf.get_height()
            ok = bad <= total * MAX_BAD_FRAC and worst <= MAX_DIFF
            if bad:
                print(f"{'ок ' if ok else 'ОШИБКА'} {name}/{layer}: пикселей {bad} из {total}, макс. отличие {worst}")
            failed += 0 if ok else 1
    if save:
        print(f"Эталон сохранён: {BASE_DIR}")
    else:
        print("Всё совпадает." if not failed else f"Проблем: {failed}")
    pygame.quit()

if __name__ == "__main__":
    main()