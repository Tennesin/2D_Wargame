"""vehicles/td/spec.py — характеристики ПТ-САУ: шасси + орудие без башни (TDGunSpec) + положение орудия."""
import dataclasses
import math

from engine import clamp, lerp, fmt_num, PX_PER_M, round_to
from ..chassis.params import ENGINE_T_PER_HP
from ..chassis.spec import ChassisBody, armor_masses
from ..chassis.hulls import NOSE_FLAT, NOSE_PIKE, NOSE_RU
from ..chassis.hull_noses import NOSE_MIN_FRONT_MM
from ..gun.ammo import SPECIAL_HEAT, SPECIAL_HESH
from ..gun.spec import GunSpec, turret_masses
from ..gun.tuning import TD_GUN
from ..gun.barrel import effective_length
from ..gun.params import (
    REF_L_CAL, BARREL_VISIBLE_K, GUN_ARM_BASE_M, GUN_ARM_BARREL_K,
    TURRET_INERTIA_EXP, TURRET_POWER_EXP,
)
from ..gun.vehicle_specific import GunVehicleSpec
from .layout import td_layout
from .rules import td_caliber_limits
from .params import (
    TD_PARAMS, TD_FIXED_MASS_T, TD_FRONT_AREA_M2, TD_SIDE_AREA_M2, TD_REAR_AREA_M2, TD_HP_REF,
    TD_CASEMATE_K, gun_arc_deg, TD_TRAVERSE_REF, TD_TRAVERSE_MIN, TD_TRAVERSE_MAX, TD_SPINUP_REF,
    TD_GUN_FRONT_M, TD_BARREL_VIS_REF_M, TD_RECOIL_K, MOUNT_FRONT_FWD_M, MOUNT_REAR_FWD_M,
    MOUNT_CAL, MOUNT_STEP_M, SUPPORT_T, TD_HULL_COLL_HALF_W_M, TD_HULL_COLL_HALF_L_M,
    TD_LOOK_FRONT_RATIO, TD_LOOK_SIDE_RATIO, TD_LOOK_GUN_RATIO, TD_LOOK_SPEED_RATIO,
    TD_CASE_CAL_EXP, TD_CASE_K_LIMITS, TD_SIZE_ARMOR_K, TD_DESIGN_PARAMS,
    MOUNT_REAR_LIMIT_SMALL_M, MOUNT_FRONT_LIMIT_BIG_M
)

_CAL = TD_PARAMS["gun_caliber_mm"]
_FRONT = TD_PARAMS["front_armor_mm"]
_SIDE = TD_PARAMS["side_armor_mm"]
_REAR = TD_PARAMS["rear_armor_mm"]
_POWER = TD_PARAMS["engine_power_hp"]
_AREAS = (TD_FRONT_AREA_M2, TD_SIDE_AREA_M2, TD_REAR_AREA_M2)

# ==========================================
# 1. ПОЛОЖЕНИЕ ОРУДИЯ
# ==========================================

def mount_t(cal):
    """0 — орудие на лбу, 1 — на задней опоре (сглаженный переход)."""
    lo, hi = MOUNT_CAL
    x = clamp((cal - lo) / (hi - lo), 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)

def mount_fwd_m(cal):
    """Насколько ось орудия впереди центра корпуса, м (минус = позади). Квантуется шагом MOUNT_STEP_M."""
    raw = lerp(MOUNT_FRONT_FWD_M, MOUNT_REAR_FWD_M, mount_t(cal))
    return round(round_to(raw, MOUNT_STEP_M), 3)

def support_level_for_mount(mount):
    """Уровень задней опоры по ФАКТИЧЕСКОМУ положению орудия: 0 нет, 1 малая, 2 большая."""
    t = clamp((MOUNT_FRONT_FWD_M - mount) / (MOUNT_FRONT_FWD_M - MOUNT_REAR_FWD_M), 0.0, 1.0)
    return 0 if t < SUPPORT_T[0] else (1 if t < SUPPORT_T[1] else 2)

def mount_shift_range(cal):
    """(мин, макс) сдвига орудия от «авто»-положения, м, для калибра cal."""
    auto = mount_fwd_m(cal)
    t = clamp((cal - _CAL.min) / (_CAL.max - _CAL.min), 0.0, 1.0)
    rear_abs = min(auto, lerp(MOUNT_REAR_LIMIT_SMALL_M, MOUNT_REAR_FWD_M, t))
    front_abs = max(auto, lerp(MOUNT_FRONT_FWD_M, MOUNT_FRONT_LIMIT_BIG_M, t))
    p = TD_DESIGN_PARAMS["mount_shift_m"]
    lo = math.ceil((rear_abs - auto) / p.step - 1e-9) * p.step
    hi = math.floor((front_abs - auto) / p.step + 1e-9) * p.step
    return round(max(p.min, lo), 3) + 0.0, round(min(p.max, hi), 3) + 0.0

