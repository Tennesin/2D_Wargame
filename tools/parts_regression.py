"""tools/parts_regression.py — сверка спрайтов техники до и после выноса деталей в данные.
Запуск из корня проекта:
  python -m tools.parts_regression --save   (ДО правок: сохранить эталонные PNG)
  python -m tools.parts_regression          (ПОСЛЕ правок: сравнить с эталоном)"""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")          # окно не нужно

import pygame

from engine import PX_PER_M, VehicleKind
from tools.tank_snapshot import SNAPSHOT_DIR
from vehicles import VEHICLE_TYPES, RENDERERS, NOSE_PIKE
from vehicles.gun.params import BARREL_LEN_STEP_M, BARREL_THICK_STEP_M

ZOOM = 0.25                       # ppm = 25: зерно включено, спрайты небольшие
BASE_DIR = os.path.join(SNAPSHOT_DIR, "parts_baseline")
MAX_BAD_FRAC = 0.002              # допустимая доля отличающихся пикселей
MAX_DIFF = 70                     # допустимое отличие канала у такого пикселя
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
    out["barrel"] = renderer._build_barrel(bl, bt, look)
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

def main():
    save = "--save" in sys.argv
    pygame.init()
    pygame.display.set_mode((1, 1))
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