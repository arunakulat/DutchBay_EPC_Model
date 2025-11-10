from __future__ import annotations
from typing import Dict


def irr_bisection(
    cfs: list[float],
    lo: float = -0.99,
    hi: float = 1.5,
    tol: float = 1e-6,
    max_iter: int = 200,
) -> float:
    """Simple IRR via bisection. Returns rate (per period)."""

    def npv(r: float) -> float:
        return sum(cf / ((1 + r) ** t) for t, cf in enumerate(cfs))

    f_lo, f_hi = npv(lo), npv(hi)
    # If signs are same, push hi upwards a bit
    if f_lo * f_hi > 0:
        # fallback: try a grid
        grid = [-0.9, -0.5, 0.0, 0.2, 0.5, 1.0, 1.5]
        vals = [npv(g) for g in grid]
        # find sign change
        for j in range(len(grid) - 1):
            if vals[j] == 0:
                return grid[j]
            if vals[j] * vals[j + 1] < 0:
                lo, hi = grid[j], grid[j + 1]
                break
        else:
            # As a last resort, return 0 if monotonic
            return 0.0
    for _ in range(max_iter):
        mid = (lo + hi) / 2
        f_mid = npv(mid)
        if abs(f_mid) < tol:
            return mid
        if f_lo * f_mid < 0:
            hi = mid
            f_hi = f_mid
        else:
            lo = mid
            f_lo = f_mid
    return (lo + hi) / 2


def npv(rate: float, cfs: list[float]) -> float:
    return sum(cf / ((1 + rate) ** t) for t, cf in enumerate(cfs))


def _fx_path(
    year_idx: int,
    fx_initial: float,
    fx_depr: float,
    cod_year: int,
    start_year: int = 2025,
) -> float:
    """Compute FX for a given project year (1-indexed). FX starts at `fx_initial` in start_year (Nov 2025)
    and depreciates at `fx_depr` compounded annually to COD (Nov 2029), and continues thereafter at same rate.
    """
    # Map project year to calendar year for simplicity: assume year 1 = start_year+1 (2026) operations?
    # We'll treat depreciation from 2025 to 2029 for COD, then continue.
    # For modeling simplicity, apply compounded depreciation per year index (year 1 corresponds to first operating year).
    # Starting FX is fx_initial at 2025; after n years: fx = fx_initial * (1+fx_depr) ** n
    n = year_idx + 0  # approximate continuous depreciation
    return fx_initial * ((1.0 + fx_depr) ** n)


def _production_mwh(params: Dict, year_idx: int) -> float:
    nameplate_mw = params["nameplate_mw"]
    cf = params["capacity_factor"]
    deg = params["degradation"]
    hours = params["hours_per_year"]
    eff_cf = cf * ((1 - deg) ** max(year_idx - 1, 0))
    return nameplate_mw * hours * eff_cf / 1e3  # MWh


def _revenue_usd(params: Dict, year_idx: int, prod_mwh: float) -> float:
    lkr_per_kwh = params["tariff_lkr_per_kwh"]
    fx = _fx_path(year_idx, params["fx_initial"], params["fx_depr"], params["cod_year"])
    lkr_revenue = prod_mwh * 1000.0 * lkr_per_kwh  # kWh * LKR/kWh
    usd_revenue = lkr_revenue / fx
    return usd_revenue


def _opex_usd(params: Dict, prod_mwh: float) -> float:
    return params["opex_usd_per_mwh"] * prod_mwh


def _blended_cost_of_debt(params: Dict) -> float:
    usd = params["usd_debt_ratio"]
    lkr = 1.0 - usd
    usd_rate = (
        params["usd_dfi_pct"] * params["usd_dfi_rate"]
        + (1.0 - params["usd_dfi_pct"]) * params["usd_mkt_rate"]
    )
    return usd * usd_rate + lkr * params["lkr_rate"]


def _debt_service_schedule(params: Dict, total_debt: float, years: int) -> list[dict]:
    """Front-loaded principal: flat principal in first 4 amort years for 'principal_pct_1_4'=0.5 and rest thereafter.
    Simpler: grace then equal principal across remaining years."""
    g = params["grace_years"]
    tenor = params["tenor_years"]
    r = _blended_cost_of_debt(params)
    sched = []
    opening = total_debt
    amort_years = max(0, min(tenor, years) - g)
    principal_per_year = (total_debt / amort_years) if amort_years > 0 else 0.0
    for y in range(1, years + 1):
        interest = opening * r
        principal = 0.0
        if y > g and y <= g + amort_years and opening > 0:
            principal = min(opening, principal_per_year)
        closing = max(0.0, opening - principal)
        ds = interest + principal
        sched.append(
            {
                "year": y,
                "opening": opening,
                "interest": interest,
                "principal": principal,
                "closing": closing,
                "debt_service": ds,
            }
        )
        opening = closing
    return sched


