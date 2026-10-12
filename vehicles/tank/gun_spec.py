"""tank/gun_spec.py — расчёт башни и орудия: масса, наводка, урон, пробитие, перезарядка,
размеры спрайтов, снаряд и эффекты. Шасси не знает: получает от него size_k и мощность."""
import math

from engine import PX_PER_M, clamp
from .gun_tuning import resolve_tuning, reload_factor
from .params import (
    PARAMS, REF_L_CAL, GUN_MASS_T, GUN_MASS_AT_MM, TURRET_MASS_REF_T,
    BARREL_VISIBLE_K, BARREL_THICK_REF_M, BARREL_LEN_STEP_M, TURRET_FRONT_M,
    GUN_RELOAD_REF, GUN_RELOAD_MIN, GUN_OVERLOAD_Q, GUN_OVERLOAD_K,
    GUN_TUNE_RELOAD_MIN,
    TURRET_TURN_REF, TURRET_TURN_MIN, TURRET_TURN_MAX, TURRET_POWER_EXP,
    TURRET_INERTIA_EXP, TURRET_SPINUP_REF, TURRET_RADIUS_M, GUN_ARM_BASE_M, GUN_ARM_BARREL_K,
    SHELL_LEN_K,
)

_CAL = PARAMS["gun_caliber_mm"]
_POWER = PARAMS["engine_power_hp"]
REF_CAL = _CAL.default
REF_POWER = _POWER.default

def turret_masses(cal):
    """Массы орудия и башни калибра cal, т: (орудие, башня)."""
    return (GUN_MASS_T * (cal / GUN_MASS_AT_MM) ** 2,
            TURRET_MASS_REF_T * (cal / REF_CAL) ** 1.5)

def _turret_inertia(m_turret, m_gun, size_k, barrel_len_m):
    """Момент инерции вращающейся части (башня + орудие), т·м²."""
    r_turret = TURRET_RADIUS_M * size_k
    r_gun = GUN_ARM_BASE_M * size_k + GUN_ARM_BARREL_K * barrel_len_m
    return m_turret * r_turret ** 2 + m_gun * r_gun ** 2

_REF_GUN_MASS, _REF_TURRET_MASS = turret_masses(REF_CAL)
REF_TURRET_INERTIA = _turret_inertia(_REF_TURRET_MASS, _REF_GUN_MASS, 1.0,
                                     REF_CAL * REF_L_CAL / 1000.0 * BARREL_VISIBLE_K)

class GunSpec:
    """arc_deg — полный сектор наводки башни относительно корпуса: 360 = круговая башня,
    меньше (например 40) = казематная установка (ПТ-САУ), которой надо доворачивать корпус."""

    def __init__(self, cal, size_k, power, m_gun, m_turret, arc_deg=360.0,
                 damage=None, penetration=None):
        self.cal = cal
        self.TURRET_ARC_DEG = arc_deg
        self._calc_basics(size_k)
        self._calc_turret(size_k, power, m_gun, m_turret)
        self._calc_gun(damage, penetration)
        self._calc_visual(size_k)
        self._calc_shot()

    def _calc_basics(self, size_k):
        self.q_gun = (self.cal / REF_CAL) / size_k                      # калибр относительно платформы
        self.l_cal = clamp(REF_L_CAL * size_k ** 0.45, 30.0, 55.0)      # длина ствола, калибров

    def _calc_turret(self, size_k, power, m_gun, m_turret):
        barrel_len = self.cal * self.l_cal / 1000.0 * BARREL_VISIBLE_K
        self.i_turret = _turret_inertia(m_turret, m_gun, size_k, barrel_len)
        i_rel = self.i_turret / REF_TURRET_INERTIA
        self.turret_turn = clamp(
            TURRET_TURN_REF * (power / REF_POWER) ** TURRET_POWER_EXP * i_rel ** -TURRET_INERTIA_EXP,
            TURRET_TURN_MIN, TURRET_TURN_MAX)
        self.turret_alpha = self.turret_turn / (TURRET_SPINUP_REF * i_rel ** 0.5)   # °/с²

    def _calc_gun(self, damage, penetration):
        cr = self.cal / REF_CAL
        # урон и пробитие: номинал калибра + выбор игрока (длина ствола на них больше не влияет)
        self.damage, self.penetration, self.damage_k, self.pen_k = resolve_tuning(
            self.cal, damage, penetration)

        # базовая перезарядка: ровно как раньше (пол GUN_RELOAD_MIN действует ДО тюнинга)
        reload = max(GUN_RELOAD_MIN, GUN_RELOAD_REF * cr * self.q_gun ** 0.5)
        overload = max(0.0, self.q_gun - GUN_OVERLOAD_Q)
        reload *= 1.0 + GUN_OVERLOAD_K * overload

        # тюнинг: больше урон или пробитие = дольше перезарядка
        reload *= reload_factor(self.damage_k, self.pen_k)
        self.reload = max(GUN_TUNE_RELOAD_MIN, reload)
        self.dps = self.damage / self.reload

    def _calc_visual(self, size_k):
        cal = self.cal
        cr = cal / REF_CAL
        self.TURRET_SCALE = size_k * clamp(cr ** 0.35, 0.8, 1.15)
        self.BARREL_LEN_M = round(cal * self.l_cal / 1000.0 * BARREL_VISIBLE_K / BARREL_LEN_STEP_M) * BARREL_LEN_STEP_M
        self.BARREL_THICK_M = max(0.18, BARREL_THICK_REF_M * cr ** 0.7)

    def _calc_shot(self):
        """Всё, что зависит от калибра (размеры в мировых px, 100 px = 1 м)."""
        cal = self.cal
        cal_k = clamp((cal - _CAL.min) / (_CAL.max - _CAL.min), 0.0, 1.0)   # 0..1 по диапазону калибров

        # где находится дульный срез от центра машины (px мира, с учётом масштаба башни)
        self.MUZZLE_DIST_PX = (TURRET_FRONT_M + self.BARREL_LEN_M) * self.TURRET_SCALE * PX_PER_M

        # снаряд
        self.SHELL_LEN_PX = SHELL_LEN_K * cal
        self.SHELL_THICK_PX = 0.15 * cal
        self.SHELL_SPEED_PX = 6000.0 * (self.l_cal / REF_L_CAL) ** 0.3
        self.SHELL_RANGE_PX = 3500.0                                   # дальше — взрыв, как при попадании в землю

        # откат ствола (метры эталонного спрайта)
        self.RECOIL_DEPTH_M = 0.12 + 0.0028 * cal
        self.RECOIL_TIME = 0.25 + cal / 400.0                          # полный цикл «назад и обратно», с

        # вспышка
        self.FLASH_SIZE_PX = 2.2 * cal
        self.FLASH_TIME = 0.07 + 0.05 * cal_k

        # дым
        self.SMOKE_TIME = 1.0 + 0.5 * cal_k
        self.SMOKE_STREAKS = 5 + int(cal / 20)
        self.SMOKE_REACH_PX = 160.0 + 3.2 * cal
        self.SMOKE_WIDTH_PX = max(8.0, cal / 6.0)

        # взрыв снаряда и след на земле
        self.BLAST_SIZE_PX = 1.8 * cal
        self.BLAST_TIME = 0.35 + 0.2 * cal_k
        self.BLAST_DIRT_COUNT = 6 + int(cal / 15)
        self.SCORCH_RADIUS_PX = 0.9 * cal
        self.SCORCH_TIME = 4.0 + 2.0 * cal_k