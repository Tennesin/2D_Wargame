"""game/state/session.py — данные, которые переживают смену сцен и запуски."""
import math
import random

from engine import VehicleKind, WORLD_DEFAULT_M, WORLD_MIN_M, WORLD_MAX_M, clamp, round_to
from vehicles import (
    VEHICLE_TYPES, default_tuning, FRONT_SCREEN, NOSE_FLAT, NOSE_PIKE, NOSE_WEDGE,
    SPECIAL_HEAT, SPECIAL_HESH, default_length, TURRET_STYLES, DESIGN_PARAMS
)
from vehicles.parts import clean_design_data
from .preferences import Preferences
from .settings import GameSettings
from .stats import Career
from world import build_natural
from . import storage
from .maps import MapStore

SESSION_FILE = "session.json"
FORMAT_VERSION = 1
MAP_STEP_M = 50.0                                   # шаг ползунков размера карты (как в «Новой игре»)
_NOSES = (NOSE_FLAT, NOSE_PIKE, NOSE_WEDGE)
_AMMO = (SPECIAL_HEAT, SPECIAL_HESH)

def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)

class Session:
    def __init__(self):
        self.kind = VehicleKind.MBT
        self.map_w_m = WORLD_DEFAULT_M   # размер карты по X, м (задаётся в «Новой игре»)
        self.map_h_m = WORLD_DEFAULT_M   # по Y, м
        # значения ползунков для КАЖДОГО типа отдельно: при переключении кнопок настройки не теряются
        self.values = {kind: self._defaults(t) for kind, t in VEHICLE_TYPES.items() if t.playable}
        self.prefs = Preferences()       # настройки меню: живут, пока открыто приложение
        self.settings = GameSettings()   # настройки меню «Настройки»
        self.career = Career()           # накопленная статистика и рекорды (файл stats.json)
        self.maps = MapStore()           # хранилище карт (папка maps/), список кэшируется
        self.map_file = None             # None: случайная карта по сиду; иначе имя файла в maps/
        self.map_seed = self._roll_seed()
        self._seed_spent = False         # True: партия на этом сиде уже сыграна, нужен новый
        self._load()                     # сохранённая сборка и настройки (если файл есть и читается)

    @staticmethod
    def _defaults(vtype):
        values = {key: p.default for key, p in vtype.params.items()}
        dmg, pen = default_tuning(values["gun_caliber_mm"], vtype.gun_profile)
        values["gun_damage"] = dmg
        values["gun_penetration"] = pen
        length = default_length(values["gun_caliber_mm"])
        values["gun_length_cal"] = length
        values["special_ammo"] = SPECIAL_HEAT
        values["front_screen_mm"] = FRONT_SCREEN.default
        values["front_nose"] = NOSE_FLAT
        values.update(vtype.design_defaults or {})
        values["parts_design"] = None
        return values

    def spec(self):
        """Спецификация выбранной техники по текущим значениям."""
        t = VEHICLE_TYPES[self.kind]
        return t.spec_cls.from_values(self.values[self.kind])

    # ---------- сохранение между запусками ----------
    def to_dict(self):
        return {
            "version": FORMAT_VERSION,
            "kind": self.kind.name,
            "map_w_m": self.map_w_m,
            "map_h_m": self.map_h_m,
            "enemies": sorted(self.prefs.enabled_keys()),
            "values": {kind.name: dict(vals) for kind, vals in self.values.items()},
        }

    def save(self):
        """Записать сборку и настройки в session.json. True при успехе."""
        return storage.write_json(SESSION_FILE, self.to_dict())

    def _load(self):
        """Читает файл."""
        data = storage.read_json(SESSION_FILE)
        if not isinstance(data, dict):
            return
        name = data.get("kind")
        kind = VehicleKind.__members__.get(name) if isinstance(name, str) else None
        if kind in self.values:
            self.kind = kind

        for attr, key in (("map_w_m", "map_w_m"), ("map_h_m", "map_h_m")):
            v = data.get(key)
            if _is_num(v):
                setattr(self, attr, round_to(clamp(float(v), WORLD_MIN_M, WORLD_MAX_M), MAP_STEP_M))

        enemies = data.get("enemies")
        if isinstance(enemies, list):
            self.prefs.set_enabled([k for k in enemies if isinstance(k, str)])

        saved_all = data.get("values")
        if not isinstance(saved_all, dict):
            return
        for k, current in self.values.items():
            saved = saved_all.get(k.name)
            if isinstance(saved, dict):
                self._load_values(k, current, saved)

    @staticmethod
    def _load_values(kind, current, saved):
        """Переносит в current корректные значения из saved."""
        params = VEHICLE_TYPES[kind].params
        for key in current:
            v = saved.get(key)
            if key == "special_ammo":
                if v in _AMMO:
                    current[key] = v
            elif key == "front_nose":
                if v in _NOSES:
                    current[key] = v
            elif key == "turret_style":
                if v in TURRET_STYLES:
                    current[key] = v
            elif key == "parts_design":
                current[key] = clean_design_data(v)
            elif not _is_num(v):
                continue
            elif key in params:
                current[key] = params[key].fit(v)
            elif key in DESIGN_PARAMS:
                current[key] = DESIGN_PARAMS[key].fit(v)
            elif key == "front_screen_mm":
                current[key] = FRONT_SCREEN.fit(v)
            else:
                current[key] = float(v)

    @staticmethod
    def _roll_seed():
        return random.randrange(1, 1_000_000)

    def fresh_seed(self):
        """Новый сид для превью случайной карты."""
        self.map_seed = self._roll_seed()
        self._seed_spent = False

    def prepare_seed(self):
        """При открытии «Новой игры»: если на прошлом сиде уже играли, берём новый."""
        if self._seed_spent:
            self.fresh_seed()

    def make_map(self, seed=None):
        """Карта для новой партии: выбранный файл или случайная по map_seed.
        seed: принудительный сид (отладка), действует только для случайной карты."""
        if self.map_file is not None:
            data = self.maps.load(self.map_file)
            if data is not None:
                return data
            self.map_file = None                      # файл пропал или повреждён: вернёмся к случайной
        if seed is not None:
            self.map_seed = seed
        self._seed_spent = True
        return build_natural(self.map_seed, self.map_w_m, self.map_h_m)