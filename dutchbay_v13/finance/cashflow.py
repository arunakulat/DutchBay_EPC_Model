from __future__ import annotations

from dutchbay_v13.types import AnnualRow, Params, DebtTerms
from dutchbay_v13.finance.debt import amortization_schedule


def build(
    p: Params, d: DebtTerms
) -> tuple[list[AnnualRow], float, float, float, float, float]:
    years = list(range(1, p.project_life_years + 1))
    total_debt = p.total_capex * d.debt_ratio
    schedule = amortization_schedule(total_debt, d, p.project_life_years)

    rows: list[AnnualRow] = []
    total_equity_fcf = 0.0
    total_project_fcf = 0.0
    npv = 0.0
    dscr_list = []

    for y in years:
        fx = p.fx_initial * ((1.0 + p.fx_depr) ** (y - 1))
        prod = _production(p, y)
        revenue_lkr = _revenue_lkr(p, prod)
        revenue_usd = revenue_lkr / fx
        opex = _opex_usd(p, y, prod, fx)
        sscl = revenue_usd * p.sscl_rate
        ebit = revenue_usd - opex - sscl

        debt_year = schedule[y - 1]
        interest = debt_year.interest
        principal = debt_year.principal

        ebt = ebit - interest
        tax = max(0.0, ebt * p.tax_rate)
        cfads = ebit - interest - tax
        equity_fcf = cfads - principal
        dscr = cfads / (interest + principal) if (interest + principal) > 0 else None

        npv += equity_fcf / ((1.0 + p.discount_rate) ** y)
        total_equity_fcf += equity_fcf
        total_project_fcf += cfads
        if dscr is not None:
            dscr_list.append(dscr)

        row = AnnualRow(
            year=y,
            fx_rate=fx,
            production_mwh=prod,
            revenue_usd=revenue_usd,
            opex_usd=opex,
            sscl_usd=sscl,
            ebit_usd=ebit,
            interest_usd=interest,
            principal_usd=principal,
            ebt_usd=ebt,
            tax_usd=tax,
            cfads_usd=cfads,
            equity_fcf_usd=equity_fcf,
            debt_service_usd=interest + principal,
            dscr=dscr,
        )
        rows.append(row)

    equity_irr = _irr([r.equity_fcf_usd for r in rows])
    project_irr = _irr([r.cfads_usd for r in rows])
    min_dscr = min(dscr_list) if dscr_list else 0.0
    avg_dscr = sum(dscr_list) / len(dscr_list) if dscr_list else 0.0

    return rows, equity_irr, project_irr, npv, min_dscr, avg_dscr


def _production(p: Params, year: int) -> float:
    return (
        p.cf_p50
        * p.nameplate_mw
        * p.hours_per_year
        * ((1.0 - p.yearly_degradation) ** (year - 1))
    )


def _revenue_lkr(p: Params, prod_mwh: float) -> float:
    return prod_mwh * 1_000 * p.tariff_lkr_kwh


def _opex_usd(p: Params, year: int, prod_mwh: float, fx: float) -> float:
    if p.opex_usd_mwh is None:
        raise ValueError("opex_usd_mwh must be set or computed before cashflow calc")
    usd_comp = (
        p.opex_usd_mwh * p.opex_split_usd * ((1.0 + p.opex_esc_usd) ** (year - 1))
    )
    lkr_comp = (
        p.opex_usd_mwh * p.opex_split_lkr * ((1.0 + p.opex_esc_lkr) ** (year - 1)) / fx
    )
    return usd_comp + lkr_comp


def _irr(cashflows: list[float]) -> float:
    from numpy_financial import irr as np_irr

    result = np_irr([-cashflows[0]] + cashflows[1:]) if cashflows else 0.0
    return float(result) if result else 0.0
