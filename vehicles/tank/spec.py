"""tank/spec.py — характеристики танка: шасси + орудие (GunVehicleSpec) + правила корпуса ОБТ."""
import dataclasses

from engine import clamp, fmt_num, PX_PER_M
from ..chassis.hulls import layout_for, HULL_CLASS_RU, NOSE_FLAT, NOSE_RU, layout_with_axis
from ..chassis.hull_noses import layout_with_nose, resolve_nose
from ..chassis.params import ENGINE_T_PER_HP, FRONT_SCREEN
from ..chassis.spec import ChassisBody, armor_masses, chassis_masses
from ..gun.ammo import SPECIAL_HEAT, SPECIAL_HESH
from ..gun.spec import GunSpec, turret_masses, REF_CAL, REF_POWER
from ..gun.vehicle_specific import GunVehicleSpec
from .hull_rules import class_index, class_for_index, near_class_border, turret_axis_for, caliber_limits
from .params import (
    PARAMS, FIXED_MASS_T, FRONT_AREA_M2, SIDE_AREA_M2, REAR_AREA_M2,
    HP_REF, HULL_COLL_HALF_W_M, HULL_COLL_HALF_L_M, HULL_COLL_SHIFT_M,
    LOOK_FRONT_RATIO, LOOK_SIDE_RATIO, LOOK_GUN_RATIO, LOOK_SPEED_RATIO,
)

# ==========================================
# ГРАНИЦЫ ВХОДОВ И ЭТАЛОН
# ==========================================
_CAL = PARAMS["gun_caliber_mm"]
_FRONT = PARAMS["front_armor_mm"]
_SIDE = PARAMS["side_armor_mm"]
_REAR = PARAMS["rear_armor_mm"]
_POWER = PARAMS["engine_power_hp"]

_AREAS = (FRONT_AREA_M2, SIDE_AREA_M2, REAR_AREA_M2)

# ---------- эталонный танк: считается теми же функциями, что и любой другой ----------
REF_GUN_MASS, REF_TURRET_MASS = turret_masses(REF_CAL)
REF_ENGINE_MASS = ENGINE_T_PER_HP * REF_POWER
REF_FILLING = FIXED_MASS_T + REF_GUN_MASS + REF_TURRET_MASS + REF_ENGINE_MASS
REF_ARMOR_MASS = sum(armor_masses(_AREAS, _FRONT.default, _SIDE.default, _REAR.default, 1.0))
REF_MASS = REF_FILLING + REF_ARMOR_MASS

TANK_BODY = ChassisBody(
    fixed_t=FIXED_MASS_T, engine_t_per_hp=ENGINE_T_PER_HP, areas_m2=_AREAS,
    ref_filling_t=REF_FILLING, ref_mass_t=REF_MASS, ref_power_hp=REF_POWER,
    ref_armor_share=REF_ARMOR_MASS / REF_MASS, hp_ref=HP_REF,
    coll_half_w_m=HULL_COLL_HALF_W_M, coll_half_l_m=HULL_COLL_HALF_L_M,
    coll_shift_m=HULL_COLL_SHIFT_M)

# ---------- вход классификатора корпуса ----------
def _armor_mass_index(front, side, rear):
    """Условная «масса брони»: толщина × площадь по зонам."""
    return FRONT_AREA_M2 * front + SIDE_AREA_M2 * side + REAR_AREA_M2 * rear

_ARMOR_IDX_MIN = _armor_mass_index(_FRONT.min, _SIDE.min, _REAR.min)
_ARMOR_IDX_MAX = _armor_mass_index(_FRONT.max, _SIDE.max, _REAR.max)

def hull_inputs(front, side, rear, power):
    """Броня и мощность, нормированные в 0..1 по границам ползунков."""
    armor_t = clamp((_armor_mass_index(front, side, rear) - _ARMOR_IDX_MIN)
                    / (_ARMOR_IDX_MAX - _ARMOR_IDX_MIN), 0.0, 1.0)
    power_t = clamp((power - _POWER.min) / (_POWER.max - _POWER.min), 0.0, 1.0)
    return armor_t, power_t

def caliber_range_for(front, side, rear, power):
    """(мин, макс) калибра, допустимые для корпуса, который получится при таких броне и мощности.
    Нужна конструктору (границы ползунка) и подбору сборок ботов."""
    return caliber_limits(class_index(*hull_inputs(front, side, rear, power)))

def estimate_mass(cal, front, side, rear, power, screen=0.0, unbounded=False):
    """Полная масса ОБТ, т, по входным параметрам, без создания TankSpec."""
    front = _FRONT.fit(front, unbounded)
    side = _SIDE.fit(side, unbounded)
    rear = _REAR.fit(rear, unbounded)
    power = _POWER.fit(power, unbounded)
    screen = clamp(float(screen), FRONT_SCREEN.min, FRONT_SCREEN.max)
    index = class_index(*hull_inputs(front, side, rear, power))
    cal = _CAL.fit(cal, unbounded)
    if not unbounded:
        lo, hi = caliber_limits(index)
        cal = clamp(cal, lo, hi)
    layout = layout_for(class_for_index(index))
    m_gun, m_turret = turret_masses(cal)
    _, filling, _, armor = chassis_masses(TANK_BODY, layout.area_k, front, side, rear,
                                          power, m_gun + m_turret, screen)
    return filling + sum(armor)

