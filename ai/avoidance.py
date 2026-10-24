"""ai/avoidance.py — локальное избегание союзников: объезд и ограничение скорости сближения."""
import math

from engine import PX_PER_M, clamp, heading_vector

LOOK_BASE_M = 10.0        # минимальная дальность «щупа» вперёд
LOOK_PER_MS = 1.2         # плюс метров на каждый м/с собственной скорости
MARGIN_M = 1.5            # запас между корпусами
MAX_DEFLECT_DEG = 55.0    # максимальный увод курса от одного союзника
MAX_TOTAL_DEG = 75.0      # и суммарно от всех
HARD_GAP_M = 1.0          # просвет меньше этого: стоим
TOUCH_MS = 0.7            # допустимая скорость сближения вплотную (ниже порога урона тарана)
BRAKE_MS2 = 2.5           # расчётное торможение (BRAKE_DECEL ≈ 3.3 м/с², берём с запасом)
SIDE_HOLD_S = 1.5         # сколько секунд помним выбранную сторону объезда

def _radius(tank):
    s = tank.spec
    return (s.COLLISION_HALF_W_PX + s.COLLISION_HALF_L_PX) / 2.0

class AllyAvoider:
    """Корректирует (курс, газ) мозга: уводит курс от союзника на пути и не даёт подъехать к нему быстро."""

    def __init__(self):
        self._side = {}          # id(союзника) -> [сторона объезда (+1 вправо), ttl]

    def adjust(self, dt, me, heading, go, ctx):
        if go == 0.0 or me.stunned:
            return heading, go
        for mem in self._side.values():
            mem[1] -= dt
        self._side = {k: m for k, m in self._side.items() if m[1] > 0.0}

        fwd = 1.0 if go > 0.0 else -1.0                 # go < 0: едем задом, курс корпуса смотрит назад
        dx, dy = heading_vector(heading)
        dx, dy = dx * fwd, dy * fwd                     # куда реально поедем
        rx, ry = -dy, dx                                # вправо от направления движения
        mvx, mvy = me.velocity_px()
        v_along = (mvx * dx + mvy * dy) / PX_PER_M      # м/с вдоль движения
        look = (LOOK_BASE_M + LOOK_PER_MS * max(0.0, v_along)) * PX_PER_M
        r_me = _radius(me)
        margin = MARGIN_M * PX_PER_M

        shift, cap_ms, brake = 0.0, float("inf"), False
        for b in ctx.fleet.bots:
            ally = b.tank
            if ally is me or not ally.alive:
                continue
            px, py = ally.x - me.x, ally.y - me.y
            reach = r_me + _radius(ally) + margin
            along = px * dx + py * dy
            if along <= 0.0 or along > look + reach:
                continue                                 # позади или далеко
            lateral = px * rx + py * ry
            if abs(lateral) >= reach:
                continue                                 # мимо курса

            # сторона объезда: от союзника; лоб в лоб — все уходят вправо (правило дороги)
            mem = self._side.get(id(ally))
            if mem is None:
                side = 1.0 if (abs(lateral) < 0.15 * reach or lateral < 0.0) else -1.0
                mem = self._side[id(ally)] = [side, SIDE_HOLD_S]
            mem[1] = SIDE_HOLD_S
            depth = 1.0 - abs(lateral) / reach                       # 0..1: насколько точно по курсу
            near = 1.0 - clamp(along / (look + reach), 0.0, 1.0)     # 0..1: насколько близко
            shift += mem[0] * MAX_DEFLECT_DEG * depth * (0.3 + 0.7 * near)

            # скорость: можно сближаться не быстрее, чем успеем остановиться до HARD_GAP_M
            gap = (math.hypot(px, py) - r_me - _radius(ally)) / PX_PER_M
            avx, avy = ally.velocity_px()
            ally_along = (avx * dx + avy * dy) / PX_PER_M
            closing = v_along - ally_along
            allowed = 0.0 if gap <= HARD_GAP_M else math.sqrt(2.0 * BRAKE_MS2 * (gap - HARD_GAP_M)) + TOUCH_MS
            cap_ms = min(cap_ms, max(0.0, allowed + ally_along))
            if closing > allowed * 1.1:
                brake = True

        if shift:
            heading = (heading + clamp(shift, -MAX_TOTAL_DEG, MAX_TOTAL_DEG)) % 360.0
        if brake and v_along > 0.5:
            go = -fwd                                    # противоположный газ = торможение (decel_brake)
        elif cap_ms != float("inf"):
            cap_go = cap_ms * 3.6 / max(me.spec.v_max, 1.0)
            go = fwd * min(abs(go), cap_go)
        return heading, go