"""tools/check_arty.py — проверка САУ: характеристики, правила выстрела, подбор сборки под бюджет.
Запуск из корня проекта: python -m tools.check_arty"""
import random

from ai import Archetype, fit_loadout
from ai.loadout import loadout_cost
from engine import PX_PER_M, VehicleCommand, VehicleKind
from vehicles import VEHICLE_TYPES, SPG_PARAMS, SPGSpec, make_vehicle

POWER = SPG_PARAMS["engine_power_hp"].default
DT = 1.0 / 60.0

def table():
    print("=== 1. Характеристики (двигатель по умолчанию) ===")
    for cal in (125, 200, 255):
        for armor in (5, 25, 50):
            spec = SPGSpec(cal, armor, armor, armor, POWER)
            g = spec.shell_stats
            print(f"кал {cal:3d} броня {armor:2d} | HP {spec.hp:4.0f} масса {spec.mass:5.1f} т "
                  f"size_k {spec.size_k:.3f} масштаб {spec.HULL_SCALE:.2f} | урон {g.damage:4.0f} "
                  f"дальн {g.range_max_px / PX_PER_M:4.0f} м мёртвая {g.range_min_px / PX_PER_M:3.0f} м "
                  f"перез {g.reload:4.1f} с оглуш {g.stun_s:.1f} с v {g.speed_px / PX_PER_M:4.1f} м/с "
                  f"R {g.outer_radius_px / PX_PER_M:4.1f}/{g.inner_radius_px / PX_PER_M:3.1f} м "
                  f"цена {spec.cost}")
    print("Ориентир (кал 200, броня 25): HP 500, урон 500, дальность 160, оглушение 3.0, v 30, перезарядка 12")

def run(spg, aim_m, seconds, fire=True):
    """Гоняет технику seconds секунд с целью на aim_m метров впереди. Возвращает [(время, Shot)]."""
    aim = (spg.x, spg.y - aim_m * PX_PER_M)             # курс 0 = вверх
    shots = []
    for i in range(round(seconds / DT)):
        shot = spg.update(VehicleCommand(aim_point=aim, fire=fire), DT)
        if shot is not None:
            shots.append((i * DT, shot))
    return shots

def fire_test():
    print("\n=== 2. Правила выстрела (кал 200) ===")
    spec = SPGSpec(200, 25, 25, 25, POWER)

    def fresh():
        return make_vehicle(VehicleKind.SPG, spec)

    s = run(fresh(), 100.0, 0.5)
    print(f"в зоне (100 м):          {'OK, выстрел' if s else 'ОШИБКА, выстрела нет'}; "
          f"target={s[0][1].target if s else None}")
    print(f"мёртвая зона (10 м):     {'ОШИБКА' if run(fresh(), 10.0, 0.5) else 'OK, не стреляет'}")
    print(f"за дальностью (200 м):   {'ОШИБКА' if run(fresh(), 200.0, 0.5) else 'OK, не стреляет'}")

    stunned = fresh()
    stunned.apply_stun(3.0)
    print(f"оглушена (первые 2 с):   {'ОШИБКА' if run(stunned, 100.0, 2.0) else 'OK, не стреляет'}")

    cycle = run(fresh(), 100.0, 26.0)
    times = ", ".join(f"{t:.1f}" for t, _ in cycle)
    print(f"выстрелы за 26 с (с):    {times}  (ждём около 0, 12, 24)")

def fit_test():
    print("\n=== 3. Подбор сборки под бюджет (хуки loadout) ===")
    vtype = VEHICLE_TYPES[VehicleKind.SPG]
    caps = {key: p.max for key, p in SPG_PARAMS.items()}
    arch = Archetype(
        "САУ (тест)",
        {"gun_caliber_mm": 0.8, "front_armor_mm": 0.4, "side_armor_mm": 0.4,
         "rear_armor_mm": 0.3, "engine_power_hp": 0.5},
        (200, 120, 40), 60.0, 0.0, jitter=0.0, kind=VehicleKind.SPG, caps=caps)
    rng = random.Random(1)
    for budget in (4000, 6000, 9000, 12000, 16000, 30000):
        values = fit_loadout(arch, budget, rng)
        cost = loadout_cost(values, vtype)
        spec = SPGSpec.from_values(values, unbounded=True)
        print(f"бюджет {budget:6d} -> цена {cost:7.0f} ({cost / budget * 100:5.1f}%) "
              f"кал {spec.cal:3.0f} брони {spec.front:.0f}/{spec.side:.0f}/{spec.rear:.0f} "
              f"мощн {spec.power:.0f}  HP {spec.hp:.0f}")

if __name__ == "__main__":
    table()
    fire_test()
    fit_test()