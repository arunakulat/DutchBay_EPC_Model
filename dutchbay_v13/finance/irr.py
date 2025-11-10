from typing import Sequence
from math import isfinite
from scipy.optimize import brentq


def npv(rate: float, cashflows: Sequence[float]) -> float:
    total = 0.0
    for t, c in enumerate(cashflows):
        total += c / ((1.0 + rate) ** t)
    return total


def irr(cashflows: Sequence[float]) -> float:
    if not cashflows or all(c == 0 for c in cashflows):
        return 0.0
    # search for a sign-changing bracket
    xs = [-0.999999, 0.0] + [i / 10 for i in range(1, 201)]  # 0.1 .. 20.0
    prev_x = xs[0]
    prev_f = npv(prev_x, cashflows)
    for x in xs[1:]:
        f = npv(x, cashflows)
        if (
            isfinite(prev_f)
            and isfinite(f)
            and ((prev_f == 0) or (f == 0) or ((prev_f < 0) != (f < 0)))
        ):
            a, b = (prev_x, x) if prev_x < x else (x, prev_x)
            return brentq(lambda r: npv(r, cashflows), a, b, maxiter=100)
        prev_x, prev_f = x, f
    return 0.0
