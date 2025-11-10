from __future__ import annotations
from typing import Dict, Any
from dataclasses import asdict
import pandas as pd
from .types import Params, DebtTerms
from .finance.cashflow import build as build_financials

def _coerce_params(d: Dict[str, Any]) -> Params:
    return Params(**{**Params().__dict__, **d})

def _default_debt() -> DebtTerms:
    return DebtTerms()

def build_financial_model(params: Dict[str, Any]) -> Dict[str, Any]:
    p = _coerce_params(params)
    debt = _coerce_debt(params.get('debt')) if isinstance(params, dict) and 'debt' in params else _default_debt()
    rows, eq_irr, prj_irr, npv_12, min_dscr, avg_dscr = build_financials(p, debt)
    df = pd.DataFrame([asdict(r) for r in rows])
    out: Dict[str, Any] = {
        "equity_irr": eq_irr,
        "project_irr": prj_irr,
        "npv_12pct": npv_12,
        "min_dscr": float(min_dscr),
        "avg_dscr": float(avg_dscr),
        "year1_dscr": float(rows[0].dscr) if rows[0].dscr is not None else float("inf"),
        "annual_data": df,
    }
    return out

def _coerce_debt(d: dict | None) -> DebtTerms:
    base = DebtTerms().__dict__.copy()
    for k, v in (d or {}).items():
        if k in base:
            base[k] = float(v) if isinstance(base[k], (int, float)) else v
    # cast ints
    base["tenor_years"] = int(round(base["tenor_years"]))
    base["grace_years"] = int(round(base["grace_years"]))
    return DebtTerms(**base)
