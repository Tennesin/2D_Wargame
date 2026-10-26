"""world/mapdata.py — данные карты: размер, ландшафт, камни, стены. Без pygame.
Единый формат для игры, редактора и мини-карты. Файл — один json (см. game/state/maps.py)."""
import math
from dataclasses import dataclass

from engine import WORLD_MIN_M, WORLD_MAX_M, PX_PER_M, clamp
from .landscape import Landscape

FORMAT_VERSION = 1
MODE_NATURAL = "natural"
MODE_EMPTY = "empty"

MAX_ROCK_R_PX = 2600.0     # радиус камня не больше этого (нужно поиску соседей в TerrainMap)
START_CLEAR_M = 14.0       # вокруг центра карты не бывает камней, стен и глубокой воды
MAX_NAME_LEN = 40
MAX_ROCKS = 20000
MAX_WALLS = 5000
DEFAULT_NAME = "Без имени"

@dataclass
class RockData:
    x: float                 # центр, мировые px
    y: float
    pts: list                # вершины [(x, y), ...], мировые px; звёздчатый многоугольник вокруг центра

@dataclass
class WallData:
    x: float
    y: float
    hp: float
    width_m: float
    length_m: float
    angle: float = 0.0

def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)

class MapData:
    def __init__(self, name, width_m, length_m, mode=MODE_NATURAL, seed=0,
                 landscape=None, rocks=None, walls=None):
        self.name = (str(name).strip() or DEFAULT_NAME)[:MAX_NAME_LEN]
        self.width_m = int(round(clamp(float(width_m), WORLD_MIN_M, WORLD_MAX_M)))
        self.length_m = int(round(clamp(float(length_m), WORLD_MIN_M, WORLD_MAX_M)))
        self.mode = mode if mode in (MODE_NATURAL, MODE_EMPTY) else MODE_NATURAL
        self.seed = int(seed)
        if landscape is None:
            landscape = Landscape(self.width_m, self.length_m)
        if landscape.cols != self.width_m or landscape.rows != self.length_m:
            raise ValueError("MapData: размер ландшафта не совпадает с размером карты")
        self.landscape = landscape
        self.rocks = list(rocks or [])
        self.walls = list(walls or [])
        self.file = None          # имя файла в maps/ (ставит MapStore, в файл не пишется)

    @property
    def half_w_px(self):
        return self.width_m * PX_PER_M / 2.0

    @property
    def half_h_px(self):
        return self.length_m * PX_PER_M / 2.0

    # ---------- файл ----------
    def to_dict(self):
        return {
            "version": FORMAT_VERSION,
            "name": self.name,
            "width_m": self.width_m,
            "length_m": self.length_m,
            "mode": self.mode,
            "seed": self.seed,
            "landscape": self.landscape.to_dict(),
            "rocks": [{"x": r.x, "y": r.y, "pts": [[px, py] for px, py in r.pts]} for r in self.rocks],
            "walls": [{"x": w.x, "y": w.y, "hp": w.hp, "width_m": w.width_m,
                       "length_m": w.length_m, "angle": w.angle} for w in self.walls],
        }

    @classmethod
    def from_dict(cls, data):
        """Карта из словаря или None. Битая шапка или ландшафт: карта отклоняется целиком.
        Битый камень или стена: пропускается, остальное загружается."""
        if not isinstance(data, dict):
            return None
        version = data.get("version", 1)
        if not isinstance(version, int) or isinstance(version, bool) or version > FORMAT_VERSION:
            return None
        w, l = data.get("width_m"), data.get("length_m")
        if not (_num(w) and _num(l) and WORLD_MIN_M <= w <= WORLD_MAX_M
                and WORLD_MIN_M <= l <= WORLD_MAX_M):
            return None
        land = Landscape.from_dict(data.get("landscape"))
        if land is None or land.cols != int(round(w)) or land.rows != int(round(l)):
            return None
        seed = data.get("seed")
        try:
            return cls(data.get("name") or DEFAULT_NAME, w, l, data.get("mode"),
                       int(seed) if _num(seed) else 0, land,
                       cls._read_rocks(data.get("rocks")), cls._read_walls(data.get("walls")))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _read_rocks(items):
        rocks = []
        if not isinstance(items, list):
            return rocks
        for r in items[:MAX_ROCKS]:
            if not isinstance(r, dict) or not (_num(r.get("x")) and _num(r.get("y"))):
                continue
            pts = r.get("pts")
            if not isinstance(pts, list) or not (3 <= len(pts) <= 64):
                continue
            clean = []
            for p in pts:
                if not (isinstance(p, (list, tuple)) and len(p) == 2 and _num(p[0]) and _num(p[1])):
                    clean = None
                    break
                clean.append((float(p[0]), float(p[1])))
            if clean is None:
                continue
            x, y = float(r["x"]), float(r["y"])
            if max(math.hypot(px - x, py - y) for px, py in clean) > MAX_ROCK_R_PX:
                continue
            rocks.append(RockData(x, y, clean))
        return rocks

    @staticmethod
    def _read_walls(items):
        walls = []
        if not isinstance(items, list):
            return walls
        for w in items[:MAX_WALLS]:
            if not isinstance(w, dict):
                continue
            vals = [w.get(k) for k in ("x", "y", "hp", "width_m", "length_m")]
            if not all(_num(v) for v in vals) or vals[2] <= 0 or vals[3] <= 0 or vals[4] <= 0:
                continue
            angle = w.get("angle", 0.0)
            walls.append(WallData(*(float(v) for v in vals), float(angle) if _num(angle) else 0.0))
        return walls

def build_empty(name, width_m, length_m, seed=0):
    """Пустая карта: везде трава, ни камней, ни стен."""
    return MapData(name, width_m, length_m, MODE_EMPTY, seed)