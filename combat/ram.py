"""combat/ram.py — правила тарана."""
import math
from dataclasses import dataclass

# ==========================================
# 1. ПРАВИЛА
# ==========================================

RESTITUTION_ROCK = 0.15      # упругость удара о камень (0 = «прилип», 1 = идеальный отскок)
RESTITUTION_TANK = 0.25      # то же для танка о танк (базовая: ram_restitution её ослабляет)
PUSH_MASS_LIMIT = 1.0        # инертное тело (камень) сдвигается, только если m_тела < m_танка * этого числа
MIN_CLOSING_MS = 0.4         # медленнее этого сближения, м/с, таран не считаем (просто упёрлись)

SAFE_DV_MS = 1.0             # изменение скорости до этого значения урона не даёт
DAMAGE_PER_MS = 100.0        # HP за каждый м/с сверх безопасного
ZONE_K = {"front": 0.5, "side": 1.0, "rear": 1.3}   # лоб крепче всего, корма слабее всего

RAM_FRICTION = 0.35          # трение сталь о сталь на контакте: предел касательного импульса = μ · нормальный
RESTITUTION_FAST_MS = 12.0   # при таком сближении упругость падает на RESTITUTION_FAST_LOSS
RESTITUTION_FAST_LOSS = 0.5  # сильный удар деформирует корпуса и отскакивает хуже
RESTITUTION_GLANCE_LOSS = 0.5  # скользящий удар отскакивает хуже лобового

# ==========================================
# 2. РЕЗУЛЬТАТ
# ==========================================

@dataclass(frozen=True)
class RamResult:
    u1: float          # новая скорость тела 1 вдоль нормали, м/с
    u2: float          # новая скорость тела 2 вдоль нормали, м/с

@dataclass(frozen=True)
class RamResult2D:
    jn: float          # нормальный импульс, т·м/с
    jt: float          # касательный импульс (с трением), т·м/с
    dv1: tuple         # изменение скорости центра тела 1, (x, y) м/с
    dw1: float         # изменение угловой скорости тела 1, рад/с
    dv2: tuple
    dw2: float
    closing: float     # скорость сближения в точке контакта до удара, м/с
    restitution: float # использованная упругость

# ==========================================
# 3. ФОРМУЛЫ
# ==========================================

def can_push(pusher_mass_t, target_mass_t):
    """Может ли танк сдвинуть инертное тело (камень): оно должно быть легче."""
    return target_mass_t < pusher_mass_t * PUSH_MASS_LIMIT

def resolve_ram(m1, u1, m2, u2, restitution):
    """Удар вдоль нормали (от тела 1 к телу 2). Массы в тоннах, скорости в м/с
    (плюс = в сторону тела 2). Возвращает новые скорости обоих тел."""
    closing = u1 - u2
    j = (1.0 + restitution) * (m1 * m2 / (m1 + m2)) * closing
    return RamResult(u1 - j / m1, u2 + j / m2)

def ram_damage(dv_ms, zone):
    """Урон танку от тарана. dv_ms — на сколько м/с изменилась ЕГО скорость, zone — грань, принявшая удар."""
    return max(0.0, dv_ms - SAFE_DV_MS) * DAMAGE_PER_MS * ZONE_K[zone]

def ram_restitution(base, closing_ms, head_on):
    """Упругость удара. head_on: 1 = строго в лоб (скорость сближения направлена по нормали),
    0 = скользящий. Сильный и скользящий удары отскакивают слабее."""
    fast = min(1.0, closing_ms / RESTITUTION_FAST_MS)
    glance = 1.0 - max(0.0, min(1.0, head_on))
    return base * (1.0 - RESTITUTION_FAST_LOSS * fast) * (1.0 - RESTITUTION_GLANCE_LOSS * glance)

def _cross(ax, ay, bx, by):
    return ax * by - ay * bx

def resolve_ram_2d(m1, i1, v1, w1, r1, m2, i2, v2, w2, r2, n,
                   restitution=RESTITUTION_TANK, friction=RAM_FRICTION):
    """Удар двух твёрдых тел в одной точке контакта."""
    nx, ny = n
    tx, ty = -ny, nx

    # скорость точки контакта каждого тела: v + w × r
    p1x, p1y = v1[0] - w1 * r1[1], v1[1] + w1 * r1[0]
    p2x, p2y = v2[0] - w2 * r2[1], v2[1] + w2 * r2[0]
    rvx, rvy = p2x - p1x, p2y - p1y

    closing = -(rvx * nx + rvy * ny)
    if closing < MIN_CLOSING_MS:
        return None
    speed = math.hypot(rvx, rvy)
    e = ram_restitution(restitution, closing, closing / speed if speed > 1e-9 else 1.0)

    # нормальный импульс: эффективная масса учитывает, как далеко от центра точка контакта
    rn1, rn2 = _cross(r1[0], r1[1], nx, ny), _cross(r2[0], r2[1], nx, ny)
    inv_n = 1.0 / m1 + 1.0 / m2 + rn1 * rn1 / i1 + rn2 * rn2 / i2
    jn = (1.0 + e) * closing / inv_n

    # касательный импульс (трение): гасит скольжение в точке контакта, но не больше μ · jn
    vt = rvx * tx + rvy * ty
    rt1, rt2 = _cross(r1[0], r1[1], tx, ty), _cross(r2[0], r2[1], tx, ty)
    inv_t = 1.0 / m1 + 1.0 / m2 + rt1 * rt1 / i1 + rt2 * rt2 / i2
    jt = -vt / inv_t
    lim = friction * jn
    jt = max(-lim, min(lim, jt))

    jx, jy = jn * nx + jt * tx, jn * ny + jt * ty
    return RamResult2D(
        jn=jn, jt=jt,
        dv1=(-jx / m1, -jy / m1), dw1=-_cross(r1[0], r1[1], jx, jy) / i1,
        dv2=(jx / m2, jy / m2), dw2=_cross(r2[0], r2[1], jx, jy) / i2,
        closing=closing, restitution=e)