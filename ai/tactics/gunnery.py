"""ai/tactics/gunnery.py — упреждение, оценка урона по граням, точка фланга."""
import math
from dataclasses import dataclass

from combat import resolve_hit, impact_cos, pen_after_modules
from engine import clamp, PX_PER_M
from vehicles import ammo_stats
from vehicles.chassis.params import KMH_TO_PX

def lead_point(shooter, target, lead_k=1.0):
    """Точка упреждения: где будет цель, когда долетит снаряд. Две итерации."""
    sx, sy = shooter.muzzle_point()
    speed = shooter.round_stats().speed_px
    vx, vy = target.velocity_px()
    px, py = target.x, target.y
    for _ in range(2):
        t = math.hypot(px - sx, py - sy) / speed
        px = target.x + vx * t * lead_k
        py = target.y + vy * t * lead_k
    return px, py

AIM_LATERALS_M = (-0.36, 0.0, 0.36)      # = AIM_SPREAD_M * 0.3

def _mean_frac(defender, pen, from_deg, hull_deg, laterals=AIM_LATERALS_M):
    """Средняя доля урона по броне defender для лучей с азимута from_deg при курсе корпуса hull_deg.
    Лучи, прошедшие мимо корпуса, не считаются. Если мимо все: 1.0 (худший случай для защитника)."""
    total, n = 0.0, 0
    for lat in laterals:
        res = defender.armor_along(from_deg, hull_deg, lat)
        if res is None:
            continue
        armor, cos_i = res
        total += resolve_hit(pen, armor, cos_i).damage_frac
        n += 1
    return total / n if n else 1.0

def damage_by_aspect(me, enemy):
    """Доля урона моего снаряда по лбу, борту и корме врага (лучи с трёх направлений от его корпуса,
    среднее по AIM_LATERALS_M). Броню и угол даёт раскладка корпуса, а не нормали с cos = 1."""
    pen = me.spec.penetration
    h = enemy.hull_angle
    return {
        "front": _mean_frac(enemy, pen, h, h),
        "side": _mean_frac(enemy, pen, h + 90.0, h),
        "rear": _mean_frac(enemy, pen, h + 180.0, h),
    }

def seconds_to_break(me, wall, cos_impact=1.0, normal=None, min_frac=0.15):
    """Сколько секунд бот будет ломать стену, или None, если пробить не получится."""
    if wall.hp <= 0.0:
        return None
    frac = wall.hit_result(me.spec.penetration, cos_impact, normal).damage_frac
    if frac < min_frac:
        return None
    shots = math.ceil(wall.hp / (me.spec.damage * frac))
    return shots * me.spec.reload

# ==========================================
# КОНСТАНТЫ ОЦЕНКИ
# ==========================================
BREACH_MAX_S = 25.0           # дольше этого стену не долбим
MIN_USEFUL_DAMAGE = 0.15      # меньше этой доли урона по цели не стреляем

TTK_CAP_S = 60.0              # «убить невозможно»: время убийства ограничиваем сверху
NO_DAMAGE = 0.05              # доля урона ниже этого считается нулевой

KITE_RANGE_K = 0.85           # какую долю дальности снаряда занимает дальняя дистанция боя
CLOSE_DIST_M = 12.0           # самая ближняя желаемая дистанция боя

HULL_ANGLES = (0.0, 15.0, -15.0, 25.0, -25.0, 35.0, -35.0, 45.0, -45.0)   # проба поворота корпуса, °
AIM_JITTER_DEG = 6.0          # на столько градусов враг может промахнуться мимо центра корпуса

OUTFLANK_MIN_RADIUS_M = 5.0   # ближе этого радиус облёта не считаем (угловая скорость не взлетает)

AMMO_SPEED_EXP = 0.5          # штраф за медленный снаряд: (скорость типа / скорость ББ) ** этой степени
AMMO_SWITCH_GAIN = 1.15       # новый тип берём, только если он лучше текущего больше чем в столько раз

