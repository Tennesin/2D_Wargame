"""game/session.py — данные, которые переживают смену сцен: выбранный тип техники и настройки каждого типа."""
from engine import VehicleKind
from vehicles import VEHICLE_TYPES, default_tuning, FRONT_SCREEN
from .preferences import Preferences

class Session:
    def __init__(self):
        self.kind = VehicleKind.MBT
        # значения ползунков для КАЖДОГО типа отдельно: при переключении кнопок настройки не теряются
        self.values = {kind: self._defaults(t) for kind, t in VEHICLE_TYPES.items()}
        self.prefs = Preferences()       # настройки меню: живут, пока открыто приложение

    @staticmethod
    def _defaults(vtype):
        values = {key: p.default for key, p in vtype.params.items()}
        dmg, pen = default_tuning(values["gun_caliber_mm"], vtype.gun_profile)
        values["gun_damage"] = dmg
        values["gun_penetration"] = pen
        values["front_screen_mm"] = FRONT_SCREEN.default
        return values

    def spec(self):
        """Спецификация выбранной техники по текущим значениям."""
        t = VEHICLE_TYPES[self.kind]
        return t.spec_cls.from_values(self.values[self.kind])