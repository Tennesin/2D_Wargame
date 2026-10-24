"""game/background/paths.py — траектории для событий фона. Точки задаются долями экрана:
(0, 0) левый верхний угол, (1, 1) правый нижний, за экраном значения меньше 0 или больше 1."""
import math

def _lerp(a, b, t):
    return a + (b - a) * t

def line(a, b, n=2):
    """Прямая из n точек."""
    n = max(2, n)
    return [(_lerp(a[0], b[0], i / (n - 1)), _lerp(a[1], b[1], i / (n - 1))) for i in range(n)]

def wave(a, b, amp=0.12, waves=1.5, n=28, phase=0.0):
    """Кривая из a в b: прямая плюс синусоида поперёк. amp в долях экрана, waves сколько волн на пути.
    На концах отклонение гаснет, поэтому старт и финиш лежат ровно в a и b."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    ln = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / ln, dx / ln
    pts = []
    for i in range(n + 1):
        t = i / n
        env = min(1.0, 4.0 * t, 4.0 * (1.0 - t))
        off = amp * env * math.sin(math.tau * waves * t + phase)
        pts.append((_lerp(a[0], b[0], t) + nx * off, _lerp(a[1], b[1], t) + ny * off))
    return pts

def bezier(p0, p1, p2, p3, n=24):
    """Кубическая кривая Безье: p0 старт, p3 финиш, p1 и p2 направляют изгиб."""
    pts = []
    for i in range(n + 1):
        t = i / n
        u = 1.0 - t
        pts.append((u ** 3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t ** 3 * p3[0],
                    u ** 3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t ** 3 * p3[1]))
    return pts