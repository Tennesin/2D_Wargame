"""game/match/loot/upgrades.py — определения улучшений и ячейки игрока. Ничего не рисует.
Ключ улучшения = ключ архетипа, с которого оно выпадает (ai.ARCHETYPES)."""
from dataclasses import dataclass
from enum import Enum, auto

from vehicles import StatMods, NO_MODS

SLOT_COUNT = 3
MAX_LEVEL = 3

@dataclass(frozen=True)
class UpgradeDef:
    key: str            # ключ архетипа-источника
    title: str          # название улучшения
    label: str          # что усиливается (для текста эффекта)
    fields: tuple       # поля StatMods, которые двигает улучшение
    bonus: tuple        # прирост по уровням 1..3 (доли)
    reduce: bool = False    # True: множитель уменьшается (сопротивление), иначе растёт
    icon: str = ""          # название значка в ui/upgrade_icons.py

    def factor(self, level):
        """Множитель для полей StatMods на этом уровне."""
        b = self.bonus[level - 1]
        return 1.0 - b if self.reduce else 1.0 + b

    def effect(self, level):
        """Текст эффекта для интерфейса: числа берутся из тех же данных, что и расчёт."""
        return f"{self.label} +{self.bonus[level - 1] * 100:g}%"

UPGRADES = {d.key: d for d in (
    UpgradeDef("universal", "Мощный заряд", "Урон снарядов",
               ("dmg_k",), (0.10, 0.15, 0.20), icon="damage"),
    UpgradeDef("bunker", "Усиленная броня", "Эффективность брони",
               ("armor_k",), (0.10, 0.15, 0.20), icon="armor"),
    UpgradeDef("scout", "Форсаж двигателя", "Эффективность двигателя",
               ("power_k",), (0.10, 0.15, 0.20), icon="engine"),
    UpgradeDef("destroyer", "Бронебойный сердечник", "Пробитие снарядов",
               ("pen_k",), (0.10, 0.175, 0.25), icon="pierce"),
    UpgradeDef("assault", "Быстрые приводы", "Скорость поворота башни и корпуса",
               ("turn_k",), (0.20, 0.35, 0.50), icon="drives"),
    UpgradeDef("sniper", "Баллистика", "Дальность и скорость снарядов",
               ("shell_range_k", "shell_speed_k"), (0.20, 0.30, 0.40), icon="ballistics"),
    UpgradeDef("artillery", "Противоосколочная защита", "Сопротивление ФГ и HESH",
               ("blast_taken_k",), (0.15, 0.20, 0.25), reduce=True, icon="blast"),
)}

class Plan(Enum):
    """Что произойдёт, если игрок возьмёт улучшение."""
    LEVEL_UP = auto()   # такое улучшение уже есть: растёт уровень
    FREE = auto()       # нет, но есть свободная ячейка
    REPLACE = auto()    # нет, и все ячейки заняты другими: нужно выбрать, какую заменить
    MAXED = auto()      # уже третий уровень: предлагать нечего

class UpgradeSlots:
    """Три ячейки. Каждая либо None, либо (ключ, уровень)."""

    def __init__(self):
        self.slots = [None] * SLOT_COUNT

    def index_of(self, key):
        """Номер ячейки с этим улучшением или None."""
        for i, s in enumerate(self.slots):
            if s is not None and s[0] == key:
                return i
        return None

    def plan(self, key):
        i = self.index_of(key)
        if i is not None:
            return Plan.MAXED if self.slots[i][1] >= MAX_LEVEL else Plan.LEVEL_UP
        return Plan.FREE if None in self.slots else Plan.REPLACE

    def apply(self, key, slot=None):
        """Взять улучшение. slot нужен только при Plan.REPLACE (какую ячейку заменить).
        Возвращает (номер ячейки, новый уровень) или None, если взять нельзя."""
        plan = self.plan(key)
        if plan is Plan.MAXED:
            return None
        if plan is Plan.LEVEL_UP:
            i = self.index_of(key)
            level = self.slots[i][1] + 1
        elif plan is Plan.FREE:
            i, level = self.slots.index(None), 1
        else:
            if slot is None or not 0 <= slot < SLOT_COUNT:
                return None
            i, level = slot, 1
        self.slots[i] = (key, level)
        return i, level

    def build_mods(self):
        """Итоговый набор множителей по всем ячейкам. Пустые ячейки: NO_MODS (та же константа, не копия)."""
        values = {}
        for s in self.slots:
            if s is None:
                continue
            d = UPGRADES[s[0]]
            for field in d.fields:
                values[field] = values.get(field, 1.0) * d.factor(s[1])
        return StatMods(**values) if values else NO_MODS