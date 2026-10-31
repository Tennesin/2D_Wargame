"""vehicles/mods.py — множители улучшений техники (StatMods) и их применение к числам выстрела."""
from dataclasses import dataclass, replace

@dataclass(frozen=True)
class StatMods:
    """Неизменяемый набор множителей. 1.0 = без изменений. Каждое улучшение двигает только свои поля."""
    dmg_k: float = 1.0            # урон снаряда
    pen_k: float = 1.0            # пробитие снаряда
    shell_speed_k: float = 1.0    # скорость полёта снаряда
    shell_range_k: float = 1.0    # дальность снаряда
    armor_k: float = 1.0          # эффективность брони (корпус, гусеницы, экраны)
    power_k: float = 1.0          # эффективная мощность двигателя (ход, разгон, поворот корпуса)
    turn_k: float = 1.0           # скорость и разгон поворота корпуса и орудия
    blast_taken_k: float = 1.0    # входящий урон и оглушение от ФГ и HESH (меньше 1 = сопротивление)

NO_MODS = StatMods()

def apply_to_ammo(stats, mods):
    """AmmoStats с учётом улучшений. Без улучшений возвращает тот же объект."""
    if mods is NO_MODS:
        return stats
    return replace(stats,
                   damage=stats.damage * mods.dmg_k,
                   penetration=stats.penetration * mods.pen_k,
                   speed_px=stats.speed_px * mods.shell_speed_k,
                   range_px=stats.range_px * mods.shell_range_k)