def _tax_calc(params: Dict, ebit: float, interest: float, year_idx: int) -> float:
    # Sri Lanka tax on taxable income derived from accounting net profit; simplified here:
    # taxable_income = ebit - interest (ignoring complex add-backs/allowances).
    # Apply holiday by setting tax to 0 for 'tax_holiday_years' from COD.
    tax_rate = params["corp_tax_rate"]
    if year_idx <= params["tax_holiday_years"]:
        return 0.0
    taxable = max(0.0, ebit - interest)
    return taxable * tax_rate


def build_project_cashflows(params: Dict) -> tuple[list[dict], float, float]:
    years = params["project_life_years"]
    total_capex = params["total_capex_usd_m"] * 1e6
    debt_ratio = params["debt_ratio"]
    total_debt = total_capex * debt_ratio
    equity = total_capex - total_debt
    blended = _blended_cost_of_debt(params)

    debt_sched = _debt_service_schedule(params, total_debt, years)
    rows = []
    for y in range(1, years + 1):
        prod_mwh = _production_mwh(params, y)
        rev = _revenue_usd(params, y, prod_mwh)
        opex = _opex_usd(params, prod_mwh)
        ebitda = rev - opex
        # Non-cash items ignored for simplicity; EBIT ~ EBITDA here
        interest = debt_sched[y - 1]["interest"]
        principal = debt_sched[y - 1]["principal"]
        ds = debt_sched[y - 1]["debt_service"]
        tax = _tax_calc(params, ebitda, interest, y)
        cfads = ebitda - tax  # before debt service
        dscr = (cfads / ds) if ds > 1e-9 else None

        # Risk cover costs
        ida_cost = 0.0
        if params["use_ida_prg"]:
            # 0.75% of last 9 months revenue (approx 75% of year revenue)
            ida_cost = 0.0075 * (rev * 0.75)

        equity_cf = ebitda - tax - ds - ida_cost
        project_cf = (
            ebitda - tax - ida_cost
        ) - 0.0  # before equity/debt financing injections

        # DSRA funding at year 1, release at end of amortization
        dsra_flow = 0.0
        if params["use_dsra"]:
            if y == 1:
                dsra_flow = -(params["dsra_months"] / 12.0) * ds  # fund
            if y == (params["grace_years"] + params["tenor_years"]):
                dsra_flow = +(params["dsra_months"] / 12.0) * ds  # release
        equity_cf += dsra_flow
        project_cf += dsra_flow

        rows.append(
            {
                "year": y,
                "prod_mwh": prod_mwh,
                "revenue_usd": rev,
                "opex_usd": opex,
                "ebitda_usd": ebitda,
                "interest_usd": interest,
                "principal_usd": principal,
                "debt_service_usd": ds,
                "tax_usd": tax,
                "ida_cost_usd": ida_cost,
                "equity_cf_usd": (
                    equity_cf if y > 1 else equity_cf - equity
                ),  # include equity outflow at t=0 within y=1
                "project_cf_usd": project_cf - total_capex if y == 1 else project_cf,
                "dscr": dscr,
            }
        )

    return rows, total_debt, blended


def wacc_from_terms(
    equity_cost: float, cost_of_debt: float, debt_ratio: float, tax_rate: float
) -> float:
    e = 1.0 - debt_ratio
    d = debt_ratio
    return e * equity_cost + d * cost_of_debt * (1.0 - tax_rate)


def llcr_plcr(
    rows: list[dict], opening_debt: float, discount_rate: float
) -> tuple[float | None, float | None]:
    # Using CFADS series during debt amort years only for LLCR
    cfads_series = []
    debt_years = 0
    for r in rows:
        ds = r["debt_service_usd"]
        cfads = r["ebitda_usd"] - r["tax_usd"]
        if ds > 0:
            cfads_series.append(cfads)
            debt_years += 1
    if not cfads_series:
        return None, None

    def _npv(rate, cfs):
        return sum(cf / ((1 + rate) ** i) for i, cf in enumerate(cfs, start=1))

    llcr = (
        _npv(discount_rate, cfads_series) / opening_debt if opening_debt > 0 else None
    )
    # PLCR uses entire project CFADS
    all_cfads = [r["ebitda_usd"] - r["tax_usd"] for r in rows]
    plcr = _npv(discount_rate, all_cfads) / opening_debt if opening_debt > 0 else None
    return llcr, plcr