# ==========================================
# МАТЧАП: КТО КОГО УБЬЁТ БЫСТРЕЕ
# ==========================================
@dataclass(frozen=True)
class Matchup:
    front_ratio: float    # >1: в лоб я убиваю быстрее, чем он меня
    flank_ratio: float    # то же, если я бью в борт или корму (он по-прежнему бьёт в мой лоб)

def _ttk(shooter, target, frac):
    """Секунды, за которые shooter убьёт target при доле урона frac."""
    if frac < NO_DAMAGE:
        return TTK_CAP_S
    sp = shooter.spec
    shots = max(1, math.ceil(target.hp / (sp.damage * frac)))
    return min(TTK_CAP_S, shots * sp.reload)

def evaluate_matchup(me, enemy):
    """Оценка в обе стороны по текущему HP. Дорогая, поэтому мозг кэширует её по «вёдрам» HP."""
    mine = damage_by_aspect(me, enemy)         # мои снаряды по граням врага
    theirs = damage_by_aspect(enemy, me)       # его снаряды по моим граням
    my_front = _ttk(me, enemy, mine["front"])
    my_flank = min(_ttk(me, enemy, mine["side"]), _ttk(me, enemy, mine["rear"]))
    his_front = _ttk(enemy, me, theirs["front"])
    return Matchup(his_front / my_front, his_front / my_flank)

# ==========================================
# МОБИЛЬНОСТЬ И ДИСТАНЦИЯ
# ==========================================

def outflank_feasibility(me, enemy, dist_px):
    """0..1: успею ли я обойти врага, пока он доворачивает орудие.
    Угловая скорость облёта по окружности радиуса dist равна v / R, но не больше моего поворота корпуса.
    Сравниваем с тем, как быстро враг водит башней (плюс половина поворота его корпуса)."""
    r_px = max(dist_px, OUTFLANK_MIN_RADIUS_M * PX_PER_M)
    omega = math.degrees(me.spec.v_avg * KMH_TO_PX / r_px)
    omega = min(omega, me.spec.hull_turn)
    track = enemy.spec.turret_turn + 0.5 * enemy.spec.hull_turn
    return clamp(0.35 + 0.65 * omega / max(track, 1.0), 0.0, 1.0)

def preferred_distance_m(me, enemy, base_m, edge_k=1.0):
    """Желаемая дистанция боя из характеристик. Быстрее и скорострельнее врага: держимся дальше
    (кайтинг). Медленнее и слабее по темпу: сокращаем дистанцию."""
    spd = me.spec.v_avg / max(enemy.spec.v_avg, 1.0)
    rel = enemy.spec.reload / max(me.spec.reload, 0.1)
    edge = clamp(0.6 * math.log2(spd) + 0.4 * math.log2(rel), -1.0, 1.0) * edge_k
    far_m = me.spec.SHELL_RANGE_PX / PX_PER_M * KITE_RANGE_K
    if edge >= 0.0:
        dist = base_m + edge * max(0.0, far_m - base_m)
    else:
        dist = base_m + edge * max(0.0, base_m - CLOSE_DIST_M)
    return min(dist, max(far_m, CLOSE_DIST_M))

# ==========================================
# УГОЛ КОРПУСА
# ==========================================

def best_hull_heading(me, enemy, to_enemy_deg):
    """Курс корпуса, при котором враг наносит мне меньше урона (с запасом на неточность его прицела).
    Если поворот ничего не даёт, возвращает курс прямо на врага."""
    pen = enemy.spec.penetration
    best_h, best_key = to_enemy_deg, None
    for off in HULL_ANGLES:
        h = to_enemy_deg + off
        expo = max(_mean_frac(me, pen, to_enemy_deg + j, h)
                   for j in (-AIM_JITTER_DEG, 0.0, AIM_JITTER_DEG))
        key = (round(expo, 2), abs(off))               # при равенстве выбираем меньший поворот
        if best_key is None or key < best_key:
            best_key, best_h = key, h
    return best_h % 360.0

# ==========================================
# ВЫБОР СНАРЯДА
# ==========================================

