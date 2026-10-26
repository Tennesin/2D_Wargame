"""world/natural.py — естественная карта по сиду: прежний процедурный генератор,
результат запекается в сетку ландшафта (озёра, грязь) и список камней. Без pygame."""
import math
import random

from engine import hash_int, SEED_SALT, shrink_polygon, PX_PER_M, WORLD_MIN_M, WORLD_MAX_M, clamp
from .landscape import Landscape, L_MUD, L_SHALLOWS, L_WATER, L_DEEP
from .mapdata import MapData, RockData, MODE_NATURAL
from .patch_geometry import patches_overlap
from .terrain import (
    Patch, SHALLOWS, MUD, ROCK, _make_pts, FEATURE_CELL, SPAWN_CLEAR,
    LAKE_CHANCE, LAKE_RADIUS, MID_SCALE, DEEP_SCALE, MUD_CHANCE, MUD_RADIUS,
    ROCK_CELL_CHANCE, ROCKS_PER_CELL, ROCK_SMALL, ROCK_MEDIUM, ROCK_BIG, ROCK_MEDIUM_P, ROCK_BIG_P,
    LAKE_VERTS, LAKE_STRETCH, LAKE_ROUGH, LAKE_JITTER,
    MUD_VERTS, MUD_STRETCH, MUD_ROUGH, MUD_JITTER,
    ROCK_VERTS, ROCK_STRETCH, ROCK_ROUGH, ROCK_JITTER,
)

class _Generator:
    """Кандидаты по ячейкам генерации (30 м) и проверки пересечений, как раньше в TerrainMap."""

    def __init__(self, seed, width_m, length_m):
        self.seed = seed
        self.half_w = width_m * PX_PER_M / 2.0
        self.half_h = length_m * PX_PER_M / 2.0
        # диапазон ячеек: мир + 1 ячейка запаса
        self.ix = (math.floor(-self.half_w / FEATURE_CELL) - 1, math.floor(self.half_w / FEATURE_CELL) + 1)
        self.iy = (math.floor(-self.half_h / FEATURE_CELL) - 1, math.floor(self.half_h / FEATURE_CELL) + 1)
        self._raw_cache = {}
        self._lake_cache = {}

    def raw(self, ix, iy):
        key = (ix, iy)
        value = self._raw_cache.get(key)
        if value is None:
            value = self._raw_cache[key] = self._make_raw(ix, iy)
        return value

    def _make_raw(self, ix, iy):
        """Кандидаты ячейки без учёта соседей: (озеро или None, грязь или None, [камни])."""
        rng = random.Random(hash_int(ix, iy, self.seed + SEED_SALT["terrain"]))
        ox, oy = ix * FEATURE_CELL, iy * FEATURE_CELL

        def place(kind, radius, n, stretch, rough, jitter):
            x = ox + rng.uniform(0.0, FEATURE_CELL)
            y = oy + rng.uniform(0.0, FEATURE_CELL)
            pts = _make_pts(rng, x, y, radius, n, stretch, rough, jitter)
            patch = Patch(kind, x, y, pts)
            if math.hypot(x, y) - patch.r_max < SPAWN_CLEAR:      # стартовую площадку не трогаем
                return None
            return patch

        lake = mud = None
        rocks = []
        if rng.random() < LAKE_CHANCE:
            lake = place(SHALLOWS, rng.uniform(*LAKE_RADIUS), LAKE_VERTS,
                         rng.uniform(*LAKE_STRETCH), LAKE_ROUGH, LAKE_JITTER)
        if rng.random() < MUD_CHANCE:
            mud = place(MUD, rng.uniform(*MUD_RADIUS), MUD_VERTS,
                        rng.uniform(*MUD_STRETCH), MUD_ROUGH, MUD_JITTER)
        if rng.random() < ROCK_CELL_CHANCE:
            for n in range(rng.randint(*ROCKS_PER_CELL)):
                roll = rng.random()
                if roll < ROCK_BIG_P:
                    radius = rng.uniform(*ROCK_BIG)
                elif roll < ROCK_BIG_P + ROCK_MEDIUM_P:
                    radius = rng.uniform(*ROCK_MEDIUM)
                else:
                    radius = rng.uniform(*ROCK_SMALL)
                rock = place(ROCK, radius, rng.randint(*ROCK_VERTS), rng.uniform(*ROCK_STRETCH),
                             ROCK_ROUGH, ROCK_JITTER)
                if rock is not None:
                    rocks.append(rock)
        return lake, mud, rocks

    def survives(self, patch, rank, ix, iy):
        """Остаётся ли озеро (rank 0) или грязь (rank 1): нет ли рядом пересекающегося кандидата
        с более высоким приоритетом (меньший ключ (rank, ix, iy) побеждает)."""
        key = (rank, ix, iy)
        for jy in range(iy - 2, iy + 3):
            for jx in range(ix - 2, ix + 3):
                lake, mud, _ = self.raw(jx, jy)
                for other, other_rank in ((lake, 0), (mud, 1)):
                    if other is not None and (other_rank, jx, jy) < key and patches_overlap(patch, other):
                        return False
        return True

    def accepted_lake(self, ix, iy):
        """[озеро ячейки], если оно прошло проверку пересечений, иначе []."""
        key = (ix, iy)
        value = self._lake_cache.get(key)
        if value is None:
            lake = self.raw(ix, iy)[0]
            value = [lake] if lake is not None and self.survives(lake, 0, ix, iy) else []
            self._lake_cache[key] = value
        return value

