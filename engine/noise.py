"""noise.py — детерминированные хеши и плавный шум. Без pygame и без знания о мире."""
import math

from .mathx import lerp

def hash_int(ix, iy, seed):
    """Детерминированный целочисленный хеш трёх чисел (32 бита)."""
    h = (ix * 374761393 + iy * 668265263 + seed * 144269504) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    return h ^ (h >> 16)

def hash_float(ix, iy, seed):
    """То же, но результат в диапазоне 0..1."""
    return hash_int(ix, iy, seed) / 4294967295.0

def value_noise(x, y, seed):
    """Плавный шум 0..1: хеши в углах клетки, сглаженная интерполяция."""
    x0 = math.floor(x)
    y0 = math.floor(y)
    fx = x - x0
    fy = y - y0
    fx = fx * fx * (3.0 - 2.0 * fx)
    fy = fy * fy * (3.0 - 2.0 * fy)
    x0 = int(x0)
    y0 = int(y0)
    v00 = hash_float(x0, y0, seed)
    v10 = hash_float(x0 + 1, y0, seed)
    v01 = hash_float(x0, y0 + 1, seed)
    v11 = hash_float(x0 + 1, y0 + 1, seed)
    return lerp(lerp(v00, v10, fx), lerp(v01, v11, fx), fy)