"""tank/spec.py — формулы конструктора: входные параметры -> все характеристики танка."""
import itertools
import math

from engine import PX_PER_M, clamp, fmt_num
from .params import (
    PARAMS, REF_L_CAL, FIXED_MASS_T, GUN_MASS_T, GUN_MASS_AT_MM, TURRET_MASS_REF_T, ENGINE_T_PER_HP,
    V_CAP_KMH, PW_SCALE, V_MASS_EXP, V_MIN_KMH, V_MAX_CLAMP_KMH, V_AVG_BASE, V_AVG_GAIN,
    BACK_SPEED_K, V_BACK_CAP_KMH,
    GUN_DAMAGE_REF, GUN_PEN_REF, GUN_RELOAD_REF, GUN_RELOAD_MIN, GUN_OVERLOAD_Q, GUN_OVERLOAD_K,
    HP_REF, HP_EXP, HP_STEP,
    COST_REF, COST_MIN, COST_MAX, COST_STEP, BUILD_TIME_REF, COST_ARMOR_ZONES, COST_PARTS,
    TURRET_FRONT_M, BARREL_VISIBLE_K, BARREL_THICK_REF_M,
    SHELL_LEN_K, FRONT_AREA_M2, SIDE_AREA_M2, REAR_AREA_M2, STEEL_T_PER_M3,
    HULL_COLL_HALF_W_M, HULL_COLL_HALF_L_M, HULL_COLL_SHIFT_M,
    ACCEL_K, ACCEL_MIN, ACCEL_MAX, ACCEL_TAIL_FLOOR, REVERSE_ACCEL_K,
    COAST_DECEL, BRAKE_DECEL, HULL_TURN_CAP, HULL_TURN_MIN, HULL_ALPHA_REF,
    HULL_ALPHA_MIN, HULL_ALPHA_MAX, GUN_ARM_BASE_M, GUN_ARM_BARREL_K,
    TURRET_TURN_REF, TURRET_TURN_MIN, TURRET_TURN_MAX, TURRET_POWER_EXP,
    TURRET_INERTIA_EXP, TURRET_SPINUP_REF, TURRET_RADIUS_M, BARREL_LEN_STEP_M,
)

# ==========================================
# 1. ГРАНИЦЫ ВХОДОВ И ЭТАЛОН
# ==========================================
_CAL = PARAMS["gun_caliber_mm"]
_FRONT = PARAMS["front_armor_mm"]
_SIDE = PARAMS["side_armor_mm"]
_REAR = PARAMS["rear_armor_mm"]
_POWER = PARAMS["engine_power_hp"]

REF_CAL = _CAL.default
REF_POWER = _POWER.default

def round_to(value, step):
    """Округление до ближайшего кратного step (половина округляется вверх)."""
    return math.floor(value / step + 0.5) * step

def _unit_masses(cal, power):
    """Массы агрегатов без брони, т: (орудие, башня, силовая установка)."""
    return (GUN_MASS_T * (cal / GUN_MASS_AT_MM) ** 2,
            TURRET_MASS_REF_T * (cal / REF_CAL) ** 1.5,
            ENGINE_T_PER_HP * power)

def _armor_masses(front, side, rear, size_k):
    """Массы брони лба, борта и кормы, т."""
    k2 = size_k ** 2
    return tuple(mm / 1000.0 * area * STEEL_T_PER_M3 * k2
                 for mm, area in ((front, FRONT_AREA_M2), (side, SIDE_AREA_M2), (rear, REAR_AREA_M2)))

def _turret_inertia(m_turret, m_gun, size_k, barrel_len_m):
    """Момент инерции вращающейся части (башня + орудие), т·м²."""
    r_turret = TURRET_RADIUS_M * size_k
    r_gun = GUN_ARM_BASE_M * size_k + GUN_ARM_BARREL_K * barrel_len_m
    return m_turret * r_turret ** 2 + m_gun * r_gun ** 2

# ---------- эталонный танк: считается теми же функциями, что и любой другой ----------
REF_GUN_MASS, REF_TURRET_MASS, REF_ENGINE_MASS = _unit_masses(REF_CAL, REF_POWER)
REF_FILLING = FIXED_MASS_T + REF_GUN_MASS + REF_TURRET_MASS + REF_ENGINE_MASS
REF_ARMOR_MASS = sum(_armor_masses(_FRONT.default, _SIDE.default, _REAR.default, 1.0))
REF_MASS = REF_FILLING + REF_ARMOR_MASS
REF_PW = REF_POWER / REF_MASS
REF_ARMOR_SHARE = REF_ARMOR_MASS / REF_MASS
REF_HULL_MASS = FIXED_MASS_T + REF_TURRET_MASS
REF_TURRET_INERTIA = _turret_inertia(REF_TURRET_MASS, REF_GUN_MASS, 1.0,
                                     REF_CAL * REF_L_CAL / 1000.0 * BARREL_VISIBLE_K)