def shot_geometry(me, enemy):
    """Как мой снаряд ляжет в центр корпуса врага из текущей позиции: (нормаль, cos угла, точка).
    Луч идёт из центра танка, как у настоящего снаряда. Не достаём корпус: (None, 1.0, None)."""
    dx, dy = enemy.x - me.x, enemy.y - me.y
    ln = math.hypot(dx, dy)
    if ln < 1.0:
        return None, 1.0, None
    ux, uy = dx / ln, dy / ln
    over = RAY_OVERSHOOT_M * PX_PER_M
    end_x, end_y = enemy.x + ux * over, enemy.y + uy * over
    hit = enemy.raycast(me.x, me.y, end_x, end_y)
    if hit is None or hit[2] is None:
        return None, 1.0, None
    _, t, normal = hit
    point = (me.x + (end_x - me.x) * t, me.y + (end_y - me.y) * t)
    return normal, abs(ux * normal[0] + uy * normal[1]), point

def ammo_value(me, target, kind, normal, cos_i, point):
    """Ожидаемый урон в секунду снарядом kind по цели при такой геометрии удара."""
    stats = ammo_stats(me.spec, kind)
    pen = stats.penetration
    if point is not None:
        pen = pen_after_modules(target, pen, stats, *point)           # КС на гусенице
    frac = target.hit_result(pen, impact_cos(stats, cos_i), normal).damage_frac
    dps = stats.damage * max(frac, stats.min_frac) / stats.reload      # min_frac: гарантия осколков фугаса
    return dps * (stats.speed_px / me.spec.SHELL_SPEED_PX) ** AMMO_SPEED_EXP

def best_ammo(me, target, normal, cos_i, point, banned=()):
    """Лучший тип снаряда по цели. Текущий меняем, только если выигрыш заметный (гистерезис).
    banned: типы, которыми сейчас бить нельзя (если запрещён текущий, уходим с него при любом выигрыше)."""
    scores = {k: ammo_value(me, target, k, normal, cos_i, point)
              for k in me.spec.ammo_kinds if k not in banned}
    if not scores:
        return me.ammo
    best = max(scores, key=scores.get)
    if best is me.ammo or scores[best] <= scores.get(me.ammo, 0.0) * AMMO_SWITCH_GAIN:
        return me.ammo
    return best

# ==========================================
# УРОН ИЗ ТЕКУЩЕЙ ПОЗИЦИИ
# ==========================================

AIM_SPREAD_M = 1.2            # боковой разброс пробных точек поперёк корпуса врага, м
RAY_OVERSHOOT_M = 3.0         # на сколько метров луч заходит за корпус цели

def shot_fraction_now(me, enemy):
    """Максимальная доля урона по броне (любым пробивным снарядом) из текущей позиции.
    Фугас не считаем: его осколочный минимум не должен скрывать «бить нечем»."""
    rounds = [s for s in (ammo_stats(me.spec, k) for k in me.spec.ammo_kinds)
              if s.min_frac <= 0.0]
    ex, ey = enemy.x, enemy.y
    dx, dy = ex - me.x, ey - me.y
    ln = math.hypot(dx, dy)
    if ln < 1.0:
        return 1.0
    px, py = -dy / ln, dx / ln
    spread = AIM_SPREAD_M * PX_PER_M
    best = 0.0
    overshoot = RAY_OVERSHOOT_M * PX_PER_M
    for k in (0.0, -1.0, 1.0):
        tx, ty = ex + px * spread * k, ey + py * spread * k
        sx, sy = tx - me.x, ty - me.y
        sl = math.hypot(sx, sy)
        ux, uy = sx / sl, sy / sl
        end_x, end_y = tx + ux * overshoot, ty + uy * overshoot
        hit = enemy.raycast(me.x, me.y, end_x, end_y)
        if hit is None:
            continue
        _, t_hit, normal = hit
        cos_i = 1.0 if normal is None else abs(ux * normal[0] + uy * normal[1])
        hx, hy = me.x + (end_x - me.x) * t_hit, me.y + (end_y - me.y) * t_hit
        for st in rounds:
            pen = pen_after_modules(enemy, st.penetration, st, hx, hy)
            best = max(best, enemy.hit_result(pen, impact_cos(st, cos_i), normal).damage_frac)
    return best