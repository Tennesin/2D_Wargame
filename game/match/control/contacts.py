"""game/match/control/contacts.py — участники контактов: танк, стена, камень, граница мира.
Единый интерфейс, чтобы солвер тарана не знал, кто перед ним."""
import math

from engine import PX_PER_M

INF = math.inf

class Rec:
    """Один контакт за кадр: тела, геометрия и накопленные за проходы результаты."""
    __slots__ = ("a", "b", "c", "e0", "energy", "dv_a", "dv_b", "first")

    def __init__(self, a, b, c, e0):
        self.a, self.b, self.c, self.e0 = a, b, c, e0
        self.energy = 0.0          # кДж, потерянные в этом контакте
        self.dv_a = self.dv_b = 0.0
        self.first = None          # первый результат resolve_ram_2d (для отладки и последствий)

class TankBody:
    kind = "tank"
    static = False

    def __init__(self, v):
        self.v = v
        self.obj = v

    @property
    def mass(self):
        return self.v.mass_t

    @property
    def inertia(self):
        return self.v.inertia_t_m2

    def center(self):
        return self.v.hull_obb()[:2]

    def velocity(self):
        vx, vy = self.v.velocity_px(self.v.impact_kmh, include_pending=True)
        return vx / PX_PER_M, vy / PX_PER_M

    def omega(self):
        spin = self.v.hull_rate if self.v.contact_spin is None else self.v.contact_spin
        return math.radians(spin)

    def apply(self, dvx, dvy, dw):
        self.v.apply_velocity_change(dvx, dvy, dw, self.v.push_ramp_s())

    def shove(self, nx, ny, dv):
        self.v.apply_velocity_change(nx * dv, ny * dv, 0.0, 0.0)

    def thrust(self, nx, ny):
        return self.v.push_thrust_kn(nx, ny)

    def resist(self, nx, ny):
        return self.v.push_resist_kn(nx, ny)

    def hold(self, seconds):
        self.v.hold_press(seconds)

class WallBody:
    kind = "wall"
    static = True
    mass = INF
    inertia = INF

    def __init__(self, wall):
        self.wall = wall
        self.obj = wall

    def center(self):
        return self.wall.x, self.wall.y

    def velocity(self):
        return 0.0, 0.0

    def omega(self):
        return 0.0

    def apply(self, dvx, dvy, dw):
        pass

    def shove(self, nx, ny, dv):
        pass

    def thrust(self, nx, ny):
        return 0.0

    def hold(self, seconds):
        pass

class EdgeBody(WallBody):
    """Стена по периметру мира: неразрушаема, танк о неё не ранится."""
    kind = "edge"

    def __init__(self, band):
        self.band = band
        self.obj = band

    def center(self):
        return self.band[0], self.band[1]

class RockBody:
    """Камень. movable: можно сдвинуть ударом (can_push); иначе ведёт себя как стена."""
    kind = "rock"
    inertia = INF                       # вращения у камней нет

    def __init__(self, rock, mover, movable):
        self.rock = rock
        self.obj = rock
        self.mover = mover
        self.static = not movable
        self.mass = rock.mass_t if movable else INF

    def center(self):
        return self.rock.x, self.rock.y

    def velocity(self):
        return self.rock.vx / PX_PER_M, self.rock.vy / PX_PER_M

    def omega(self):
        return 0.0

    def apply(self, dvx, dvy, dw):
        if not self.static:
            self.mover.push(self.rock, self.rock.vx + dvx * PX_PER_M, self.rock.vy + dvy * PX_PER_M)

    def shove(self, nx, ny, dv):
        self.apply(nx * dv, ny * dv, 0.0)

    def thrust(self, nx, ny):
        return 0.0

    def hold(self, seconds):
        pass