# ==========================================
# 2. СТОИМОСТЬ: индекс ценности -> цена
# ==========================================
def _cost_index(cal, front, side, rear, power):
    """Ценность машины относительно эталона (у эталона 1.0). Зависит только от входных параметров."""
    turret = _unit_masses(cal, power)[1]
    zf, zs, zr = COST_ARMOR_ZONES
    levels = {
        "armor":  (zf * front / _FRONT.default + zs * side / _SIDE.default
                   + zr * rear / _REAR.default) / (zf + zs + zr),
        "hull":   (FIXED_MASS_T + turret) / REF_HULL_MASS,
        "engine": power / REF_POWER,
        "gun":    cal / REF_CAL,
    }
    return sum(weight * levels[name] ** power_k for name, (weight, power_k) in COST_PARTS.items())

# Самая дешёвая и самая дорогая возможные машины (все ползунки в минимуме или в максимуме).
_indexes = [_cost_index(*corner) for corner in itertools.product(
    *((p.min, p.max) for p in (_CAL, _FRONT, _SIDE, _REAR, _POWER)))]
INDEX_MIN, INDEX_MAX = min(_indexes), max(_indexes)
# Степени подобраны так, чтобы эталон стоил COST_REF, самая дешёвая машина COST_MIN, самая дорогая COST_MAX.
COST_EXP_LOW = math.log(COST_MIN / COST_REF) / math.log(INDEX_MIN)
COST_EXP_HIGH = math.log(COST_MAX / COST_REF) / math.log(INDEX_MAX)

def _price(index):
    """Цена до округления."""
    return COST_REF * index ** (COST_EXP_LOW if index < 1.0 else COST_EXP_HIGH)

