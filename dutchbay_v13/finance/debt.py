from __future__ import annotations
from dataclasses import dataclass
from typing import List
from ..types import DebtTerms


@dataclass
class DebtYear:
    year: int
    opening: float
    interest: float
    principal: float
    closing: float
    debt_service: float


def blended_rate(debt: DebtTerms) -> float:
    usd = debt.usd_debt_ratio
    lkr = 1.0 - usd
    usd_rate = (
        debt.usd_dfi_pct * debt.usd_dfi_rate
        + (1.0 - debt.usd_dfi_pct) * debt.usd_mkt_rate
    )
    return usd * usd_rate + lkr * debt.lkr_rate


def amortization_schedule(
    total_debt: float, debt: DebtTerms, project_years: int
) -> List[DebtYear]:
    r = blended_rate(debt)
    years = project_years
    schedule: List[DebtYear] = []
    opening = total_debt

    start_amort = debt.grace_years + 1
    last_amort_year = min(debt.tenor_years, years)

    amort_years_total = max(0, last_amort_year - debt.grace_years)
    first_block = min(4, max(0, amort_years_total))
    second_block = max(0, amort_years_total - first_block)

    principal_first = total_debt * debt.principal_pct_1_4
    principal_second = total_debt * debt.principal_pct_5_on
    p1 = (principal_first / first_block) if first_block > 0 else 0.0
    p2 = (principal_second / second_block) if second_block > 0 else 0.0

    for y in range(1, years + 1):
        interest = opening * r
        principal = 0.0
        if start_amort <= y <= last_amort_year:
            if y < start_amort + first_block:
                principal = min(p1, opening)
            else:
                principal = min(p2, opening)
        closing = max(0.0, opening - principal)
        schedule.append(
            DebtYear(
                year=y,
                opening=opening,
                interest=interest,
                principal=principal,
                closing=closing,
                debt_service=interest + principal,
            )
        )
        opening = closing
    return schedule
