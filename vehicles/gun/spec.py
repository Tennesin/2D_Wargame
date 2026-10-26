"""vehicles/gun/spec.py — расчёт башни и орудия: масса, наводка, урон, пробитие, перезарядка,
размеры спрайтов, снаряд и эффекты. Шасси не знает: получает от него size_k и мощность."""
from engine import PX_PER_M, clamp
from vehicles.gun.ammo import ammo_kinds
from vehicles.gun.tuning import resolve_tuning, reload_factor, MBT_GUN
from vehicles.gun.params import (
    CALIBER, REF_POWER_HP, REF_L_CAL, GUN_MASS_T, GUN_MASS_AT_MM, TURRET_MASS_REF_T,
    BARREL_VISIBLE_K, BARREL_THICK_REF_M, BARREL_LEN_STEP_M,
    GUN_RELOAD_REF, GUN_RELOAD_MIN, GUN_OVERLOAD_Q, GUN_OVERLOAD_K, GUN_TUNE_RELOAD_MIN,
    TURRET_TURN_REF, TURRET_TURN_MIN, TURRET_TURN_MAX, TURRET_POWER_EXP,
    TURRET_INERTIA_EXP, TURRET_SPINUP_REF, TURRET_RADIUS_M, GUN_ARM_BASE_M, GUN_ARM_BARREL_K,
    SHELL_LEN_K, BARREL_VIS_REF_M, BARREL_VIS_EXP, BARREL_VIS_K_RANGE,
    SHELL_SPEED_REF_PX, SHELL_SPEED_L_EXP, SHELL_SPEED_CAL_EXP, SHELL_SPEED_PEN_EXP,
    SHELL_SPEED_LIMITS, SHELL_RANGE_REF_PX, SHELL_RANGE_SPEED_EXP, SHELL_RANGE_CAL_EXP,
    SHELL_RANGE_LIMITS, SHELL_RANGE_SMALL_CAL_EXP, SHELL_SIZE_EXP, SHELL_STRETCH_EXP, HESH_MIN_CAL_MM,
    L_CAL_SIZE_EXP, L_CAL_LIMITS, TURRET_SCALE_CAL_EXP,
    BARREL_MIN_STEPS, BARREL_THICK_MIN_M, BARREL_THICK_EXP, SHELL_THICK_K,
    RECOIL_BASE_M, RECOIL_PER_MM, RECOIL_TIME_BASE_S, RECOIL_TIME_CAL_DIV,
    FLASH_SIZE_PER_MM, FLASH_TIME_BASE_S, FLASH_TIME_GAIN_S,
    SMOKE_TIME_BASE_S, SMOKE_TIME_GAIN_S, SMOKE_STREAKS_BASE, SMOKE_STREAKS_CAL_DIV,
    SMOKE_REACH_BASE_PX, SMOKE_REACH_PER_MM, SMOKE_WIDTH_MIN_PX, SMOKE_WIDTH_CAL_DIV,
    BLAST_SIZE_PER_MM, BLAST_TIME_BASE_S, BLAST_TIME_GAIN_S, BLAST_DIRT_BASE, BLAST_DIRT_CAL_DIV,
    SCORCH_RADIUS_PER_MM, SCORCH_TIME_BASE_S, SCORCH_TIME_GAIN_S,
)

