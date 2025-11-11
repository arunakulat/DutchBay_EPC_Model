# dutchbay_v13/adapters.py
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

try:
    import numpy_financial as npf  # type: ignore
except Exception:  # pragma: no cover
    npf = None

# Debt engine (pure logic; no policy here)
from dutchbay_v13.finance.debt import apply_debt_layer


# ------------------------------
# Small helpers (no policy here)
# ------------------------------
def _get(d: Dict[str, Any], path: Iterable[str], default: Any = None) -> Any:
    """Safe nested get: _get(p, ['capex','usd_total'])."""
    cur: Any = d
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def _as_float(v: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        return float(v) if v is not None else default
    except Exception:
        return default


def _capacity_mw(p: Dict[str, Any]) -> float:
    # prefer namespaced; fall back if legacy present. Avoid embedding a policy default.
    val = _get(p, ["project", "capacity_mw"])
    if val is None:
        val = p.get("capacity_mw")
    return float(val) if val is not None else 0.0


def _lifetime_years(p: Dict[str, Any]) -> int:
    val = _get(p, ["project", "timeline", "lifetime_years"])
    if val is None:
        val = p.get("lifetime_years")
    # choose a neutral default (20) only to avoid crashes if user omitted it;
    # strict validation should normally require this upstream.
    return int(_as_float(val, 20) or 20)


def _capacity_factor(p: Dict[str, Any]) -> Optional[float]:
    # Accept either a direct capacity_factor, or compose via availability/loss if provided
    cf = _get(p, ["project", "capacity_factor"])
    if cf is not None:
        return float(cf)
    avail = _as_float(p.get("availability_pct"))
    loss = _as_float(p.get("loss_factor"))
    if avail is not None and loss is not None:
        return max(0.0, min(1.0, (avail / 100.0) * (1.0 - loss)))
    return None


def _degradation(p: Dict[str, Any]) -> float:
    # fractional per-year degradation if provided; else 0.0
    # sources: project.degradation (0..1) or legacy Technical.degradation
    val = _get(p, ["project", "degradation"])
    if val is None:
        val = _get(p, ["Technical", "degradation"])
    return float(val) if val is not None else 0.0


def _capex_usd(p: Dict[str, Any]) -> float:
    """
    Read CAPEX from YAML only.
    Supported:
      capex.usd_total
      OR capex.usd_per_mw * project.capacity_mw
    No baked floors here; let validation enforce bounds.
    """
    total = _get(p, ["capex", "usd_total"])
    if total is not None:
        return float(total)
    per_mw = _get(p, ["capex", "usd_per_mw"])
    cap = _capacity_mw(p)
    if per_mw is not None and cap > 0:
        return float(per_mw) * cap
    return 0.0


def _opex_for_year_usd(p: Dict[str, Any], kwh_year: float, fx_lkr_per_usd: float) -> float:
    """
    Compute OPEX USD for a year from YAML only:
      opex.usd_per_year
      opex.lkr_per_year (converted by FX)
      opex.usd_per_mwh  (applied to energy)
      opex.lkr_per_mwh  (converted by FX)
    If multiple are present, they sum.
    """
    opex_usd = 0.0

    usd_py = _get(p, ["opex", "usd_per_year"])
    if usd_py is not None:
        opex_usd += float(usd_py)

    lkr_py = _get(p, ["opex", "lkr_per_year"])
    if lkr_py is not None and fx_lkr_per_usd:
        opex_usd += float(lkr_py) / float(fx_lkr_per_usd)

    usd_pmwh = _get(p, ["opex", "usd_per_mwh"])
    if usd_pmwh is not None and kwh_year > 0:
        opex_usd += float(usd_pmwh) * (kwh_year / 1_000.0)

    lkr_pmwh = _get(p, ["opex", "lkr_per_mwh"])
    if lkr_pmwh is not None and kwh_year > 0 and fx_lkr_per_usd:
        opex_usd += (float(lkr_pmwh) / float(fx_lkr_per_usd)) * (kwh_year / 1_000.0)

    return opex_usd


def _fx_curve_for_years(p: Dict[str, Any], years: int) -> List[float]:
    """
    Return LKR/USD for each operating year.
    Sources:
      fx.curve_lkr_per_usd (explicit array) OR
      fx.start_lkr_per_usd + fx.annual_depr (compounding)
    """
    explicit = _get(p, ["fx", "curve_lkr_per_usd"])
    if isinstance(explicit, list) and explicit:
        arr = [float(x) for x in explicit]
        if len(arr) >= years:
            return arr[:years]
        return arr + [arr[-1]] * (years - len(arr))

    start = _as_float(_get(p, ["fx", "start_lkr_per_usd"]), 0.0) or 0.0
    depr = _as_float(_get(p, ["fx", "annual_depr"]), 0.0) or 0.0
    path: List[float] = []
    cur = float(start) if start > 0 else 0.0
    for _ in range(max(1, years)):
        path.append(cur if cur > 0 else 0.0)
        if cur > 0:
            cur *= (1.0 + float(depr))
    return path


def _tariff_usd_per_kwh_for_year(p: Dict[str, Any], fx_year: float) -> float:
    """
    If tariff_usd_per_kwh exists, use it as-is.
    Else if tariff_lkr_per_kwh exists, convert by FX for that year.
    """
    usd = _get(p, ["tariff", "usd_per_kwh"])
    if usd is None:
        # legacy flat key
        usd = p.get("tariff_usd_per_kwh")
    if usd is not None:
        return float(usd)

    lkr = _get(p, ["tariff", "lkr_per_kwh"])
    if lkr is None:
        # legacy flat key
        lkr = p.get("tariff_lkr_per_kwh")
    if lkr is not None and fx_year:
        return float(lkr) / float(fx_year)

    return 0.0


# ------------------------------
# Public adapter(s)
# ------------------------------
def run_irr_demo(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    High-level adapter:
      1) Build operating-year series for energy, revenue (USD), CFADS (USD).
      2) Hand CFADS + revenue + params to the debt layer (which handles DSCR sculpt/annuity/DSRA/guarantee).
      3) Compute equity IRR on the returned equity cashflows (which MUST include t0).
    No embedded policy: all floors/caps/rates/tenors live in YAML + schema.

    Returns:
      {
        'equity_irr': float,
        'project_irr': float,   # equals equity_irr in this simplified adapter (project IRR can be added later)
        'npv_12': 0.0,          # placeholder for future
        'dscr_min': float,
        'annual': [{'year': i, 'equity_cf': float, 'dscr': float|None}, ...],
      }
    """
    years = _lifetime_years(params)
    cap_mw = _capacity_mw(params)
    if years <= 0 or cap_mw <= 0:
        # Soft-fail to a trivial result; strict mode should catch upstream with validation.
        return {
            "equity_irr": 0.0,
            "project_irr": 0.0,
            "npv_12": 0.0,
            "dscr_min": 0.0,
            "annual": [{"year": i + 1, "equity_cf": 0.0, "dscr": None} for i in range(max(0, years))],
        }

    capex_usd = _capex_usd(params)
    degr = _degradation(params)
    fx = _fx_curve_for_years(params, years)

    # Energy (kWh/year) with optional degradation
    cf = _capacity_factor(params)
    if cf is None:
        # If user omitted CF, assume 0 (validation should enforce CF bounds in strict mode)
        cf = 0.0
    kwh_base = cap_mw * 8760.0 * float(cf)

    kwh_years: List[float] = []
    for y in range(years):
        # apply linear multiplicative degradation per year y (0-indexed)
        kwh = kwh_base * ((1.0 - degr) ** y)
        kwh_years.append(max(0.0, kwh))

    # Revenue & OPEX (USD), then CFADS
    revenue_usd: List[float] = []
    cfads_usd: List[float] = []
    for y in range(years):
        t_usd = _tariff_usd_per_kwh_for_year(params, fx[y] if y < len(fx) else 0.0)
        rev = t_usd * kwh_years[y]
        opx = _opex_for_year_usd(params, kwh_years[y], fx[y] if y < len(fx) else 0.0)
        revenue_usd.append(rev)
        cfads_usd.append(rev - opx)

    # Debt layer (handles equity vs debt split, DSCR sculpting, DSRA/guarantee, balloon checks)
    debt_result = apply_debt_layer(
        cfads=cfads_usd,
        revenue=revenue_usd,
        params=params,
        capex_usd=capex_usd,
    )

    equity_cf_series: List[float] = debt_result.get("equity_cf", [])  # must include t0
    dscr_series: List[Optional[float]] = debt_result.get("dscr", [None] * years)
    dscr_min: float = float(debt_result.get("dscr_min", 0.0))

    # IRR on equity
    if npf is None or not equity_cf_series:
        equity_irr = 0.0
    else:
        try:
            equity_irr = float(npf.irr(equity_cf_series))
        except Exception:
            equity_irr = 0.0

    # Project IRR placeholder (you can add a separate project cashflow later)
    project_irr = equity_irr

    annual_rows = []
    # Equity CF series includes t0; align years 1..N to equity_cf_series[1:]
    for i in range(years):
        e_cf = equity_cf_series[i + 1] if i + 1 < len(equity_cf_series) else 0.0
        dsc = dscr_series[i] if i < len(dscr_series) else None
        annual_rows.append({"year": i + 1, "equity_cf": e_cf, "dscr": dsc})

    return {
        "equity_irr": equity_irr,
        "project_irr": project_irr,
        "npv_12": 0.0,
        "dscr_min": dscr_min,
        "annual": annual_rows,
    }

    