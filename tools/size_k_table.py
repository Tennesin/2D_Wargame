"""tools/size_k_table.py — реальные границы size_k у всех типов техники (для толщины гусениц)."""
import itertools
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import VehicleKind
from vehicles import VEHICLE_TYPES, COST_REF
from ai import ARCHETYPES, fit_loadout

def report(label, sizes):
    print(f"{label:28s} n={len(sizes):4d}  size_k {min(sizes):.3f}..{max(sizes):.3f}")

rng = random.Random(1)
for kind, vtype in VEHICLE_TYPES.items():
    keys = list(vtype.params)
    corners = [dict(zip(keys, combo)) for combo in
               itertools.product(*((vtype.params[k].min, vtype.params[k].max) for k in keys))]
    report(f"{vtype.label}: углы ползунков",
           [vtype.spec_cls.from_values(v).size_k for v in corners])

for arch in ARCHETYPES.values():
    vtype = VEHICLE_TYPES[arch.kind]
    sizes = []
    for frac in (0.35, 0.7, 1.0, 1.4):
        for _ in range(60):
            values = fit_loadout(arch, COST_REF * frac, rng)
            sizes.append(vtype.spec_cls.from_values(values, unbounded=True).size_k)
    report(f"Бот: {arch.name}", sizes)