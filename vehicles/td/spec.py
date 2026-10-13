"""td/spec.py — характеристики ПТ-САУ: шасси (ChassisSpec) + орудие (TDGunSpec) + положение орудия."""
import dataclasses
import math

from engine import clamp, lerp, fmt_num, PX_PER_M
from ..chassis_spec import ChassisSpec, ChassisBody, armor_masses, round_to
from ..chassis_params import COLLISION_MARGIN_PX
from ..tank.gun_spec import GunSpec, turret_masses
from ..tank.gun_tuning import TD_GUN
from ..tank.look import Look, level
from ..tank.params import (
    REF_L_CAL, BARREL_VISIBLE_K, GUN_ARM_BASE_M, GUN_ARM_BARREL_K,
    TURRET_INERTIA_EXP, TURRET_POWER_EXP, ENGINE_T_PER_HP,
    HULL_COLL_HALF_W_M, HULL_COLL_HALF_L_M, COST_REF, BUILD_TIME_REF,
)
from ..tank.spec import _raw_cost, _round_cost
from .params import (
    TD_PARAMS, TD_FIXED_MASS_T, TD_FRONT_AREA_M2, TD_SIDE_AREA_M2, TD_REAR_AREA_M2, TD_HP_REF,
    TD_CASEMATE_K, gun_arc_deg, TD_TRAVERSE_REF, TD_TRAVERSE_MIN, TD_TRAVERSE_MAX, TD_SPINUP_REF,
    TD_GUN_FRONT_M, TD_BARREL_VIS_REF_M, MOUNT_FRONT_FWD_M, MOUNT_REAR_FWD_M, MOUNT_CAL,
    MOUNT_STEP_M, SUPPORT_T, TD_LOOK_FRONT_RATIO, TD_LOOK_SIDE_RATIO, TD_LOOK_GUN_RATIO,
    TD_LOOK_SPEED_RATIO,
)

_CAL = TD_PARAMS["gun_caliber_mm"]
_FRONT = TD_PARAMS["front_armor_mm"]
_SIDE = TD_PARAMS["side_armor_mm"]
_REAR = TD_PARAMS["rear_armor_mm"]
_POWER = TD_PARAMS["engine_power_hp"]
_AREAS = (TD_FRONT_AREA_M2, TD_SIDE_AREA_M2, TD_REAR_AREA_M2)

# ==========================================
# 1. ПОЛОЖЕНИЕ ОРУДИЯ (зависит только от калибра)
# ==========================================
# Зависимость только от калибра, а не от массы, снимает порочный круг: хитбокс считается
# в ChassisSpec.__init__ раньше, чем известен size_k.

def mount_t(cal):
    """0 — орудие на лбу, 1 — на задней опоре (сглаженный переход)."""
    lo, hi = MOUNT_CAL
    x = clamp((cal - lo) / (hi - lo), 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)

def mount_fwd_m(cal):
    """Насколько ось орудия впереди центра корпуса, м (минус = позади). Квантуется шагом MOUNT_STEP_M."""
    raw = lerp(MOUNT_FRONT_FWD_M, MOUNT_REAR_FWD_M, mount_t(cal))
    return round(round_to(raw, MOUNT_STEP_M), 3)

def support_level(cal):
    """Уровень задней опоры: 0 нет, 1 малая, 2 большая."""
    t = mount_t(cal)
    return 0 if t < SUPPORT_T[0] else (1 if t < SUPPORT_T[1] else 2)

# ==========================================
# 2. ЭТАЛОН ПТ-САУ
# ==========================================
def td_masses(cal):
    """Массы орудия и рубки калибра cal, т: (орудие, рубка)."""
    gun, turret = turret_masses(cal)
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
    coll_half_w_m=HULL_COLL_HALF_W_M, coll_half_l_m=HULL_COLL_HALF_L_M,
    coll_shift_m=0.0)       # реальный сдвиг подставляется в TDSpec (зависит от калибра)

_REF_BARREL_M = _REF_CAL * REF_L_CAL / 1000.0 * BARREL_VISIBLE_K
TD_REF_GUN_INERTIA = _REF_GUN_MASS * (GUN_ARM_BASE_M + GUN_ARM_BARREL_K * _REF_BARREL_M) ** 2

# ==========================================
# 3. ОРУДИЕ БЕЗ БАШНИ
# ==========================================
class TDGunSpec(GunSpec):
    """Вращается только орудие, а не башня: инерция меньше, наводка медленнее и в узком секторе.
    Имена turret_turn / turret_alpha сохранены: их читает GunVehicle._aim_turret."""

    def _calc_turret(self, size_k, power, m_gun, m_turret):
        barrel_len = self.cal * self.l_cal / 1000.0 * BARREL_VISIBLE_K
        arm = GUN_ARM_BASE_M * size_k + GUN_ARM_BARREL_K * barrel_len
        self.i_turret = m_gun * arm ** 2
        i_rel = self.i_turret / TD_REF_GUN_INERTIA
        self.turret_turn = clamp(
            TD_TRAVERSE_REF * (power / _POWER.default) ** TURRET_POWER_EXP * i_rel ** -TURRET_INERTIA_EXP,
            TD_TRAVERSE_MIN, TD_TRAVERSE_MAX)
        self.turret_alpha = self.turret_turn / (TD_SPINUP_REF * i_rel ** 0.5)

