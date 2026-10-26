"""world/rock_physics.py — подвижные камни: толчок тараном, скольжение с трением,
перенос камня между ячейками карты. Генерацию и запросы к местности не знает: работает через TerrainMap."""
import math

from engine import (PX_PER_M, find_free_fraction,
                    obb_convex_contact, obb_hits_convex)
from .patch_geometry import patches_overlap

GRAVITY_MS2 = 9.81
ROCK_FRICTION = 0.6          # трение камня о землю: торможение = ROCK_FRICTION * g, м/с²
ROCK_STOP_PX = 5.0           # px/с: медленнее этого камень стоит

class RockMover:
    def __init__(self, terrain):
        self.terrain = terrain
        self._moving = []           # камни, которые сейчас скользят
        self._listeners = []        # функции (x, y, r): зона круга изменилась

    # ---------- подписки ----------
    def add_move_listener(self, fn):
        """fn(x, y, r) вызывается при каждом сдвиге камня: для старого и нового положения."""
        self._listeners.append(fn)

    # ---------- контакт и толчок ----------
    def pushables_touching(self, obb, pad=0.0):
        """Подвижные камни, которых касается прямоугольник obb (с запасом pad px):
        [(камень, nx, ny), ...]. (nx, ny) — нормаль контакта ОТ прямоугольника К камню."""
        cx, cy, hw, hl, ang = obb
        result = []
        for p in self.terrain.patches_near(cx, cy, math.hypot(hw, hl) + pad):
            if not p.kind.pushable:
                continue
            best = None
            for tri in p.tris:                       # камень невыпуклый: берём треугольник с наибольшей глубиной
                c = obb_convex_contact(cx, cy, hw + pad, hl + pad, ang, tri)
                if c is not None and (best is None or c[0] > best[0]):
                    best = c
            if best is not None:
                result.append((p, best[1], best[2]))
        return result

    def push(self, rock, vx, vy):
        """Придать камню скорость (px/с): дальше он скользит в update()."""
        rock.vx, rock.vy = vx, vy
        if rock not in self._moving:
            self._moving.append(rock)

    # ---------- скольжение ----------
    def update(self, dt, obbs_near):
        """Скольжение толкнутых камней: трение гасит скорость, каждый шаг проверяется на препятствия.
        obbs_near(x, y, radius) -> [obb, ...] — прямоугольники стен и танков (их даёт игра)."""
        if not self._moving:
            return
        still = []
        for rock in self._moving:
            speed = math.hypot(rock.vx, rock.vy)
            drop = ROCK_FRICTION * GRAVITY_MS2 * PX_PER_M * dt
            if speed <= drop + ROCK_STOP_PX:
                rock.vx = rock.vy = 0.0
                continue
            k = (speed - drop) / speed
            rock.vx *= k
            rock.vy *= k
            dx, dy = rock.vx * dt, rock.vy * dt
            if self._blocked(rock, dx, dy, obbs_near):
                frac = 0.0
                if not self._blocked(rock, 0.0, 0.0, obbs_near):
                    frac = find_free_fraction(
                        lambda f: self._blocked(rock, dx * f, dy * f, obbs_near))
                self._shift(rock, dx * frac, dy * frac)
                rock.vx = rock.vy = 0.0              # упёрся: стоит
                continue
            self._shift(rock, dx, dy)
            still.append(rock)
        self._moving = still

    def _blocked(self, rock, dx, dy, obbs_near):
        """Помешает ли что-то камню оказаться со сдвигом (dx, dy): край мира, другой твёрдый камень
        или глубокая вода, стена, танк."""
        moved = rock.shifted(dx, dy)
        hw, hh = self.terrain.half_w, self.terrain.half_h
        if any(abs(px) > hw or abs(py) > hh for px, py in moved.pts):
            return True
        for q in self.terrain.patches_near(moved.x, moved.y, moved.r_max):
            if q is not rock and q.kind.solid and patches_overlap(moved, q):
                return True
        if self.terrain.deep_overlaps(moved):
            return True
        for ox, oy, ohw, ohl, ang in obbs_near(moved.x, moved.y, moved.r_max):
            if any(obb_hits_convex(ox, oy, ohw, ohl, ang, tri) for tri in moved.tris):
                return True
        return False

    def _shift(self, rock, dx, dy):
        if dx == 0.0 and dy == 0.0:
            return
        old = (rock.x, rock.y, rock.r_max)
        rock.move_by(dx, dy)
        self._register(rock)
        for fn in self._listeners:
            fn(*old)
            fn(rock.x, rock.y, rock.r_max)

    def _register(self, rock):
        """Переносит камень в список той ячейки поиска, где теперь его центр.
        Списки в TerrainMap правим на месте, поэтому ничего перегенерировать не нужно."""
        t = self.terrain
        new = t.cell_of(rock.x, rock.y)
        if new == rock.cell:
            return
        old_list = t.cached_cell(rock.cell)
        if rock in old_list:
            old_list.remove(rock)
        new_list = t.cached_cell(new)
        if rock not in new_list:
            new_list.append(rock)
        rock.cell = new