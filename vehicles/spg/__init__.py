"""spg — САУ (артиллерия). Снаружи импортируем через пакет vehicles."""
from .params import SPG_PARAMS
from .economy import spg_raw_cost, spg_loadout_cost, spg_extra_values
from .spec import SPGSpec, ArtyGunSpec
from .entity import ArtilleryVehicle
from .sprites import SPGRenderer

__all__ = ["SPG_PARAMS", "spg_raw_cost", "spg_loadout_cost", "spg_extra_values",
           "SPGSpec", "ArtyGunSpec", "ArtilleryVehicle", "SPGRenderer"]