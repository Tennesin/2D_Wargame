"""ai/team/hazards.py — зоны обстрела САУ и общие проверки «не заденет ли своих».
Работает только при включённом friendly_fire: иначе союзники от фугасов неуязвимы."""
import math
from typing import NamedTuple

from engine import PX_PER_M, WORLD, clamp, heading_vector, obb_distance_to_point

SAFE_MARGIN_M = 2.0          # запас к радиусу взрыва (поверх габарита самого бота)
EXIT_EXTRA_M = 2.0           # на сколько метров за кромку выводим бота из зоны
WAIT_EXTRA_M = 1.0           # на сколько метров за кромкой ждём, если цель внутри зоны
ALLY_SPLASH_MARGIN_M = 1.5   # запас вокруг осколочного взрыва обычных ботов
WORLD_MARGIN_M = 8.0         # точки выхода не ставим ближе этого к краю мира

class Zone(NamedTuple):
    x: float
    y: float
    r: float          # радиус, уже увеличенный на габарит бота и запас
    ttl: float        # секунд до падения (у мягких зон не используется)
    key: int          # идентификатор источника (для сравнения наборов зон)
    soft: bool        # True: САУ только собирается стрелять; не выгоняет, лишь не пускает внутрь

def friendly_fire_on(ctx):
    settings = getattr(ctx, "settings", None)
    return settings is not None and settings.friendly_fire

def allies_near(ctx, me, x, y, radius):
    """Есть ли живой союзник me (кроме него самого), чей корпус задевает круг (x, y, radius)."""
    for b in ctx.fleet.bots:
        t = b.tank
        if t is me or not t.alive:
            continue
        if obb_distance_to_point(t.hull_obb(), x, y) < radius:
            return True
    return False

def _inside_world(x, y):
    mx = WORLD.half_w_px - WORLD_MARGIN_M * PX_PER_M
    my = WORLD.half_h_px - WORLD_MARGIN_M * PX_PER_M
    return clamp(x, -mx, mx), clamp(y, -my, my)

def safe_goal(me, goal, zones):
    """Если цель лежит внутри зоны, заменяет её точкой у кромки со стороны бота.
    Возвращает (цель, ждём_ли_у_кромки). Мягкую зону, в которой бот уже стоит, не учитываем."""
    gx, gy = goal
    waiting = False
    extra = WAIT_EXTRA_M * PX_PER_M
    for _ in range(2):                                   # вторая проходка нужна при перекрытии зон
        changed = False
        for z in zones:
            if z.soft and math.hypot(me.x - z.x, me.y - z.y) < z.r:
                continue
            if math.hypot(gx - z.x, gy - z.y) >= z.r:
                continue
            bx, by = me.x - z.x, me.y - z.y
            d = math.hypot(bx, by)
            if d < 1.0:
                continue
            k = (z.r + extra) / d
            gx, gy = z.x + bx * k, z.y + by * k
            changed = waiting = True
        if not changed:
            break
    if waiting:
        gx, gy = _inside_world(gx, gy)
    return (gx, gy), waiting

class HazardBoard:
    """Все места, куда в ближайшие секунды может упасть фугас САУ."""

    def __init__(self, effects, settings, fleet):
        self.effects = effects
        self.settings = settings
        self.fleet = fleet

    def zones(self, me):
        """Зоны, опасные для me. Радиус увеличен на габарит me: центр бота должен быть за кромкой."""
        if not self.settings.friendly_fire:
            return ()
        grow = me.spec.HULL_REACH_PX + SAFE_MARGIN_M * PX_PER_M
        out = []
        for shell in self.effects.artillery_shells:      # уже летящие снаряды
            if not shell.alive:
                continue
            tx, ty = shell.target
            out.append(Zone(tx, ty, shell.stats.outer_radius_px + grow, shell.time_left,
                            id(shell), False))
        for b in self.fleet.bots:                         # САУ, которые вот-вот выстрелят
            zone = getattr(b.brain, "pending_zone", None)
            if zone is None or b.tank is me:
                continue
            x, y, r = zone
            out.append(Zone(x, y, r + grow, 0.0, id(b), True))
        return tuple(out)

    def escape_point(self, me):
        """Куда ехать, чтобы выйти из зон летящих снарядов. None: бот вне зон.
        Мягкие зоны (САУ только собирается стрелять) не выгоняют: САУ сама уступит тому, кто внутри."""
        zones = [z for z in self.zones(me) if not z.soft]
        if not zones:
            return None
        px, py = me.x, me.y
        extra = EXIT_EXTRA_M * PX_PER_M
        moved = False
        for _ in range(3):                                # точка выхода из одной зоны может лежать в другой
            pushed = False
            for z in zones:
                dx, dy = px - z.x, py - z.y
                d = math.hypot(dx, dy)
                if d >= z.r:
                    continue
                if d < 1.0:                               # встали ровно в центр: выходим по курсу корпуса
                    dx, dy = heading_vector(me.hull_angle)
                    d = 1.0
                k = (z.r + extra) / d
                px, py = z.x + dx * k, z.y + dy * k
                pushed = moved = True
            if not pushed:
                break
        return _inside_world(px, py) if moved else None