"""ai/gunnery.py — упреждение, оценка урона по граням, точка фланга."""
import math
from dataclasses import dataclass

from combat import resolve_hit
from engine import heading_vector, shortest_angle_diff, clamp, PX_PER_M

def lead_point(shooter, target, lead_k=1.0):
    """Точка упреждения: где будет цель, когда долетит снаряд. Две итерации."""
    sx, sy = shooter.muzzle_point()
    speed = shooter.spec.SHELL_SPEED_PX
    vx, vy = target.velocity_px()
    px, py = target.x, target.y
    for _ in range(2):
        t = math.hypot(px - sx, py - sy) / speed
        px = target.x + vx * t * lead_k
        py = target.y + vy * t * lead_k
    return px, py

def damage_by_aspect(me, enemy):
    """Доля урона моего снаряда при прямом ударе (cos = 1) по лбу, борту и корме врага."""
    fx, fy = heading_vector(enemy.hull_angle)
    rx, ry = -fy, fx
    pen = me.spec.penetration
    return {
        "front": enemy.hit_result(pen, 1.0, (fx, fy)).damage_frac,
        "side": enemy.hit_result(pen, 1.0, (rx, ry)).damage_frac,
        "rear": enemy.hit_result(pen, 1.0, (-fx, -fy)).damage_frac,
    }

def flank_point(enemy, dist_px, side):
    """Точка за бортом (слегка в сторону кормы) цели на заданной дистанции. side: +1 / -1."""
    fx, fy = heading_vector(enemy.hull_angle)
    rx, ry = -fy, fx
    return (enemy.x + (rx * side * 0.8 - fx * 0.6) * dist_px,
            enemy.y + (ry * side * 0.8 - fy * 0.6) * dist_px)

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
BREACH_MAX_S = 25.0           # дольше этого стену не долбим (раньше лежало в brain.py)
MIN_USEFUL_DAMAGE = 0.15      # меньше этой доли урона по цели не стреляем (раньше в brain.py)

TTK_CAP_S = 60.0              # «убить невозможно»: время убийства ограничиваем сверху
NO_DAMAGE = 0.05              # доля урона ниже этого считается нулевой

KITE_RANGE_K = 0.85           # какую долю дальности снаряда занимает дальняя дистанция боя
CLOSE_DIST_M = 12.0           # самая ближняя желаемая дистанция боя

HULL_ANGLES = (0.0, 15.0, -15.0, 25.0, -25.0, 35.0, -35.0, 45.0, -45.0)   # проба поворота корпуса, °
AIM_JITTER_DEG = 6.0          # на столько градусов враг может промахнуться мимо центра корпуса

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
    r_m = max(dist_px / PX_PER_M, 5.0)
    omega = math.degrees((me.spec.v_avg / 3.6) / r_m)
    omega = min(omega, me.spec.hull_turn)
    track = enemy.spec.turret_turn + 0.5 * enemy.spec.hull_turn
    return clamp(0.35 + 0.65 * omega / max(track, 1.0), 0.0, 1.0)

def preferred_distance_m(me, enemy, base_m):
    """Желаемая дистанция боя из характеристик. Быстрее и скорострельнее врага: держимся дальше
    (кайтинг). Медленнее и слабее по темпу: сокращаем дистанцию."""
    spd = me.spec.v_avg / max(enemy.spec.v_avg, 1.0)
    rel = enemy.spec.reload / max(me.spec.reload, 0.1)
    edge = clamp(0.6 * math.log2(spd) + 0.4 * math.log2(rel), -1.0, 1.0)
    far_m = me.spec.SHELL_RANGE_PX / PX_PER_M * KITE_RANGE_K
    if edge >= 0.0:
        return base_m + edge * max(0.0, far_m - base_m)
    return base_m + edge * max(0.0, base_m - CLOSE_DIST_M)

# ==========================================
# УГОЛ КОРПУСА
# ==========================================
def _frac_from(me, pen, from_deg, hull_deg):
    """Доля урона, если враг стреляет в центр моего корпуса с направления from_deg (азимут от меня к нему),
    а корпус развёрнут на hull_deg. Какая грань принимает удар, определяет геометрия корпуса."""
    spec = me.spec
    off = shortest_angle_diff(from_deg, hull_deg)
    a = abs(off)
    corner = math.degrees(math.atan2(spec.COLLISION_HALF_W_PX, spec.COLLISION_HALF_L_PX))
    fx, fy = heading_vector(hull_deg)
    if a <= corner:                                    # бьёт в лоб
        normal, cos_i = (fx, fy), math.cos(math.radians(a))
    elif a >= 180.0 - corner:                          # бьёт в корму
        normal, cos_i = (-fx, -fy), math.cos(math.radians(180.0 - a))
    else:                                              # бьёт в борт
        sign = 1.0 if off > 0.0 else -1.0
        normal, cos_i = (-fy * sign, fx * sign), math.cos(math.radians(90.0 - a))
    return resolve_hit(pen, me.armor_at(normal, hull_deg), cos_i).damage_frac

def best_hull_heading(me, enemy, to_enemy_deg):
    """Курс корпуса, при котором враг наносит мне меньше урона (с запасом на неточность его прицела).
    Если поворот ничего не даёт, возвращает курс прямо на врага."""
    pen = enemy.spec.penetration
    best_h, best_key = to_enemy_deg, None
    for off in HULL_ANGLES:
        h = to_enemy_deg + off
        expo = max(_frac_from(me, pen, to_enemy_deg + j, h)
                   for j in (-AIM_JITTER_DEG, 0.0, AIM_JITTER_DEG))
        key = (round(expo, 2), abs(off))               # при равенстве выбираем меньший поворот
        if best_key is None or key < best_key:
            best_key, best_h = key, h
    return best_h % 360.0

# ==========================================
# УРОН ИЗ ТЕКУЩЕЙ ПОЗИЦИИ
# ==========================================
AIM_SPREAD_M = 1.2            # боковой разброс пробных точек поперёк корпуса врага, м

def shot_fraction_now(me, enemy):
    """Максимальная доля урона, которую я нанесу по врагу из текущей позиции (по его реальному положению
    и повороту корпуса). Три прицельные точки: центр и по бокам. Если даже лучшая даёт меньше NO_DAMAGE,
    то бить отсюда бесполезно «гарантированно»."""
    pen = me.spec.penetration
    ex, ey = enemy.x, enemy.y
    dx, dy = ex - me.x, ey - me.y
    ln = math.hypot(dx, dy)
    if ln < 1.0:
        return 1.0
    px, py = -dy / ln, dx / ln
    spread = AIM_SPREAD_M * PX_PER_M
    best = 0.0
    for k in (0.0, -1.0, 1.0):
        tx, ty = ex + px * spread * k, ey + py * spread * k
        sx, sy = tx - me.x, ty - me.y
        sl = math.hypot(sx, sy)
        ux, uy = sx / sl, sy / sl
        hit = enemy.raycast(me.x, me.y, tx + ux * 300.0, ty + uy * 300.0)   # отрезок с запасом за корпус
        if hit is None:
            continue
        _, _t, normal = hit
        cos_i = 1.0 if normal is None else abs(ux * normal[0] + uy * normal[1])
        best = max(best, enemy.hit_result(pen, cos_i, normal).damage_frac)
    return best