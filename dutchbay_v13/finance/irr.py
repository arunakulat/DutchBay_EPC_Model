# dutchbay_v13/finance/irr.py
from __future__ import annotations

from typing import Iterable, List, Optional

# Try numpy-financial if available; otherwise use a robust bracketed solver.
try:
    import numpy_financial as npf  # type: ignore
except Exception:  # pragma: no cover
    npf = None  # will fall back to local IRR

# ---------- NPV ----------
def npv(rate: float, cashflows: Iterable[float]) -> float:
    """
    Classic discounted cash flow:
        NPV(r) = sum_{t=0..N} CF[t] / (1+r)^t
    """
    r = float(rate)
    if r <= -1.0:
        # Avoid division by zero / negatives beyond -100%
        r = -0.999999
    total = 0.0
    for t, cf in enumerate(cashflows):
        total += float(cf) / ((1.0 + r) ** t)
    return total


# ---------- IRR (periodic) ----------
def _irr_local(cashflows: List[float]) -> Optional[float]:
    """
    Bracketed bisection on NPV(r)=0. Returns None if sign never changes.
    Search domain: [-0.9999, 5.0] (i.e., -99.99% to 500%).
    """
    if not cashflows:
        return None

    # Quick degenerate checks
    if all(abs(cf) < 1e-12 for cf in cashflows):
        return 0.0

    lo, hi = -0.9999, 5.0
    f_lo = npv(lo, cashflows)
    f_hi = npv(hi, cashflows)

    # If no sign change, IRR is not bracketed (could be multiple roots as well)
    if f_lo == 0.0:
        return lo
    if f_hi == 0.0:
        return hi
    if (f_lo > 0 and f_hi > 0) or (f_lo < 0 and f_hi < 0):
        return None

    # Bisection
    for _ in range(200):
        mid = (lo + hi) / 2.0
        f_mid = npv(mid, cashflows)
        if abs(f_mid) < 1e-10:
            return mid
        # keep the sub-interval where sign changes
        if (f_lo < 0 and f_mid > 0) or (f_lo > 0 and f_mid < 0):
            hi, f_hi = mid, f_mid
        else:
            lo, f_lo = mid, f_mid
    return (lo + hi) / 2.0


def irr(cashflows: Iterable[float]) -> Optional[float]:
    """
    Periodic IRR with numpy-financial if present; else fallback to local solver.
    Returns a decimal rate (e.g., 0.18 = 18%).
    """
    cfs = [float(x) for x in cashflows]
    if npf is not None:
        try:
            val = float(npf.irr(cfs))  # type: ignore[attr-defined]
            # Some numpy-financial versions return nan when not bracketed
            if val != val:  # NaN check
                return None
            return val
        except Exception:
            pass
    return _irr_local(cfs)


# ---------- Helpers to assemble CF series ----------
def build_project_cashflows(capex_t0_usd: float, annual_rows: List[dict]) -> List[float]:
    """
    Project CF (before financing): [-CAPEX] + [CFADS each year]
    Assumes each annual row contains 'cfads_usd'.
    """
    out: List[float] = [float(capex_t0_usd)]
    out.extend(float(row.get("cfads_usd", 0.0)) for row in annual_rows)
    return out


def build_equity_cashflows(
    equity_t0_usd: float,
    annual_rows: List[dict],
    balloon_remaining: float = 0.0,
) -> List[float]:
    """
    Equity CF: [-Equity injection at t0] + [equity_cf each year].
    If a residual balloon is reported (not already in debt service),
    subtract it in the last period to keep accounting conservative.
    """
    out: List[float] = [float(equity_t0_usd)]
    out.extend(float(row.get("equity_cf", 0.0)) for row in annual_rows)
    b = float(balloon_remaining or 0.0)
    if b > 1e-9 and len(out) > 1:
        out[-1] -= b
    return out

    