def build_natural(seed, width_m, length_m, name=None):
    """Естественная карта."""
    width_m = int(round(clamp(float(width_m), WORLD_MIN_M, WORLD_MAX_M)))
    length_m = int(round(clamp(float(length_m), WORLD_MIN_M, WORLD_MAX_M)))
    gen = _Generator(seed, width_m, length_m)
    land = Landscape(width_m, length_m)
    rocks = []

    for iy in range(gen.iy[0], gen.iy[1] + 1):
        for ix in range(gen.ix[0], gen.ix[1] + 1):
            _, mud, raw_rocks = gen.raw(ix, iy)

            for shore in gen.accepted_lake(ix, iy):
                land.fill_polygon(shore.pts, L_SHALLOWS)
                land.fill_polygon(shrink_polygon(shore.pts, shore.x, shore.y, MID_SCALE), L_WATER)
                land.fill_polygon(shrink_polygon(shore.pts, shore.x, shore.y, DEEP_SCALE), L_DEEP)
            if mud is not None and gen.survives(mud, 1, ix, iy):
                land.fill_polygon(mud.pts, L_MUD)

            # камней посреди озера не бывает, в том числе озера из соседней ячейки
            lakes = [lake for jy in range(iy - 1, iy + 2) for jx in range(ix - 1, ix + 2)
                     for lake in gen.accepted_lake(jx, jy)]
            for rock in raw_rocks:
                if abs(rock.x) > gen.half_w or abs(rock.y) > gen.half_h:
                    continue
                if any(lake.contains(rock.x, rock.y) for lake in lakes):
                    continue
                rocks.append(RockData(int(round(rock.x)), int(round(rock.y)),
                                      [(int(round(px)), int(round(py))) for px, py in rock.pts]))

    return MapData(name or f"Сид {seed}", width_m, length_m, MODE_NATURAL, seed, land, rocks)

def natural_shapes(seed, width_m, length_m):
    """Сырые формы естественной карты без запекания в сетку (для дешёвого превью)."""
    width_m = int(round(clamp(float(width_m), WORLD_MIN_M, WORLD_MAX_M)))
    length_m = int(round(clamp(float(length_m), WORLD_MIN_M, WORLD_MAX_M)))
    gen = _Generator(seed, width_m, length_m)
    muds, lakes, rocks = [], [], []

    for iy in range(gen.iy[0], gen.iy[1] + 1):
        for ix in range(gen.ix[0], gen.ix[1] + 1):
            _, mud, raw_rocks = gen.raw(ix, iy)
            for shore in gen.accepted_lake(ix, iy):
                lakes.append((shore.pts,
                              shrink_polygon(shore.pts, shore.x, shore.y, MID_SCALE),
                              shrink_polygon(shore.pts, shore.x, shore.y, DEEP_SCALE)))
            if mud is not None and gen.survives(mud, 1, ix, iy):
                muds.append(mud.pts)

            near_lakes = [lake for jy in range(iy - 1, iy + 2) for jx in range(ix - 1, ix + 2)
                          for lake in gen.accepted_lake(jx, jy)]
            for rock in raw_rocks:
                if abs(rock.x) > gen.half_w or abs(rock.y) > gen.half_h:
                    continue
                if any(lake.contains(rock.x, rock.y) for lake in near_lakes):
                    continue
                rocks.append(rock.pts)
    return muds, lakes, rocks