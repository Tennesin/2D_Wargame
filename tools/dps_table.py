"""tools/dps_table.py — таблица DPS орудий: калибры с шагом 10 мм, урон и пробитие на 0/25/50/75/100% ползунков.
Запуск из корня проекта: python tools/dps_table.py"""
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import PX_PER_M
from vehicles import (VEHICLE_TYPES, SPGSpec, SPG_PARAMS, GUN_TUNE_PARAMS,
                      damage_range, pen_range, remap, ammo_stats)
from tools.tank_snapshot import SNAPSHOT_DIR          # тот же адрес, что и у снимков техники

CAL_STEP_MM = 10                                      # прибавка калибра после каждого расчёта
LEVELS = (0.0, 0.25, 0.5, 0.75, 1.0)                  # положение ползунков внутри коридора
MID = LEVELS.index(0.5)
DMG_STEP = GUN_TUNE_PARAMS["gun_damage"].step
PEN_STEP = GUN_TUNE_PARAMS["gun_penetration"].step
LABEL_W = 17
CELL_W = 9

def calibers(param):
    """Калибры от минимума ползунка до максимума с шагом CAL_STEP_MM."""
    cal = param.min
    while cal <= param.max:
        yield cal
        cal += CAL_STEP_MM

def pct(t):
    return f"{round(t * 100)}%"

def title(text):
    return ["", "=" * 78, text, "=" * 78]

def make_spec(vtype, cal, damage, pen):
    """Спецификация на эталонном шасси типа техники (броня и мощность по умолчанию)."""
    values = {key: p.default for key, p in vtype.params.items()}
    values["gun_caliber_mm"] = cal
    values["gun_damage"] = damage
    values["gun_penetration"] = pen
    # values["special_ammo"] = "hesh"      # раскомментировать, чтобы в слоте 2 считался HESH (калибр от 105 мм)
    return vtype.spec_cls.from_values(values, unbounded=True)

def ammo_dps(spec):
    """{имя снаряда: урон / перезарядка} для всех слотов орудия."""
    result = {}
    for kind in spec.ammo_kinds:
        st = ammo_stats(spec, kind)
        result[kind.name] = st.damage / st.reload
    return result

# ==========================================
# ОБТ И ПТ-САУ
# ==========================================
def vehicle_section(vtype):
    out = title(f"{vtype.label}: DPS бронебойного = урон / перезарядка")
    summary = []
    for cal in calibers(vtype.params["gun_caliber_mm"]):
        d_rng = damage_range(cal, vtype.gun_profile)
        p_rng = pen_range(cal, vtype.gun_profile)
        dmgs = [remap(t, (0.0, 1.0), d_rng, DMG_STEP) for t in LEVELS]
        pens = [remap(t, (0.0, 1.0), p_rng, PEN_STEP) for t in LEVELS]

        out.append("")
        out.append(f"Калибр {cal:.0f} мм | урон {d_rng[0]:.0f}..{d_rng[1]:.0f} | "
                   f"пробитие {p_rng[0]:.0f}..{p_rng[1]:.0f} мм")
        out.append("пробитие, %".ljust(LABEL_W) + "".join(f"{pct(t):>{CELL_W}}" for t in LEVELS))
        out.append("пробитие, мм".ljust(LABEL_W) + "".join(f"{p:>{CELL_W}.0f}" for p in pens))

        values, mid_spec = [], None
        for di, (dt, dmg) in enumerate(zip(LEVELS, dmgs)):
            row = f"урон {pct(dt):>4} {dmg:>5.0f}".ljust(LABEL_W)
            for pi, pen in enumerate(pens):
                spec = make_spec(vtype, cal, dmg, pen)
                values.append(spec.dps)
                if di == MID and pi == MID:
                    mid_spec = spec
                row += f"{spec.dps:>{CELL_W}.1f}"
            out.append(row)
        summary.append((cal, mid_spec, min(values), max(values)))

    out += summary_lines(summary)
    return out

def summary_lines(summary):
    """Сводка по калибрам: точка 50%/50% и разброс DPS бронебойного по всей матрице."""
    names = list(ammo_dps(summary[0][1]))
    out = ["", f"--- Сводка (урон 50% / пробитие 50%) ---"]
    out.append(f"{'Кал.':>5} {'Урон':>6} {'Проб.':>6} {'Перез.':>7}"
               + "".join(f"{n:>8}" for n in names) + f"  {'ББ мин':>8} {'ББ макс':>8}")
    for cal, spec, lo, hi in summary:
        per_ammo = ammo_dps(spec)
        out.append(f"{cal:>5.0f} {spec.damage:>6.0f} {spec.penetration:>6.0f} {spec.reload:>7.2f}"
                   + "".join(f"{per_ammo.get(n, 0.0):>8.1f}" for n in names)
                   + f"  {lo:>8.1f} {hi:>8.1f}")
    return out

# ==========================================
# САУ (ползунков урона и пробития нет: считается по калибру)
# ==========================================
def spg_section():
    params = SPG_PARAMS
    out = title("САУ: DPS = урон в зоне максимума / перезарядка (по площади, без брони)")
    out.append(f"{'Кал.':>5} {'Урон':>7} {'Перез.':>7} {'DPS':>8} {'Дальн.,м':>9} {'Радиус,м':>9}")
    for cal in calibers(params["gun_caliber_mm"]):
        values = {key: p.default for key, p in params.items()}
        values["gun_caliber_mm"] = cal
        spec = SPGSpec.from_values(values)
        g = spec.shell_stats
        out.append(f"{cal:>5.0f} {spec.damage:>7.0f} {spec.reload:>7.1f} {spec.dps:>8.1f} "
                   f"{g.range_max_px / PX_PER_M:>9.0f} {g.outer_radius_px / PX_PER_M:>9.1f}")
    return out

# ==========================================
# ЗАПИСЬ
# ==========================================
def main():
    out = ["ТАБЛИЦА DPS ОРУДИЙ — 2D Wargame",
           f"Создан: {datetime.datetime.now():%Y-%m-%d %H:%M:%S}",
           f"Калибры: от минимума ползунка, шаг {CAL_STEP_MM} мм; ползунки урона и пробития: "
           + ", ".join(pct(t) for t in LEVELS),
           "Шасси: эталонное (броня и мощность по умолчанию), ограничение калибра по классу корпуса снято.",
           "DPS = урон / перезарядка (бумажный: пробитие против брони не учитывается)."]
    for vtype in VEHICLE_TYPES.values():
        if vtype.playable:
            out += vehicle_section(vtype)
    out += spg_section()

    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(SNAPSHOT_DIR, f"dps_table_{stamp}.txt")
    with open(path, "w", encoding="utf-8-sig") as fh:      # BOM, как у снимков техники
        fh.write("\n".join(out) + "\n")
    print(f"Таблица DPS: {path}")

if __name__ == "__main__":
    main()