# ==========================================
# 2. ЭТАЛОН ПТ-САУ
# ==========================================

def td_masses(cal, length_cal=None):
    """Массы орудия и рубки калибра cal, т: (орудие, рубка)."""
    gun, turret = turret_masses(cal, length_cal)
    return gun, turret * TD_CASEMATE_K

_REF_CAL = _CAL.default
_REF_GUN_MASS, _REF_CASEMATE_MASS = td_masses(_REF_CAL)
_REF_FILLING = (TD_FIXED_MASS_T + _REF_GUN_MASS + _REF_CASEMATE_MASS
                + ENGINE_T_PER_HP * _POWER.default)
_REF_ARMOR_MASS = sum(armor_masses(_AREAS, _FRONT.default, _SIDE.default, _REAR.default, 1.0))
_REF_MASS = _REF_FILLING + _REF_ARMOR_MASS

TD_BODY = ChassisBody(
    fixed_t=TD_FIXED_MASS_T, engine_t_per_hp=ENGINE_T_PER_HP, areas_m2=_AREAS,
    ref_filling_t=_REF_FILLING, ref_mass_t=_REF_MASS, ref_power_hp=_POWER.default,
    ref_armor_share=_REF_ARMOR_MASS / _REF_MASS, hp_ref=TD_HP_REF,
    coll_half_w_m=TD_HULL_COLL_HALF_W_M, coll_half_l_m=TD_HULL_COLL_HALF_L_M,
    coll_shift_m=0.0,
    size_armor_k=TD_SIZE_ARMOR_K,
    ref_size_mass_t=_REF_FILLING + TD_SIZE_ARMOR_K * _REF_ARMOR_MASS)

_REF_BARREL_M = _REF_CAL * REF_L_CAL / 1000.0 * BARREL_VISIBLE_K
TD_REF_GUN_INERTIA = _REF_GUN_MASS * (GUN_ARM_BASE_M + GUN_ARM_BARREL_K * _REF_BARREL_M) ** 2

# ==========================================
# 3. ОРУДИЕ БЕЗ БАШНИ
# ==========================================

class TDGunSpec(GunSpec):
    """Вращается только орудие, а не башня: инерция меньше, наводка медленнее и в узком секторе.
    Имена turret_turn / turret_alpha сохранены: их читает GunVehicle._aim_turret."""

    TURRET_SCALE_RANGE = (1.0, 1.0)    # у ПТ-САУ маска принадлежит корпусу, поэтому масштаб орудия = масштаб корпуса

    def _calc_turret(self, size_k, power, m_gun, m_turret):
        barrel_len = self.cal * self.l_cal / 1000.0 * BARREL_VISIBLE_K
        arm = GUN_ARM_BASE_M * size_k + GUN_ARM_BARREL_K * barrel_len
        self.i_turret = m_gun * arm ** 2
        i_rel = self.i_turret / TD_REF_GUN_INERTIA
        self.turret_turn = clamp(
            TD_TRAVERSE_REF * (power / _POWER.default) ** TURRET_POWER_EXP * i_rel ** -TURRET_INERTIA_EXP,
            TD_TRAVERSE_MIN, TD_TRAVERSE_MAX)
        self.turret_alpha = self.turret_turn / (TD_SPINUP_REF * i_rel ** 0.5)

    def _calc_shot(self):
        super()._calc_shot()
        self.RECOIL_DEPTH_M *= TD_RECOIL_K

# ==========================================
# 4. ПТ-САУ
# ==========================================

