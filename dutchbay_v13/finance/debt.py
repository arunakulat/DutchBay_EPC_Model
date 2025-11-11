"""
Debt planning module for dutchbay_v13.finance.debt

- Reads tranche mix and rate terms from `params` (YAML-driven; no policy defaults baked in).
- Builds a per-tranche schedule (LKR, USD commercial, DFI) under either:
    * sculpted: total Debt Service ≈ CFADS / dscr_target (post-grace), with principal split pro-rata by OS principal;
    * annuity: per-tranche annuity over amortization years.
- Handles interest-only years (interest_only_years).
- Supports DSRA funding/top-ups/releases OR a receivables guarantee (mutually exclusive by design).
- Returns a dictionary with dscr series/min, per-year debt service, balloon and adjustments to equity cash flows.
"""
from __future__ import annotations

from typing import Dict, Any, List, Optional, Tuple
import math


# -------------------------
# Local helpers (no policy)
# -------------------------
def _get(d: Dict[str, Any], path: List[str], default: Any = None) -> Any:
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
    ns = _get(p, ["project", "capacity_mw"])
    legacy = p.get("capacity_mw")
    return _as_float(ns, _as_float(legacy, 1.0)) or 1.0


def _lifetime_years(p: Dict[str, Any]) -> int:
    ns = _get(p, ["project", "timeline", "lifetime_years"])
    legacy = p.get("lifetime_years")
    return int(_as_float(ns, _as_float(legacy, 20)) or 20)


def _capex_usd(p: Dict[str, Any]) -> float:
    total = _get(p, ["capex", "usd_total"])
    if total is not None:
        return float(total)
    per_mw = _as_float(_get(p, ["capex", "usd_per_mw"]), 1_000_000.0) or 1_000_000.0
    floor_pm = _as_float(_get(p, ["capex", "floor_per_mw"]), 1_000_000.0) or 1_000_000.0
    return max(per_mw, floor_pm) * _capacity_mw(p)


def _pmt(rate: float, nper: int, pv: float) -> float:
    # classic annuity payment (positive)
    if rate == 0:
        return pv / nper
    return pv * (rate * (1 + rate) ** nper) / ((1 + rate) ** nper - 1)


# -------------------------
# Tranche and rate shaping
# -------------------------
class Tranche:
    __slots__ = ("name", "rate", "principal", "years_io")

    def __init__(self, name: str, rate: float, principal: float, years_io: int):
        self.name = name
        self.rate = float(rate)
        self.principal = float(principal)
        self.years_io = int(years_io)


def _solve_mix(p: Dict[str, Any], debt_total: float) -> Dict[str, Tranche]:
    mix_lkr_max = _as_float(_get(p, ["financing", "mix", "lkr_max"]), None)
    mix_dfi_max = _as_float(_get(p, ["financing", "mix", "dfi_max"]), None)
    mix_usd_min = _as_float(_get(p, ["financing", "mix", "usd_commercial_min"]), 0.0) or 0.0

    # floors and/or explicit nominals
    r_lkr = _as_float(_get(p, ["financing", "rates", "lkr_nominal"]),
                      _as_float(_get(p, ["financing", "rates", "lkr_floor"]), 0.0))
    r_usd = _as_float(_get(p, ["financing", "rates", "usd_nominal"]),
                      _as_float(_get(p, ["financing", "rates", "usd_floor"]), 0.0))
    r_dfi = _as_float(_get(p, ["financing", "rates", "dfi_nominal"]),
                      _as_float(_get(p, ["financing", "rates", "dfi_floor"]), 0.0))

    # initial caps
    lkr_amt = min(debt_total * (mix_lkr_max or 0.0), debt_total)
    dfi_amt = min(debt_total * (mix_dfi_max or 0.0), max(0.0, debt_total - lkr_amt))
    usd_amt = max(0.0, debt_total - lkr_amt - dfi_amt)

    # Enforce a minimum on USD commercial if given (pull from LKR first, then DFI)
    min_usd_amt = debt_total * mix_usd_min
    if usd_amt < min_usd_amt:
        need = min_usd_amt - usd_amt
        pull_lkr = min(need, lkr_amt)
        lkr_amt -= pull_lkr
        need -= pull_lkr
        if need > 0:
            pull_dfi = min(need, dfi_amt)
            dfi_amt -= pull_dfi
            need -= pull_dfi
        usd_amt = debt_total - lkr_amt - dfi_amt

    years_io = int(_as_float(_get(p, ["financing", "interest_only_years"]), 0) or 0)
    return {
        "LKR": Tranche("LKR", r_lkr or 0.0, lkr_amt, years_io),
        "USD": Tranche("USD", r_usd or 0.0, usd_amt, years_io),
        "DFI": Tranche("DFI", r_dfi or 0.0, dfi_amt, years_io),
    }


