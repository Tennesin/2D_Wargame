"""Какие классы корпуса и масштабы получаются на практике."""
import os
import random
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import VehicleKind
from vehicles import TankSpec, TANK_PARAMS
from ai import ARCHETYPES, fit_loadout, BASE_BUDGET


def survey(label, specs):
    groups = defaultdict(list)
    for s in specs:
        groups[s.HULL_CLASS.name].append(s)
    print(f"\n{label} (n={len(specs)})")
    for name, items in sorted(groups.items()):
        ks = [s.size_k for s in items]
        hs = [s.HULL_SCALE for s in items]
        print(f"  {name:7s} {100 * len(items) / len(specs):5.1f}%   "
              f"size_k {min(ks):.3f}..{max(ks):.3f}   HULL_SCALE {min(hs):.2f}..{max(hs):.2f}")


def random_values(rng):
    values = {}
    for key, p in TANK_PARAMS.items():
        steps = int(round((p.max - p.min) / p.step))
        values[key] = p.min + rng.randint(0, steps) * p.step
    return values


rng = random.Random(1)
survey("Случайные ползунки", [TankSpec.from_values(random_values(rng)) for _ in range(5000)])
for arch in ARCHETYPES.values():
    if arch.kind is not VehicleKind.MBT:
        continue
    budget = round(BASE_BUDGET * arch.budget_k)
    survey(f"Архетип {arch.name}",
           [TankSpec.from_values(fit_loadout(arch, budget, rng)) for _ in range(300)])