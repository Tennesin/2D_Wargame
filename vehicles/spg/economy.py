"""vehicles/spg/economy.py — цена САУ и хуки для подбора сборки ботов (ai/loadout.py)."""
from .params import SPG_PARAMS, SPG_COST_REF, SPG_COST_PARTS, SPG_COST_ARMOR_ZONES

_CAL = SPG_PARAMS["gun_caliber_mm"]
_FRONT = SPG_PARAMS["front_armor_mm"]
_SIDE = SPG_PARAMS["side_armor_mm"]
_REAR = SPG_PARAMS["rear_armor_mm"]
_POWER = SPG_PARAMS["engine_power_hp"]

def spg_raw_cost(cal, front, side, rear, power):
    """Цена до округления. Монотонно растёт по каждому аргументу (нужно бисекции в fit_loadout)."""
    zf, zs, zr = SPG_COST_ARMOR_ZONES
    levels = {
        "gun": cal / _CAL.default,
        "armor": (zf * front / _FRONT.default + zs * side / _SIDE.default
                  + zr * rear / _REAR.default) / (zf + zs + zr),
        "engine": power / _POWER.default,
        "hull": cal / _CAL.default,
    }
    index = sum(weight * levels[name] ** k for name, (weight, k) in SPG_COST_PARTS.items())
    return SPG_COST_REF * index

def spg_loadout_cost(values):
    """Хук VehicleType.cost_fn: цена сборки по словарю значений ползунков."""
    return spg_raw_cost(values["gun_caliber_mm"], values["front_armor_mm"], values["side_armor_mm"],
                        values["rear_armor_mm"], values["engine_power_hp"])

def spg_extra_values(values, arch, tune, screen):
    """Хук VehicleType.extra_values: у САУ орудие не настраивается (нет урона, пробития, носа, экранов),
    поэтому к значениям ползунков ничего не добавляем."""
    return values