# ==========================================
# ТАНК
# ==========================================

class TankSpec(GunVehicleSpec):
    """Шасси считает ChassisSpec (предок), орудие и башню GunSpec (поле self.gun, свойства в базе)."""

    PARAMS = PARAMS
    LOOK_FRONT_RATIO = LOOK_FRONT_RATIO
    LOOK_SIDE_RATIO = LOOK_SIDE_RATIO
    LOOK_GUN_RATIO = LOOK_GUN_RATIO
    LOOK_SPEED_RATIO = LOOK_SPEED_RATIO

    def __init__(self, cal, front, side, rear, power, damage=None, penetration=None,
                 screen=0.0, nose=NOSE_FLAT, special_ammo=SPECIAL_HEAT, unbounded=False):
        # входные параметры (у ботов unbounded=True: верхних границ нет, ограничивает только бюджет)
        cal, front, side, rear, power, screen = self._fit_inputs(
            cal, front, side, rear, power, screen, unbounded)

        # класс корпуса зависит ТОЛЬКО от брони и мощности (не от массы и не от калибра)
        self.hull_index = class_index(*hull_inputs(front, side, rear, power))
        self.HULL_CLASS = class_for_index(self.hull_index)

        if not unbounded:
            lo, hi = caliber_limits(self.hull_index)
            cal = clamp(cal, lo, hi)
        self.cal = cal
        self.m_gun, self.m_turret = turret_masses(cal)

        nose = resolve_nose(nose, front, estimate_mass(cal, front, side, rear, power, screen, unbounded))
        self.nose = nose

        layout = layout_for(self.HULL_CLASS)
        layout = layout_with_axis(layout, turret_axis_for(self.HULL_CLASS, self.hull_index))
        layout = layout_with_nose(layout, nose)
        body = dataclasses.replace(TANK_BODY, layout=layout,
                                   coll_half_w_m=layout.coll_half_w_m,
                                   coll_half_l_m=layout.coll_half_l_m,
                                   coll_shift_m=layout.coll_shift_m)

        def make_gun(size_k):
            return GunSpec(
                cal, size_k, power, self.m_gun, self.m_turret, arc_deg=360.0,
                damage=damage, penetration=penetration, front_m=layout.turret_front_m,
                turret_scale_range=layout.turret_scale_range,
                visual_k=self.HULL_SCALE * layout.turret_k, hesh=(special_ammo == SPECIAL_HESH))

        super().__init__(body, front, side, rear, power, self.m_gun + self.m_turret, screen, make_gun)
        self.HULL_VARIANT = (self.layout.key,)

    # ---------- вывод в интерфейс ----------
    def main_stats(self):
        """Расчётные характеристики: {название: готовая строка} (порядок = порядок в панели)."""
        return {
            "Стоимость": fmt_num(self.cost),
            "HP": fmt_num(self.hp),
            "Масса": f"{self.mass:.1f} т",
            "Корпус": HULL_CLASS_RU[self.HULL_CLASS]
                      + (" (у границы)" if near_class_border(self.hull_index) else ""),
            "Нос корпуса": NOSE_RU[self.nose],
            "Нос: разгон / поворот": f"×{self.layout.accel_k:.2f} / ×{self.layout.turn_k:.2f}",
            "Макс. скорость": f"{self.v_max:.0f} км/ч",
            "Средняя скорость": f"{self.v_avg:.0f} км/ч",
            "Скорость назад": f"{self.v_back:.0f} км/ч",
            "Разгон до средней": f"{self.t_avg:.1f} с",
            "Разгон до макс.": f"{self.t_max:.1f} с",
            "Поворот корпуса": f"{self.hull_turn:.0f} °/с",
            "Поворот башни": f"{self.turret_turn:.0f} °/с",
            "Урон": f"{self.damage:.0f}",
            "Пробитие": f"{self.penetration:.0f} мм",
            "Перезарядка": f"{self.reload:.2f} с",
            "Скорость снаряда": f"{self.SHELL_SPEED_PX / PX_PER_M:.0f} м/с",
            "Дальность": f"{self.SHELL_RANGE_PX / PX_PER_M:.0f} м",
            "Темп огня (DPS)": f"{self.dps:.0f}",
        }

    def internal_stats(self):
        """Внутренние показатели (полезны при отладке баланса)."""
        return {
            "Индекс корпуса": f"{self.hull_index:+.2f}",
            "Удельная мощность": f"{self.pw:.1f} л.с./т",
            "Калибр / платформа": f"{self.q_gun:.2f}",
            "Бронированность": f"{self.q_arm:.2f}",
            "Лоб с экранами": f"{self.front + self.screen_mm:.0f} мм",
            "Длина ствола": f"{self.l_cal:.1f} кал.",
            "Инерция башни": f"{self.i_turret:.1f} т·м²",
            "Угл. разгон корпуса": f"{self.hull_alpha:.0f} °/с²",
            "Угл. разгон башни": f"{self.turret_alpha:.0f} °/с²",
            "Множитель урона": f"{self.damage_k:.2f}",
            "Множитель пробития": f"{self.pen_k:.2f}",
        }