# -------------------------
# Schedule constructors
# -------------------------
def _annuity_schedule(tr: Tranche, amort_years: int) -> List[Tuple[float, float, float]]:
    """Return list of (interest, principal, total_service) per year for one tranche."""
    n = amort_years
    bal = tr.principal
    rows: List[Tuple[float, float, float]] = []
    # interest-only years
    for _ in range(tr.years_io):
        interest = bal * tr.rate
        principal = 0.0
        rows.append((interest, principal, interest))
    # amortization
    if n > 0:
        pmt = _pmt(tr.rate, n, bal)
        for _ in range(n):
            interest = bal * tr.rate
            principal = max(0.0, pmt - interest)
            bal = max(0.0, bal - principal)
            rows.append((interest, principal, interest + principal))
    return rows


def _sculpted_schedule(tranches: Dict[str, Tranche], amort_years: int, cfads: List[float], dscr_target: float) -> Dict[str, List[Tuple[float, float, float]]]:
    """
    Sculpt across TOTAL debt service to match CFADS / target.
    Allocate principal pro-rata by outstanding principal across tranches each year.
    """
    obals = {k: tr.principal for k, tr in tranches.items()}
    schedules = {k: [] for k in tranches.keys()}

    io_years = max(tr.years_io for tr in tranches.values())
    year_index = 0

    # IO period: interest only
    for _ in range(io_years):
        for k, tr in tranches.items():
            bal = obals[k]
            interest = bal * tr.rate
            schedules[k].append((interest, 0.0, interest))
        year_index += 1

    # Amortization period
    for _ in range(amort_years):
        cf = cfads[year_index] if year_index < len(cfads) else (cfads[-1] if cfads else 0.0)
        target_service = max(0.0, cf / dscr_target)

        interest_map = {k: obals[k] * tranches[k].rate for k in tranches.keys()}
        total_interest = sum(interest_map.values())
        principal_total = max(0.0, target_service - total_interest)

        total_bal = sum(obals.values()) or 1.0
        for k, tr in tranches.items():
            bal = obals[k]
            prorata = bal / total_bal if total_bal > 0 else 0.0
            principal_k = min(bal, principal_total * prorata)
            interest_k = interest_map[k]
            obals[k] = max(0.0, bal - principal_k)
            schedules[k].append((interest_k, principal_k, interest_k + principal_k))
        year_index += 1

    return schedules


