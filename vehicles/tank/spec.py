"""tank/spec.py — характеристики танка: шасси (ChassisSpec) + орудие (GunSpec) + цена и оформление."""
import itertools
import math
import dataclasses

from ..hulls import (
    classify, class_index, class_for_index, layout_for, HULL_CLASS_RU,
    layout_with_nose, NOSE_FLAT, NOSE_PIKE, NOSE_RU, NOSE_MIN_FRONT_MM, near_class_border,
    layout_with_axis, turret_axis_for
)
from engine import clamp, fmt_num, PX_PER_M, round_to
from ..chassis_spec import ChassisSpec, ChassisBody, armor_masses
from ..chassis_params import COLLISION_MARGIN_PX, ENGINE_T_PER_HP, FRONT_SCREEN, SCREEN_LOOK_STEPS
from ..gun_spec import GunSpec, turret_masses, REF_CAL, REF_POWER
from ..gun_tuning import tuning_k_bounds
from ..gun_params import GUN_TUNE_COST_D, GUN_TUNE_COST_P
from ..look import Look, level
from .params import (
    PARAMS, FIXED_MASS_T, FRONT_AREA_M2, SIDE_AREA_M2, REAR_AREA_M2,
    HP_REF, HULL_COLL_HALF_W_M, HULL_COLL_HALF_L_M, HULL_COLL_SHIFT_M,
    COST_REF, COST_MIN, COST_MAX, COST_STEP, BUILD_TIME_REF, COST_ARMOR_ZONES, COST_PARTS,
    LOOK_FRONT_RATIO, LOOK_SIDE_RATIO, LOOK_GUN_RATIO, LOOK_SPEED_RATIO,
)

# ==========================================
# 1. ГРАНИЦЫ ВХОДОВ И ЭТАЛОН
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
REF_HULL_MASS = FIXED_MASS_T + REF_TURRET_MASS

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

# ==========================================
# 2. СТОИМОСТЬ: индекс ценности -> цена
# ==========================================

def _cost_index(cal, front, side, rear, power, dmg_k=1.0, pen_k=1.0):
    """Ценность машины относительно эталона (у эталона 1.0). Зависит только от входных параметров.
    dmg_k и pen_k: выбранные урон и пробитие относительно номинала калибра (1.0 = номинал)."""
    turret = turret_masses(cal)[1]
    zf, zs, zr = COST_ARMOR_ZONES
    levels = {
        "armor":  (zf * front / _FRONT.default + zs * side / _SIDE.default
                   + zr * rear / _REAR.default) / (zf + zs + zr),
        "hull":   (FIXED_MASS_T + turret) / REF_HULL_MASS,
        "engine": power / REF_POWER,
        "gun":    cal / REF_CAL * dmg_k ** GUN_TUNE_COST_D * pen_k ** GUN_TUNE_COST_P,
    }
    return sum(weight * levels[name] ** power_k for name, (weight, power_k) in COST_PARTS.items())

# Самая дешёвая и самая дорогая возможные машины (все ползунки в минимуме или в максимуме)
_DK, _PK = tuning_k_bounds()
_indexes = [_cost_index(*corner) for corner in itertools.product(
    *((p.min, p.max) for p in (_CAL, _FRONT, _SIDE, _REAR, _POWER)), _DK, _PK)]
INDEX_MIN, INDEX_MAX = min(_indexes), max(_indexes)
# Степени подобраны так, чтобы эталон стоил COST_REF, самая дешёвая машина COST_MIN, самая дорогая COST_MAX.
COST_EXP_LOW = math.log(COST_MIN / COST_REF) / math.log(INDEX_MIN)
COST_EXP_HIGH = math.log(COST_MAX / COST_REF) / math.log(INDEX_MAX)

def _price(index):
    return COST_REF * index ** (COST_EXP_LOW if index < 1.0 else COST_EXP_HIGH)

def raw_cost(cal, front, side, rear, power, dmg_k=1.0, pen_k=1.0):
    """Цена до округления."""
    return _price(_cost_index(cal, front, side, rear, power, dmg_k, pen_k))

def round_cost(raw):
    """Округление цены до шага и в допустимых границах."""
    return clamp(round_to(raw, COST_STEP), COST_MIN, COST_MAX)

def cost_for(cal, front, side, rear, power, dmg_k=1.0, pen_k=1.0):
    """Цена машины по входным параметрам без полного расчёта TankSpec (для подбора билдов ботов)."""
    return round_cost(raw_cost(cal, front, side, rear, power, dmg_k, pen_k))