# ==========================================
# 3. ТАНК
# ==========================================
class TankSpec:
    """Считает всё один раз в __init__. Имена в ЗАГЛАВНЫХ буквах читают Tank и Renderer."""

    def __init__(self, cal, front, side, rear, power):
        # входные параметры (с защитой от выхода за границы)
        self.cal = clamp(float(cal), _CAL.min, _CAL.max)
        self.front = clamp(float(front), _FRONT.min, _FRONT.max)
        self.side = clamp(float(side), _SIDE.min, _SIDE.max)
        self.rear = clamp(float(rear), _REAR.min, _REAR.max)
        self.power = clamp(float(power), _POWER.min, _POWER.max)
        self._calc()

    # ---------- фабрики ----------
    @classmethod
    def from_values(cls, v):
        """v — словарь из ConstructorUI.get_values()."""
        return cls(v["gun_caliber_mm"], v["front_armor_mm"], v["side_armor_mm"],
                   v["rear_armor_mm"], v["engine_power_hp"])

    @classmethod
    def from_config(cls):
        """Танк из стартовых значений (params.PARAMS[...].default)."""
        return cls(_CAL.default, _FRONT.default, _SIDE.default, _REAR.default, _POWER.default)

    # ---------- расчёт: порядок вызовов важен, каждый метод использует результаты предыдущих ----------
    def _calc(self):
        self._calc_mass()       # 1. масса
        self._calc_internal()   # 2. внутренние переменные
        self._calc_mobility()   # 3. ход и повороты
        self._calc_gun()        # 4. орудие
        self._calc_hp()         # 5. HP
        self._calc_economy()    # 6. стоимость и время
        self._calc_visual()     # 7. внешний вид
        self._calc_collision()  # 8. размеры для столкновений
        self._calc_shot()       # 9. выстрел и эффекты

    def _calc_mass(self):
        self.m_gun, self.m_turret, self.m_engine = _unit_masses(self.cal, self.power)
        self.m_fixed = FIXED_MASS_T
        self.filling = self.m_fixed + self.m_engine + self.m_turret + self.m_gun
        self.size_k = (self.filling / REF_FILLING) ** (1.0 / 3.0)   # линейный размер, у эталона ровно 1
        self.m_front, self.m_side, self.m_rear = _armor_masses(self.front, self.side, self.rear, self.size_k)
        self.m_armor = self.m_front + self.m_side + self.m_rear
        self.mass = self.filling + self.m_armor

    def _calc_internal(self):
        cr = self.cal / REF_CAL

        self.pw = self.power / self.mass                              # удельная мощность
        self.s = 1.0 - math.exp(-self.pw / PW_SCALE)                  # «ходовая отдача» 0..1
        self.q_pw = self.pw / REF_PW                                  # мощность относительно эталона
        self.q_gun = cr / self.size_k
        self.q_arm = (self.m_armor / self.mass) / REF_ARMOR_SHARE     # доля брони относительно эталона
        self.l_cal = clamp(REF_L_CAL * self.size_k ** 0.45, 30.0, 55.0)

    def _calc_mobility(self):
        M = self.mass

        self.v_max = clamp(V_CAP_KMH * self.s * (REF_MASS / M) ** V_MASS_EXP, V_MIN_KMH, V_MAX_CLAMP_KMH)
        self.v_avg = self.v_max * (V_AVG_BASE + V_AVG_GAIN * self.s)
        self.v_back = min(BACK_SPEED_K * self.v_max, V_BACK_CAP_KMH)
        # --- корпус: мощность против сопротивления грунта и инерции ---
        # момент сопротивления ~ M * size_k, момент тяги ~ P * size_k, инерция ~ M * size_k²
        self.q_turn = self.q_pw / self.size_k
        self.hull_turn = max(
            HULL_TURN_MIN,
            HULL_TURN_CAP * (1.0 - math.exp(-math.log(2.0) * self.q_turn)))   # эталон = половина потолка
        self.hull_alpha = clamp(HULL_ALPHA_REF * self.q_turn, HULL_ALPHA_MIN, HULL_ALPHA_MAX)

        # --- башня: инерция башни и орудия, привод от двигателя ---
        barrel_len = self.cal * self.l_cal / 1000.0 * BARREL_VISIBLE_K
        self.i_turret = _turret_inertia(self.m_turret, self.m_gun, self.size_k, barrel_len)
        i_rel = self.i_turret / REF_TURRET_INERTIA
        self.turret_turn = clamp(
            TURRET_TURN_REF * (self.power / REF_POWER) ** TURRET_POWER_EXP * i_rel ** -TURRET_INERTIA_EXP,
            TURRET_TURN_MIN, TURRET_TURN_MAX)
        self.turret_alpha = self.turret_turn / (TURRET_SPINUP_REF * i_rel ** 0.5)   # °/с²
        # разгон и торможение (км/ч в секунду)
        self.accel = clamp(ACCEL_K * self.pw, ACCEL_MIN, ACCEL_MAX)
        self.accel_back = self.accel * REVERSE_ACCEL_K
        self.decel_coast = COAST_DECEL
        self.decel_brake = BRAKE_DECEL
        self.t_avg = self.v_avg / self.accel                       # время разгона до средней скорости
        self.t_max = self._time_to_speed(self.v_max - 0.5)         # время разгона до (почти) максимальной

    def accel_at(self, v):
        """Ускорение (км/ч/с) при скорости v >= 0 км/ч.
        До v_avg постоянное, потом линейно падает к нулю у v_max (но не ниже доли ACCEL_TAIL_FLOOR)."""
        if v >= self.v_max:
            return 0.0
        if v <= self.v_avg:
            return self.accel
        tail = (self.v_max - v) / (self.v_max - self.v_avg)
        return self.accel * max(tail, ACCEL_TAIL_FLOOR)

    def _time_to_speed(self, target, dt=0.05):
        """Сколько секунд разгоняться с места до скорости target (численно, один раз при расчёте танка)."""
        v, t = 0.0, 0.0
        while v < target and t < 120.0:
            v += self.accel_at(v) * dt
            t += dt
        return t

    def _calc_gun(self):
        cr = self.cal / REF_CAL
        lr = self.l_cal / REF_L_CAL

        self.damage = GUN_DAMAGE_REF * cr ** 2 * lr ** 0.3
        self.penetration = GUN_PEN_REF * cr ** 0.8 * lr ** 0.5
        self.reload = max(GUN_RELOAD_MIN, GUN_RELOAD_REF * cr * self.q_gun ** 0.5)

        overload = max(0.0, self.q_gun - GUN_OVERLOAD_Q)
        self.reload *= 1.0 + GUN_OVERLOAD_K * overload

    def _calc_hp(self):
        """Здоровье растёт с массой «начинки» (корпус, башня, орудие, двигатель). Броню сюда не включаем:
        она уже защищает через правила пробития (armor.py), и второй бонус был бы двойным учётом."""
        raw = HP_REF * (self.filling / REF_FILLING) ** HP_EXP
        self.hp = max(HP_STEP, round_to(raw, HP_STEP))

    def _calc_economy(self):
        raw = _price(_cost_index(self.cal, self.front, self.side, self.rear, self.power))
        self.cost = clamp(round_to(raw, COST_STEP), COST_MIN, COST_MAX)
        self.build_time = BUILD_TIME_REF * raw / COST_REF

    def _calc_visual(self):
        cal = self.cal
        cr = cal / REF_CAL

        self.HULL_SCALE = self.size_k
        self.TURRET_SCALE = self.size_k * clamp(cr ** 0.35, 0.8, 1.15)
        self.BARREL_LEN_M = round(cal * self.l_cal / 1000.0 * BARREL_VISIBLE_K / BARREL_LEN_STEP_M) * BARREL_LEN_STEP_M
        self.BARREL_THICK_M = max(0.18, BARREL_THICK_REF_M * cr ** 0.7)

    def _calc_collision(self):
        """Хитбоксы для столкновений (мировые px): корпус и ствол. Масштабируются вместе со спрайтами."""
        k = self.HULL_SCALE * PX_PER_M
        self.COLLISION_HALF_W_PX = HULL_COLL_HALF_W_M * k
        self.COLLISION_HALF_L_PX = HULL_COLL_HALF_L_M * k
        self.COLLISION_SHIFT_PX = HULL_COLL_SHIFT_M * k

        # ствол: прямоугольник вдоль оси башни, от торца маски орудия до дульного среза
        t = self.TURRET_SCALE * PX_PER_M
        self.BARREL_COLL_START_PX = TURRET_FRONT_M * t
        self.BARREL_COLL_END_PX = (TURRET_FRONT_M + self.BARREL_LEN_M) * t   # = MUZZLE_DIST_PX
        self.BARREL_COLL_HALF_W_PX = (self.BARREL_THICK_M + 0.08) * t / 2.0  # +8 см на эжектор

    def _calc_shot(self):
        """Всё, что зависит от калибра (размеры в мировых px, 100 px = 1 м)."""
        cal = self.cal
        cal_k = clamp((cal - _CAL.min) / (_CAL.max - _CAL.min), 0.0, 1.0)   # 0..1 по диапазону калибров

        # где находится дульный срез от центра танка (px мира, с учётом масштаба башни)
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
        self.SMOKE_STREAKS = 5 + int(cal / 20)                         # число полосок
        self.SMOKE_REACH_PX = 160.0 + 3.2 * cal                        # на сколько они расходятся
        self.SMOKE_WIDTH_PX = max(8.0, cal / 6.0)

        # взрыв снаряда и след на земле
        self.BLAST_SIZE_PX = 1.8 * cal                                 # диаметр огненного шара
        self.BLAST_TIME = 0.35 + 0.2 * cal_k
        self.BLAST_DIRT_COUNT = 6 + int(cal / 15)                      # комья земли
        self.SCORCH_RADIUS_PX = 0.9 * cal
        self.SCORCH_TIME = 4.0 + 2.0 * cal_k

    # ---------- вывод в интерфейс и в консоль ----------
    def main_stats(self):
        """Расчётные характеристики: {название: готовая строка} (порядок = порядок в панели)."""
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
            "Поворот башни": f"{self.turret_turn:.0f} °/с",
            "Урон": f"{self.damage:.0f}",
            "Пробитие": f"{self.penetration:.0f} мм",
            "Перезарядка": f"{self.reload:.2f} с",
        }

    def internal_stats(self):
        """Внутренние показатели (полезны при отладке баланса)."""
        return {
            "Удельная мощность": f"{self.pw:.1f} л.с./т",
            "Калибр / платформа": f"{self.q_gun:.2f}",
            "Бронированность": f"{self.q_arm:.2f}",
            "Длина ствола": f"{self.l_cal:.1f} кал.",
            "Инерция башни": f"{self.i_turret:.1f} т·м²",
            "Угл. разгон корпуса": f"{self.hull_alpha:.0f} °/с²",
            "Угл. разгон башни": f"{self.turret_alpha:.0f} °/с²",
        }

    def print_specs(self):
        print("=" * 50)
        print("        ХАРАКТЕРИСТИКИ ТАНКА (TankSpec)")
        print("=" * 50)
        for name, text in {**self.main_stats(), **self.internal_stats()}.items():
            print(f"{name + ':':<24}{text}")
        print("=" * 50)