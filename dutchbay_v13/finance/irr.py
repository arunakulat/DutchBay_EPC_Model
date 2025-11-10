from __future__ import annotations
from typing import Iterable, Optional
import numpy as np
from scipy.optimize import brentq, newton

def npv(rate: float, cash_flows: Iterable[float]) -> float:
    cf = np.asarray(list(cash_flows), dtype=float)
    return float(np.sum(cf / (1.0 + rate) ** np.arange(cf.size)))

def _sign_change_exists(cf: np.ndarray) -> bool:
    return np.any(cf[:-1] * cf[1:] < 0)

def irr(cash_flows: Iterable[float], guess: float = 0.10, xtol: float = 1e-8, maxiter: int = 200) -> Optional[float]:
    cf = np.asarray(list(cash_flows), dtype=float)
    if cf.size < 2 or not _sign_change_exists(cf):
        return None
    try:
        return float(brentq(lambda r: npv(r, cf), -0.90, 5.00, xtol=xtol, maxiter=maxiter))
    except Exception:
        pass
    try:
        def d_npv(r: float) -> float:
            k = np.arange(cf.size)
            return float(-np.sum(k * cf / (1.0 + r) ** (k + 1)))
        r = newton(lambda r: npv(r, cf), guess, fprime=d_npv, tol=xtol, maxiter=maxiter)
        return float(r) if -0.90 < r < 5.00 else None
    except Exception:
        return None