"""vehicles/chassis_spec.py — расчёт шасси любой наземной техники: масса, ход, повороты,
здоровье, размеры для столкновений. Орудия и башни не знает: их масса приходит как payload_t.
Чем один тип техники отличается от другого, описывает ChassisBody."""
import math
from dataclasses import dataclass

from engine import PX_PER_M, clamp, round_to
from .chassis_params import (
    STEEL_T_PER_M3, V_CAP_KMH, PW_SCALE, V_MASS_EXP, V_MIN_KMH, V_MAX_CLAMP_KMH,
    V_AVG_BASE, V_AVG_GAIN, BACK_SPEED_K, V_BACK_CAP_KMH,
    ACCEL_K, ACCEL_MIN, ACCEL_MAX, ACCEL_TAIL_FLOOR, REVERSE_ACCEL_K, COAST_DECEL, BRAKE_DECEL,
    HULL_TURN_CAP, HULL_TURN_MIN, HULL_ALPHA_REF, HULL_ALPHA_MIN, HULL_ALPHA_MAX,
    HP_EXP, HP_STEP, TRACK_WIDTH_M, TRACK_EDGE_ZONE_M,
)
from .running_gear import RunningGear, TRACKS

def armor_masses(areas_m2, front, side, rear, size_k):
    """Массы брони лба, борта и кормы, т."""
    k2 = size_k ** 2
    return tuple(mm / 1000.0 * area * STEEL_T_PER_M3 * k2
                 for mm, area in zip((front, side, rear), areas_m2))

@dataclass(frozen=True)
class ChassisBody:
    """Описание конкретного типа шасси и его эталона."""
    fixed_t: float            # масса каркаса и гусениц, т
    engine_t_per_hp: float    # масса силовой установки на 1 л.с., т
    areas_m2: tuple           # площади лба, борта и кормы, м²
    ref_filling_t: float      # масса «начинки» эталона (без брони), т
    ref_mass_t: float         # полная масса эталона, т
    ref_power_hp: float       # мощность эталона, л.с.
    ref_armor_share: float    # доля брони в массе эталона
    hp_ref: float             # здоровье эталона
    coll_half_w_m: float      # половина ширины корпуса вместе с гусеницами, м
    coll_half_l_m: float      # половина длины гусениц, м
    coll_shift_m: float       # на сколько центр корпуса лежит позади оси башни, м
    gear: RunningGear = TRACKS  # тип ходовой части (поле с умолчанием должно быть последним)

    @property
    def ref_pw(self):
        return self.ref_power_hp / self.ref_mass_t

class ChassisSpec:
    """Входы уже должны быть в допустимых границах (это делает конкретная спецификация)."""

    def __init__(self, body, front, side, rear, power, payload_t, screen_mm=0.0):
        self.screen_mm = screen_mm
        self.body = body
        self.gear = body.gear
        self.front, self.side, self.rear = front, side, rear
        self.power = power
        self.payload_t = payload_t        # масса того, что стоит на шасси (башня, орудие), т
        self._calc_mass()
        self._calc_ratios()
        self._calc_mobility()
        self._calc_hp()
        self._calc_collision()

    def _calc_mass(self):
        b = self.body
        self.m_fixed = b.fixed_t
        self.m_engine = b.engine_t_per_hp * self.power
        self.filling = self.m_fixed + self.m_engine + self.payload_t
        self.size_k = (self.filling / b.ref_filling_t) ** (1.0 / 3.0)   # линейный размер, у эталона 1
        self.m_front, self.m_side, self.m_rear = armor_masses(
            b.areas_m2, self.front + self.screen_mm * SCREEN_MASS_K, self.side, self.rear, self.size_k)
        self.m_armor = self.m_front + self.m_side + self.m_rear
        self.mass = self.filling + self.m_armor

    def _calc_ratios(self):
        b = self.body
        self.HULL_SCALE = self.size_k
        self.pw = self.power / self.mass                              # удельная мощность
        self.s = 1.0 - math.exp(-self.pw / PW_SCALE)                  # «ходовая отдача» 0..1
        self.q_pw = self.pw / b.ref_pw                                # мощность относительно эталона
        self.q_arm = (self.m_armor / self.mass) / b.ref_armor_share   # доля брони относительно эталона

    def _calc_mobility(self):
        b = self.body
        self.v_max = clamp(V_CAP_KMH * self.s * (b.ref_mass_t / self.mass) ** V_MASS_EXP,
                           V_MIN_KMH, V_MAX_CLAMP_KMH)
        self.v_avg = self.v_max * (V_AVG_BASE + V_AVG_GAIN * self.s)
        self.v_back = min(BACK_SPEED_K * self.v_max, V_BACK_CAP_KMH)

        # момент сопротивления ~ M * size_k, момент тяги ~ P * size_k, инерция ~ M * size_k²
        self.q_turn = self.q_pw / self.size_k
        screen_k = 1.0 - SCREEN_TURN_LOSS * self.screen_mm / FRONT_SCREEN.max
        self.hull_turn = max(
            HULL_TURN_MIN,
            screen_k * HULL_TURN_CAP * (1.0 - math.exp(-math.log(2.0) * self.q_turn)))
        self.hull_alpha = clamp(HULL_ALPHA_REF * self.q_turn * screen_k, HULL_ALPHA_MIN, HULL_ALPHA_MAX)

        self.accel = clamp(ACCEL_K * self.pw, ACCEL_MIN, ACCEL_MAX)
        self.accel_back = self.accel * REVERSE_ACCEL_K
        self.decel_coast = COAST_DECEL
        self.decel_brake = BRAKE_DECEL
        self.t_avg = self.v_avg / self.accel
        self.t_max = self._time_to_speed(self.v_max - 0.5)

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
        """Сколько секунд разгоняться с места до скорости target (численно, один раз при расчёте)."""
        v, t = 0.0, 0.0
        while v < target and t < 120.0:
            v += self.accel_at(v) * dt
            t += dt
        return t

    def _calc_hp(self):
        """Здоровье растёт с массой «начинки». Броню не включаем: она защищает через правила пробития."""
        b = self.body
        raw = b.hp_ref * (self.filling / b.ref_filling_t) ** HP_EXP
        self.hp = max(HP_STEP, round_to(raw, HP_STEP))

    def _calc_collision(self):
        """Хитбокс корпуса. Всё, что торчит из корпуса (ствол), в столкновениях не участвует."""
        b = self.body
        k = self.HULL_SCALE * PX_PER_M
        self.COLLISION_HALF_W_PX = b.coll_half_w_m * k
        self.COLLISION_HALF_L_PX = b.coll_half_l_m * k
        self.COLLISION_SHIFT_PX = b.coll_shift_m * k
        self.HULL_REACH_PX = (math.hypot(self.COLLISION_HALF_W_PX, self.COLLISION_HALF_L_PX)
                              + abs(self.COLLISION_SHIFT_PX))
        self.TRACK_BAND_PX = TRACK_WIDTH_M * k          # полоса гусеницы вдоль борта
        self.TRACK_EDGE_PX = TRACK_EDGE_ZONE_M * k      # уязвимый конец гусеницы