# ==========================================
# 3. ТАНК
# ==========================================
class TankSpec(ChassisSpec):
    """Шасси считает ChassisSpec (родитель), орудие и башню GunSpec (поле self.gun).
    Атрибуты орудия копируются в сам объект, поэтому снаружи всё читается как раньше:
    spec.v_max (шасси), spec.damage (орудие). Имена в ЗАГЛАВНЫХ буквах читают Tank и Renderer."""

    def __init__(self, cal, front, side, rear, power, damage=None, penetration=None,
                 screen=0.0, nose=NOSE_FLAT):
        # входные параметры (с защитой от выхода за границы)
        cal = clamp(float(cal), _CAL.min, _CAL.max)
        front = clamp(float(front), _FRONT.min, _FRONT.max)
        side = clamp(float(side), _SIDE.min, _SIDE.max)
        rear = clamp(float(rear), _REAR.min, _REAR.max)
        power = clamp(float(power), _POWER.min, _POWER.max)
        screen = clamp(float(screen), FRONT_SCREEN.min, FRONT_SCREEN.max)

        if nose != NOSE_PIKE or front <= NOSE_MIN_FRONT_MM:
            nose = NOSE_FLAT                    # щучий нос только при лобовой броне больше порога
        if nose == NOSE_PIKE:
            screen = 0.0                        # экраны со щучьим носом пока не сочетаются
        self.nose = nose

        self.cal = cal
        self.m_gun, self.m_turret = turret_masses(cal)

        # класс корпуса зависит ТОЛЬКО от ползунков (не от массы)
        self.hull_index = class_index(*hull_inputs(front, side, rear, power))
        self.HULL_CLASS = class_for_index(self.hull_index)
        layout = layout_for(self.HULL_CLASS)
        layout = layout_with_axis(layout, turret_axis_for(self.HULL_CLASS, self.hull_index))
        layout = layout_with_nose(layout, nose)
        body = dataclasses.replace(TANK_BODY, layout=layout,
                                   coll_half_w_m=layout.coll_half_w_m,
                                   coll_half_l_m=layout.coll_half_l_m,
                                   coll_shift_m=layout.coll_shift_m)
        super().__init__(body, front, side, rear, power,
                         payload_t=self.m_gun + self.m_turret, screen_mm=screen)

        # arc_deg=360: круговая башня. У будущей ПТ-САУ здесь будет маленький сектор.
        self.gun = GunSpec(cal, self.size_k, power, self.m_gun, self.m_turret, arc_deg=360.0,
                           damage=damage, penetration=penetration,
                           front_m=layout.turret_front_m)
        self.__dict__.update(vars(self.gun))
        self.HULL_VARIANT = (self.layout.key,)

        self._calc_reach()
        self._calc_economy()
        self._calc_look()

    # ---------- фабрики ----------
    @classmethod
    def from_values(cls, v):
        """v — словарь значений ползунков. Ключи тюнинга необязательны: нет ключа = номинал калибра
        (так работают боты, у которых этих значений нет)."""
        return cls(v["gun_caliber_mm"], v["front_armor_mm"], v["side_armor_mm"],
                   v["rear_armor_mm"], v["engine_power_hp"],
                   damage=v.get("gun_damage"), penetration=v.get("gun_penetration"),
                   screen=v.get("front_screen_mm", 0.0), nose=v.get("front_nose", NOSE_FLAT))

    @classmethod
    def from_config(cls):
        """Танк из стартовых значений (params.PARAMS[...].default)."""
        return cls(_CAL.default, _FRONT.default, _SIDE.default, _REAR.default, _POWER.default)

    # ---------- то, что требует и шасси, и орудие ----------
    def _calc_reach(self):
        """Радиус, в который попадает всё, что машина может задеть за кадр, и который нужен для
        отсечения по экрану. Ствол в столкновениях не участвует, но на экране его надо дорисовать."""
        t = self.TURRET_SCALE * PX_PER_M
        barrel_end = (self.GUN_FRONT_M + self.BARREL_LEN_M) * t
        barrel_half_w = (self.BARREL_THICK_M + 0.08) * t / 2.0
        barrel_reach = math.hypot(barrel_end, barrel_half_w)
        self.REACH_PX = max(self.HULL_REACH_PX, barrel_reach) + COLLISION_MARGIN_PX

    def _calc_economy(self):
        raw = raw_cost(self.cal, self.front + self.screen_mm, self.side, self.rear, self.power,
                       self.damage_k, self.pen_k)
        self.cost = round_cost(raw)
        self.build_time = BUILD_TIME_REF * raw / COST_REF

    def _calc_look(self):
        self.LOOK = Look(
            front=level(self.front / _FRONT.default, LOOK_FRONT_RATIO),
            side=level(self.side / _SIDE.default, LOOK_SIDE_RATIO),
            gun=level(self.cal / REF_CAL, LOOK_GUN_RATIO),
            speed=level(self.q_pw, LOOK_SPEED_RATIO),
            screen=level(self.screen_mm, SCREEN_LOOK_STEPS),
        )

    # ---------- вывод в интерфейс ----------
    def main_stats(self):
        """Расчётные характеристики: {название: готовая строка} (порядок = порядок в панели)."""
        return {
            "Стоимость": fmt_num(self.cost),
            "Время производства": f"{self.build_time:.1f} с",
            "HP": fmt_num(self.hp),
            "Масса": f"{self.mass:.1f} т",
            "Корпус": HULL_CLASS_RU[self.HULL_CLASS]
                      + (" (у границы)" if near_class_border(self.hull_index) else ""),
            "Нос корпуса": NOSE_RU[self.nose],
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