# -------------------------
# Main entry
# -------------------------
def apply_debt_layer(params: Dict[str, Any], annual_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Add debt to an equity-only cashflow. `annual_rows` should include CFADS proxy under one of:
    - 'equity_cf' (net operating cash flow used earlier),
    - OR 'cfads_usd' (if upstream already computed explicit CFADS).

    Returns structure includes DSCR series/min, per-year debt service, balloon and adjustments that
    adapters.py will subtract from equity series.
    """
    lifetime = _lifetime_years(params)
    debt_ratio = _as_float(_get(params, ["financing", "debt_ratio"]), None)
    tenor_years = int(_as_float(_get(params, ["financing", "tenor_years"]), 0) or 0)
    amortization = (_get(params, ["financing", "amortization"], "sculpted") or "sculpted").lower()
    dscr_target = _as_float(_get(params, ["financing", "dscr_target"]), None)

    if not debt_ratio or debt_ratio <= 0.0:
        return {
            "mode": "equity_only",
            "dscr_series": [None] * lifetime,
            "dscr_min": None,
            "balloon_remaining": 0.0,
            "debt_service": [0.0] * lifetime,
            "principal_series": [0.0] * lifetime,
            "interest_series": [0.0] * lifetime,
            "dsra_cashflows": [0.0] * lifetime,
            "fees_cashflows": [0.0] * lifetime,
            "notes": ["No debt terms present; equity-only path."],
        }

    capex = _capex_usd(params)
    debt_total = capex * debt_ratio
    equity_total = capex - debt_total

    # CFADS series (use equity_cf if cfads not provided)
    cfads: List[float] = []
    for row in annual_rows[:lifetime]:
        v = row.get("cfads_usd")
        if v is None:
            v = row.get("equity_cf", 0.0)
        cfads.append(float(v or 0.0))
    if len(cfads) < lifetime:
        cfads += [cfads[-1] if cfads else 0.0] * (lifetime - len(cfads))

    # Tranche mix
    tr_map = _solve_mix(params, debt_total)

    # Amortization window after IO years
    io_years = max(tr.years_io for tr in tr_map.values())
    amort_years = max(0, tenor_years - io_years)

    # Build schedules
    if amortization.startswith("sculp") and dscr_target:
        sch_map = _sculpted_schedule(tr_map, amort_years, cfads, float(dscr_target))
    else:
        sch_map = {k: _annuity_schedule(tr, amort_years) for k, tr in tr_map.items()}

    # Aggregate
    max_len = max(len(v) for v in sch_map.values()) if sch_map else 0
    total_years = max(lifetime, max_len)
    interest_series = [0.0] * total_years
    principal_series = [0.0] * total_years
    for rows in sch_map.values():
        for y, (i, p, _s) in enumerate(rows):
            if y < total_years:
                interest_series[y] += i
                principal_series[y] += p
    debt_service = [i + p for i, p in zip(interest_series, principal_series)]

    # DSRA or receivables guarantee
    dsra_m = int(_as_float(_get(params, ["financing", "reserves", "dsra_months"]), 0) or 0)
    recv_m = int(_as_float(_get(params, ["financing", "reserves", "receivables_guarantee_months"]), 0) or 0)
    dsra_cash = [0.0] * total_years
    fees_cash = [0.0] * total_years

    # Optional receivables guarantee fee as % of revenue (either financing.guarantee_revenue_pct or fees.guarantee_pct_of_revenue)
    fee_pct = _as_float(_get(params, ["financing", "guarantee_revenue_pct"]), None)
    fee_pct = _as_float(_get(params, ["financing", "fees", "guarantee_pct_of_revenue"]), fee_pct)
    revenues = [float(row.get("revenue_usd", 0.0) or 0.0) for row in annual_rows[:total_years]]

    if recv_m > 0:
        # alternative to DSRA; charge optional fee
        if fee_pct and any(revenues):
            for y in range(min(total_years, len(revenues))):
                fees_cash[y] += revenues[y] * float(fee_pct)
    elif dsra_m > 0 and total_years > 0:
        monthly = [s / 12.0 for s in debt_service]
        target_buf = [sum(monthly[y:y + dsra_m]) for y in range(total_years)]
        buf = 0.0
        for y in range(total_years):
            need = target_buf[y]
            delta = need - buf
            if abs(delta) < 1e-9:
                pass
            elif delta > 0:
                dsra_cash[y] -= delta  # funding (cash out)
                buf += delta
            else:
                dsra_cash[y] += (-delta)  # release (cash in)
                buf += delta

    # DSCR series
    dscr_series: List[Optional[float]] = []
    for y in range(total_years):
        svc = debt_service[y]
        cf = cfads[y] if y < len(cfads) else (cfads[-1] if cfads else 0.0)
        dscr_series.append((cf / svc) if svc > 0 else None)
    dscr_min = min([x for x in dscr_series if x is not None], default=None)

    # Balloon at maturity
    total_principal_paid = sum(principal_series)
    balloon_remaining = max(0.0, debt_total - total_principal_paid)

    # Adjustments for equity cash flow
    # (interest + principal + dsra funding − fees; releases add back)
    adjustments = [-(debt_service[y]) + dsra_cash[y] - fees_cash[y] for y in range(total_years)]

    notes: List[str] = []
    if balloon_remaining > 1e-6:
        notes.append(f"Balloon remains at maturity: {balloon_remaining:,.2f} USD")
    min_dscr_covenant = _as_float(_get(params, ["financing", "min_dscr"]), None)
    if dscr_min is not None and min_dscr_covenant is not None and dscr_min + 1e-9 < float(min_dscr_covenant):
        notes.append(f"DSCR min {dscr_min:.2f} below minimum covenant.")

    return {
        "mode": "debt_applied",
        "debt_total": debt_total,
        "equity_total": equity_total,
        "interest_series": interest_series[:lifetime],
        "principal_series": principal_series[:lifetime],
        "debt_service": debt_service[:lifetime],
        "dscr_series": dscr_series[:lifetime],
        "dscr_min": dscr_min,
        "dsra_cashflows": dsra_cash[:lifetime],
        "fees_cashflows": fees_cash[:lifetime],
        "balloon_remaining": balloon_remaining,
        "adjustments": adjustments[:lifetime],
        "notes": notes,
    }

    