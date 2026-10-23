"""tools/check_loadout.py — проверка подбора ботов под бюджет.
Запуск из корня проекта: python -m tools.check_loadout"""
import random

from ai import ARCHETYPES, fit_loadout
from ai.loadout import loadout_cost
from vehicles import VEHICLE_TYPES

PLAYER_COSTS = (6000, 15000, 25000, 35000)     # возможные V игрока
FRACTIONS = (0.35, 0.75, 1.0)
TOL = 0.02

def main():
    rng = random.Random(1)
    bad = 0
    for v in PLAYER_COSTS:
        for frac in FRACTIONS:
            budget = v * frac
            print(f"\nV={v}  доля={frac:.2f}  бюджет={budget:.0f}")
            for key, arch in ARCHETYPES.items():
                vals = fit_loadout(arch, budget, rng)
                cost = loadout_cost(vals)
                spec = VEHICLE_TYPES[arch.kind].spec_cls.from_values(vals, unbounded=True)
                ratio = cost / budget
                if ratio < 1.0 - TOL:
                    mark, bad = "!! НЕДОБОР", bad + 1
                elif ratio > 1.0 + TOL:
                    mark = "пол (дешевле нельзя)"
                else:
                    mark = ""
                print(f"  {key:10s} {ratio * 100:6.1f}%  кал {spec.cal:4.0f}  лоб {spec.front:4.0f}  "
                      f"мощн {spec.power:5.0f}  масса {spec.mass:6.1f} т  HP {spec.hp:5.0f}  {mark}")
    print("\nНедоборов:", bad)

if __name__ == "__main__":
    main()