# ==========================================
# 4. ПТ-САУ
# ==========================================
class TDSpec(ChassisSpec):
    def __init__(self, cal, front, side, rear, power, damage=None, penetration=None):
        cal = clamp(float(cal), _CAL.min, _CAL.max)
        front = clamp(float(front), _FRONT.min, _FRONT.max)
        side = clamp(float(side), _SIDE.min, _SIDE.max)
        rear = clamp(float(rear), _REAR.min, _REAR.max)
        power = clamp(float(power), _POWER.min, _POWER.max)

        self.cal = cal
        self.m_gun, self.m_casemate = td_masses(cal)
        self.MOUNT_FWD_M = mount_fwd_m(cal)
        self.SUPPORT = support_level(cal)
        # положение орудия = сдвиг хитбокса корпуса относительно оси (x, y) машины
        body = dataclasses.replace(TD_BODY, coll_shift_m=self.MOUNT_FWD_M)
        super().__init__(body, front, side, rear, power, payload_t=self.m_gun + self.m_casemate)

        self.gun = TDGunSpec(cal, self.size_k, power, self.m_gun, self.m_casemate,
                             arc_deg=gun_arc_deg(cal), damage=damage, penetration=penetration,
                             profile=TD_GUN, front_m=TD_GUN_FRONT_M,
                             barrel_ref_m=TD_BARREL_VIS_REF_M)
        self.__dict__.update(vars(self.gun))
        self.HULL_VARIANT = (round(self.MOUNT_FWD_M / MOUNT_STEP_M), self.SUPPORT)

        self._calc_reach()
        self._calc_economy()
        self._calc_look()

    # ---------- фабрики ----------
    @classmethod
    def from_values(cls, v):
        return cls(v["gun_caliber_mm"], v["front_armor_mm"], v["side_armor_mm"],
                   v["rear_armor_mm"], v["engine_power_hp"],
                   damage=v.get("gun_damage"), penetration=v.get("gun_penetration"))

    @classmethod
    def from_config(cls):
        return cls(_CAL.default, _FRONT.default, _SIDE.default, _REAR.default, _POWER.default)

    # ---------- производные ----------
    def _calc_reach(self):
        """Радиус отсечения по экрану: корпус (уже со сдвигом оси) и дульный срез."""
        t = self.TURRET_SCALE * PX_PER_M
        barrel_end = (self.GUN_FRONT_M + self.BARREL_LEN_M) * t
        barrel_half_w = (self.BARREL_THICK_M + 0.08) * t / 2.0
        barrel_reach = math.hypot(barrel_end, barrel_half_w)
        self.REACH_PX = max(self.HULL_REACH_PX, barrel_reach) + COLLISION_MARGIN_PX

    def _calc_economy(self):
        """Цена по формуле танка, но урон и пробитие считаются вместе с бонусом профиля:
        сильное орудие стоит дороже."""
        prof = self.profile
        raw = _raw_cost(self.cal, self.front, self.side, self.rear, self.power,
                        self.damage_k * prof.dmg_mult(self.cal),
                        self.pen_k * prof.pen_mult(self.cal))
        self.cost = _round_cost(raw)
        self.build_time = BUILD_TIME_REF * raw / COST_REF

    def _calc_look(self):
        self.LOOK = Look(
            front=level(self.front / _FRONT.default, TD_LOOK_FRONT_RATIO),
            side=level(self.side / _SIDE.default, TD_LOOK_SIDE_RATIO),
            gun=level(self.cal / _REF_CAL, TD_LOOK_GUN_RATIO),
            speed=level(self.q_pw, TD_LOOK_SPEED_RATIO),
        )

    # ---------- вывод в интерфейс ----------
    def mount_name(self):
        return ("носовое", "смещено к корме", "задняя опора")[self.SUPPORT]

    def main_stats(self):
        return {
            "Стоимость": fmt_num(self.cost),
            "Время производства": f"{self.build_time:.1f} с",
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
            "Урон": f"{self.damage:.0f}",
            "Пробитие": f"{self.penetration:.0f} мм",
            "Перезарядка": f"{self.reload:.2f} с",
            "Темп огня (DPS)": f"{self.dps:.0f}",
        }

    def internal_stats(self):
        return {
            "Удельная мощность": f"{self.pw:.1f} л.с./т",
            "Калибр / платформа": f"{self.q_gun:.2f}",
            "Бронированность": f"{self.q_arm:.2f}",
            "Длина ствола": f"{self.l_cal:.1f} кал.",
            "Инерция орудия": f"{self.i_turret:.1f} т·м²",
            "Угл. разгон корпуса": f"{self.hull_alpha:.0f} °/с²",
            "Угл. разгон орудия": f"{self.turret_alpha:.0f} °/с²",
            "Ось орудия от центра": f"{self.MOUNT_FWD_M:+.1f} м",
            "Множитель урона": f"{self.damage_k:.2f}",
            "Множитель пробития": f"{self.pen_k:.2f}",
            "Бонус орудия (урон)": f"×{self.profile.dmg_mult(self.cal):.2f}",
            "Бонус орудия (пробитие)": f"×{self.profile.pen_mult(self.cal):.2f}",
        }