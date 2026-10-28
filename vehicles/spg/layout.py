"""vehicles/spg/layout.py — раскладка корпуса САУ. Корпус как у ПТ-САУ (хитбокс, контур, гусеницы),
но с орудием позади центра и квантованным масштабом. Собственный силуэт можно добавить позже."""
from dataclasses import replace

from vehicles.td.layout import td_layout
from .params import SPG_MOUNT_FWD_M, SPG_SCALE_RANGE, SPG_SCALE_STEP

SPG_LAYOUT = replace(td_layout(SPG_MOUNT_FWD_M), key="spg",
                     scale_range=SPG_SCALE_RANGE, scale_step=SPG_SCALE_STEP)