_CAL = CALIBER
REF_CAL = CALIBER.default
REF_POWER = REF_POWER_HP

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

    TURRET_SCALE_RANGE = (0.8, 1.15)   # границы поправки масштаба башни на калибр

    def __init__(self, cal, size_k, power, m_gun, m_turret, front_m, arc_deg=360.0,
                 damage=None, penetration=None, profile=MBT_GUN,
                 barrel_ref_m=BARREL_VIS_REF_M, turret_scale_range=None, visual_k=None, hesh=False):
        """profile — профиль орудия (бонус урона и пробития); front_m — на сколько метров вперёд
        от оси выступает маска орудия; barrel_ref_m — визуальная длина ствола эталона."""
        self.cal = cal
        self.hesh = bool(hesh) and cal >= HESH_MIN_CAL_MM  # правило калибра живёт только здесь
        self.ammo_kinds = ammo_kinds(self.hesh)
        self.TURRET_ARC_DEG = arc_deg
        self.profile = profile
        self.GUN_FRONT_M = front_m
        self.BARREL_REF_M = barrel_ref_m
        if turret_scale_range is not None:
            self.TURRET_SCALE_RANGE = turret_scale_range
        self._visual_k = visual_k
        self._calc_basics(size_k)
        self._calc_turret(size_k, power, m_gun, m_turret)
        self._calc_gun(damage, penetration)
        self._calc_visual(size_k)
        self._calc_shot()

    def _calc_basics(self, size_k):
        self.q_gun = (self.cal / REF_CAL) / size_k                      # калибр относительно платформы
        self.l_cal = clamp(REF_L_CAL * size_k ** L_CAL_SIZE_EXP, *L_CAL_LIMITS)   # длина ствола, калибров

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
            self.cal, damage, penetration, self.profile)

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
        base = size_k if self._visual_k is None else self._visual_k
        self.TURRET_SCALE = base * clamp(cr ** TURRET_SCALE_CAL_EXP, *self.TURRET_SCALE_RANGE)

        world_len = self.BARREL_REF_M * base * clamp(cr ** BARREL_VIS_EXP, *BARREL_VIS_K_RANGE)
        raw = world_len / self.TURRET_SCALE
        self.BARREL_LEN_M = max(BARREL_MIN_STEPS * BARREL_LEN_STEP_M,
                                round(raw / BARREL_LEN_STEP_M) * BARREL_LEN_STEP_M)

        # тонкий ствол плохо читается: пол толщины выше, рост с калибром мягче
        self.BARREL_THICK_M = max(BARREL_THICK_MIN_M, BARREL_THICK_REF_M * cr ** BARREL_THICK_EXP)

    def _calc_shot(self):
        """Всё, что зависит от калибра (размеры в мировых px, 100 px = 1 м)."""
        cal = self.cal
        cal_k = clamp((cal - _CAL.min) / (_CAL.max - _CAL.min), 0.0, 1.0)   # 0..1 по диапазону калибров

        # где находится дульный срез от центра машины (px мира, с учётом масштаба башни)
        self.MUZZLE_DIST_PX = (self.GUN_FRONT_M + self.BARREL_LEN_M) * self.TURRET_SCALE * PX_PER_M

        # снаряд: сначала скорость, от неё зависят дальность и длина трассера
        cr = cal / REF_CAL
        speed = (SHELL_SPEED_REF_PX
                 * (self.l_cal / REF_L_CAL) ** SHELL_SPEED_L_EXP
                 * cr ** SHELL_SPEED_CAL_EXP
                 * self.pen_k ** SHELL_SPEED_PEN_EXP
                 * self.profile.speed_mult(cal))
        self.SHELL_SPEED_PX = clamp(speed, *SHELL_SPEED_LIMITS)

        range_cal_exp = SHELL_RANGE_SMALL_CAL_EXP if cr < 1.0 else SHELL_RANGE_CAL_EXP
        reach = (SHELL_RANGE_REF_PX
                 * (self.SHELL_SPEED_PX / SHELL_SPEED_REF_PX) ** SHELL_RANGE_SPEED_EXP
                 * cr ** range_cal_exp
                 * self.profile.range_mult(cal))
        self.SHELL_RANGE_PX = clamp(reach, *SHELL_RANGE_LIMITS)

        size = SHELL_LEN_K * REF_CAL * cr ** SHELL_SIZE_EXP
        stretch = (self.SHELL_SPEED_PX / SHELL_SPEED_REF_PX) ** SHELL_STRETCH_EXP
        self.SHELL_LEN_PX = size * stretch
        self.SHELL_THICK_PX = SHELL_THICK_K * REF_CAL * cr ** SHELL_SIZE_EXP

        # откат ствола (метры эталонного спрайта)
        self.RECOIL_DEPTH_M = RECOIL_BASE_M + RECOIL_PER_MM * cal
        self.RECOIL_TIME = RECOIL_TIME_BASE_S + cal / RECOIL_TIME_CAL_DIV  # полный цикл «назад и обратно», с

        # вспышка
        self.FLASH_SIZE_PX = FLASH_SIZE_PER_MM * cal
        self.FLASH_TIME = FLASH_TIME_BASE_S + FLASH_TIME_GAIN_S * cal_k

        # дым
        self.SMOKE_TIME = SMOKE_TIME_BASE_S + SMOKE_TIME_GAIN_S * cal_k
        self.SMOKE_STREAKS = SMOKE_STREAKS_BASE + int(cal / SMOKE_STREAKS_CAL_DIV)
        self.SMOKE_REACH_PX = SMOKE_REACH_BASE_PX + SMOKE_REACH_PER_MM * cal
        self.SMOKE_WIDTH_PX = max(SMOKE_WIDTH_MIN_PX, cal / SMOKE_WIDTH_CAL_DIV)

        # взрыв снаряда и след на земле
        self.BLAST_SIZE_PX = BLAST_SIZE_PER_MM * cal
        self.BLAST_TIME = BLAST_TIME_BASE_S + BLAST_TIME_GAIN_S * cal_k
        self.BLAST_DIRT_COUNT = BLAST_DIRT_BASE + int(cal / BLAST_DIRT_CAL_DIV)
        self.SCORCH_RADIUS_PX = SCORCH_RADIUS_PER_MM * cal
        self.SCORCH_TIME = SCORCH_TIME_BASE_S + SCORCH_TIME_GAIN_S * cal_k