class TDSpec(GunVehicleSpec):
    PARAMS = TD_PARAMS
    LOOK_FRONT_RATIO = TD_LOOK_FRONT_RATIO
    LOOK_SIDE_RATIO = TD_LOOK_SIDE_RATIO
    LOOK_GUN_RATIO = TD_LOOK_GUN_RATIO
    LOOK_SPEED_RATIO = TD_LOOK_SPEED_RATIO
    DESIGN_KWARGS = {"mount_shift_m": "mount_shift"}

    def __init__(self, cal, front, side, rear, power, damage=None, penetration=None,
                 screen=0.0, nose=NOSE_FLAT, special_ammo=SPECIAL_HEAT, unbounded=False,
                 gun_length=None, mount_shift=0.0):
        cal, front, side, rear, power, screen = self._fit_inputs(
            cal, front, side, rear, power, screen, unbounded)
        if not unbounded:                       # боты ограничиваются в подборе сборки
            lo, hi = td_caliber_limits(front, side, rear)
            cal = clamp(cal, lo, hi)
        if nose != NOSE_PIKE or front <= NOSE_MIN_FRONT_MM:
            nose = NOSE_FLAT                    # щучий нос только при лобовой броне больше порога
        self.nose = nose                        # его читает Vehicle.describe

        self.cal = cal
        self.m_gun, self.m_casemate = td_masses(cal, effective_length(cal, gun_length))

        # положение орудия: «авто» по калибру + сдвиг игрока в границах, зависящих от калибра
        auto = mount_fwd_m(cal)
        lo_s, hi_s = mount_shift_range(cal)
        step = TD_DESIGN_PARAMS["mount_shift_m"].step
        shift = clamp(round_to(float(mount_shift), step), lo_s, hi_s)
        self.mount_shift = round(shift, 3)
        self.MOUNT_FWD_M = round(auto + shift, 1) + 0.0
        self.SUPPORT = support_level_for_mount(self.MOUNT_FWD_M)
        self.CASE_K = round(clamp((cal / _REF_CAL) ** TD_CASE_CAL_EXP, *TD_CASE_K_LIMITS), 1)
        layout = td_layout(self.MOUNT_FWD_M, nose)
        body = dataclasses.replace(TD_BODY, layout=layout,
                                   coll_half_w_m=layout.coll_half_w_m,
                                   coll_half_l_m=layout.coll_half_l_m,
                                   coll_shift_m=layout.coll_shift_m)

        def make_gun(size_k):
            return TDGunSpec(
                cal, size_k, power, self.m_gun, self.m_casemate,
                arc_deg=gun_arc_deg(cal), damage=damage, penetration=penetration,
                profile=TD_GUN, front_m=TD_GUN_FRONT_M, barrel_ref_m=TD_BARREL_VIS_REF_M,
                hesh=(special_ammo == SPECIAL_HESH),
                length_cal=gun_length,
                visual_k=self.HULL_SCALE)

        super().__init__(body, front, side, rear, power, self.m_gun + self.m_casemate, screen, make_gun)
        self.HULL_VARIANT = (round(self.MOUNT_FWD_M / MOUNT_STEP_M), self.SUPPORT, self.CASE_K,
                             round(self.TURRET_ARC_DEG), nose)

    # ---------- вывод в интерфейс ----------

    def mount_name(self):
        return ("носовое", "смещено к корме", "задняя опора")[self.SUPPORT]

    def main_stats(self):
        return {
            "Стоимость": fmt_num(self.cost),
            "HP": fmt_num(self.hp),
            "Масса": f"{self.mass:.1f} т",
            "Макс. скорость": f"{self.v_max:.0f} км/ч",
            "Средняя скорость": f"{self.v_avg:.0f} км/ч",
            "Скорость назад": f"{self.v_back:.0f} км/ч",
            "Разгон до средней": f"{self.t_avg:.1f} с",
            "Разгон до макс.": f"{self.t_max:.1f} с",
            "Поворот корпуса": f"{self.hull_turn:.0f} °/с",
            "УГН": f"±{self.TURRET_ARC_DEG / 2.0:.0f} °",
            "Наводка орудия": f"{self.turret_turn:.0f} °/с",
            "Крепление орудия": self.mount_name(),
            "Нос корпуса": NOSE_RU[self.nose],
            "Урон": f"{self.damage:.0f}",
            "Пробитие": f"{self.penetration:.0f} мм",
            "Нормализация": f"{self.normalization_deg:.1f}°",
            "Перезарядка": f"{self.reload:.2f} с",
            "Скорость снаряда": f"{self.SHELL_SPEED_PX / PX_PER_M:.0f} м/с",
            "Дальность": f"{self.SHELL_RANGE_PX / PX_PER_M:.0f} м",
            "Темп огня (DPS)": f"{self.dps:.0f}",
        }

    def internal_stats(self):
        return {
            "Удельная мощность": f"{self.pw:.1f} л.с./т",
            "Калибр / платформа": f"{self.q_gun:.2f}",
            "Бронированность": f"{self.q_arm:.2f}",
            "Лоб с экранами": f"{self.front + self.screen_mm:.0f} мм",
            "Гусеница: толщина / HP": f"{self.track_mm:.0f} мм / {self.track_max_hp:.0f}",
            "Ремонт гусеницы": f"{self.track_repair_s:.1f} с",
            "Длина ствола": f"{self.l_cal:.1f} кал.",
            "Масса орудия": f"{self.m_gun:.1f} т",
            "Инерция орудия": f"{self.i_turret:.1f} т·м²",
            "Угл. разгон корпуса": f"{self.hull_alpha:.0f} °/с²",
            "Угл. разгон орудия": f"{self.turret_alpha:.0f} °/с²",
            "Ось орудия от центра": f"{self.MOUNT_FWD_M:+.1f} м",
            "Сдвиг орудия": f"{self.mount_shift:+.1f} м",
            "Масштаб корпуса": f"{self.HULL_SCALE:.2f}",
            "Множитель урона": f"{self.damage_k:.2f}",
            "Множитель пробития": f"{self.pen_k:.2f}",
            "Бонус орудия (урон)": f"×{self.profile.dmg_mult(self.cal):.2f}",
            "Бонус орудия (пробитие)": f"×{self.profile.pen_mult(self.cal):.2f}",
        }