# dutchbay_v13/finance/debt.py
"""
Debt helpers required by legacy tests and adapters:
 - blended_rate(weights, rates)
 - amortization_schedule(...)
 - apply_debt_layer(params, annual_rows)

Numbers are annual. Keep this module self-contained.
"""

from __future__ import annotations
from typing import Dict, Iterable, List, Optional

def blended_rate(weights: Dict[str, float], rates: Dict[str, float]) -> float:
    """Weighted average nominal rate. Ignores unknown keys / zero weights."""
    num = 0.0
    den = 0.0
    for k, w in (weights or {}).items():
        if not w:
            continue
        r = rates.get(k)
        if r is None:
            continue
        num += float(w) * float(r)
        den += float(w)
    return num / den if den else 0.0

def amortization_schedule(
    principal: float,
    annual_rate: float,
    tenor_years: int,
    *,
    interest_only_years: int = 0,
    amortization: str = "level",          # "level" | "sculpted"
    target_dscr: Optional[float] = None,  # when amortization == "sculpted"
    cfads: Optional[Iterable[float]] = None,  # yearly CFADS for sculpting
) -> List[Dict[str, float]]:
    """
    Annual schedule with: year, interest, principal, debt_service, balance.
    """
    P = float(principal)
    r = float(annual_rate)
    n = int(tenor_years)
    io = int(max(0, interest_only_years))
    out: List[Dict[str, float]] = []

    bal = P
    # IO years
    for y in range(1, io + 1):
        interest = bal * r
        out.append({"year": float(y), "interest": interest, "principal": 0.0,
                    "debt_service": interest, "balance": bal})

    rem = n - io
    if rem <= 0:
        return out

    if amortization.lower() == "sculpted":
        if target_dscr is None or not cfads:
            raise ValueError("sculpted amortization requires target_dscr and cfads")
        cfads_list = list(cfads)
        if len(cfads_list) < rem:
            last = cfads_list[-1] if cfads_list else 0.0
            cfads_list += [last] * (rem - len(cfads_list))
        for i in range(rem):
            year = io + i + 1
            ds = max(0.0, float(cfads_list[i]) / float(target_dscr))
            interest = bal * r
            principal = max(0.0, min(bal, ds - interest))
            bal = max(0.0, bal - principal)
            out.append({"year": float(year), "interest": interest, "principal": principal,
                        "debt_service": interest + principal, "balance": bal})
        return out

    # level (annuity) after IO
    if abs(r) < 1e-12:
        A = bal / rem
    else:
        A = bal * r / (1.0 - (1.0 + r) ** (-rem))
    for i in range(rem):
        year = io + i + 1
        interest = bal * r
        principal = max(0.0, min(bal, A - interest))
        ds = interest + principal
        bal = max(0.0, bal - principal)
        out.append({"year": float(year), "interest": interest, "principal": principal,
                    "debt_service": ds, "balance": bal})
    return out

def apply_debt_layer(params: Dict, annual_rows: List[Dict[str, float]]) -> Dict[str, object]:
    """
    Minimal debt layer used by adapters.run_irr:
    - Computes a nominal blended rate from Financing_Terms.mix and .rates floors.
    - Builds a schedule; sets equity_cf = CFADS - debt_service.
    Returns: {"annual": rows_with_debt, "dscr_min": float|None,
              "balloon_remaining": float, "debt_service": [float,...]}
    """
    terms = (params or {}).get("Financing_Terms", {}) or {}
    debt_ratio = float(terms.get("debt_ratio", 0.0) or 0.0)
    # passthrough if no debt
    if debt_ratio <= 0:
        rows = []
        for r in annual_rows:
            cf = float(r.get("cfads_usd", 0.0))
            rr = dict(r)
            rr["debt_service"] = 0.0
            rr["equity_cf"] = cf
            rows.append(rr)
        return {"annual": rows, "dscr_min": None, "balloon_remaining": 0.0, "debt_service": []}

    capex = float((params.get("capex") or {}).get("usd_total", 0.0))
    principal = capex * debt_ratio

    mix = terms.get("mix") or {}
    rates = terms.get("rates") or {}
    # Gather floors as nominal rates
    floors = {
        k.replace("_floor", ""): float(v)
        for k, v in rates.items()
        if k.endswith("_floor")
    }
    # Normalize weights if any
    wsum = sum(v for v in (mix or {}).values() if v)
    weights = {k: (v / wsum) for k, v in mix.items()} if wsum else {}
    rate = blended_rate(weights, floors) if weights else (floors.get("usd") or floors.get("lkr") or floors.get("dfi") or 0.0)

    tenor = int(terms.get("tenor_years", 10) or 10)
    io = int(terms.get("interest_only_years", 0) or 0)
    amort = (terms.get("amortization") or "level").lower()

    cfads = [float(r.get("cfads_usd", 0.0)) for r in annual_rows]
    target_dscr = terms.get("dscr_target")
    sched = amortization_schedule(
        principal, rate, tenor_years=tenor,
        interest_only_years=io, amortization=amort,
        target_dscr=float(target_dscr) if target_dscr else None,
        cfads=cfads
    )

    # decorate annual rows with debt_service + equity_cf
    rows: List[Dict[str, float]] = []
    by_year = {int(s["year"]): s for s in sched}
    dscr_vals: List[float] = []
    for r in annual_rows:
        y = int(r.get("year", 0))
        cf = float(r.get("cfads_usd", 0.0))
        ds = float(by_year.get(y, {}).get("debt_service", 0.0))
        row = dict(r)
        row["debt_service"] = ds
        row["equity_cf"] = cf - ds
        rows.append(row)
        if ds > 0:
            dscr_vals.append(cf / ds if ds else None)

    dscr_min = min(d for d in dscr_vals) if dscr_vals else None
    balloon_remaining = float(sched[-1]["balance"]) if sched else 0.0
    return {
        "annual": rows,
        "dscr_min": dscr_min,
        "balloon_remaining": balloon_remaining,
        "debt_service": [float(s["debt_service"]) for s in sched],
    }

__all__ = ["blended_rate", "amortization_schedule", "apply_debt_layer"]

