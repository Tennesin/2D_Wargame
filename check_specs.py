# check_specs.py — временный: сравнивает расчёты до и после переноса
import json, sys
from tank_spec import TankSpec      # после переезда замените на: from tank import TankSpec

BUILDS = {
    "reference":    (120, 300, 75, 50, 750),
    "light_armor":  (120, 15, 15, 15, 750),
    "heavy_armor":  (120, 500, 375, 250, 750),
    "big_gun_thin": (175, 15, 15, 15, 500),
    "big_gun_fast": (175, 15, 15, 15, 1500),
    "small_gun":    (45, 500, 375, 250, 500),
}

def snapshot():
    out = {}
    for name, args in BUILDS.items():
        spec = TankSpec(*args)
        out[name] = {k: round(v, 4) for k, v in vars(spec).items()
                     if isinstance(v, (int, float))}
    return out

if __name__ == "__main__":
    path = "baseline.json"
    if len(sys.argv) > 1 and sys.argv[1] == "save":
        json.dump(snapshot(), open(path, "w"), indent=1)
        print("слепок сохранён")
    else:
        old, new = json.load(open(path)), snapshot()
        diffs = [(b, k, old[b].get(k), new[b].get(k))
                 for b in new for k in new[b] if old[b].get(k) != new[b][k]]
        print("ВСЁ СОВПАДАЕТ" if not diffs else f"Отличий: {len(diffs)}")
        for d in diffs[:30]:
            print(d)