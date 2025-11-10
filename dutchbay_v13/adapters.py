from __future__ import annotations
import logging

from dutchbay_v13.finance.cashflow import build as build_financials
from dutchbay_v13.finance.debt import amortization_schedule
from dutchbay_v13.types import Params, DebtTerms

logger = logging.getLogger()
logging.basicConfig(level=logging.INFO)

def run_irr_demo(cfg: dict):
    try:
        logger.info("✅ YAML loaded with %d top-level blocks", len(cfg))
        logger.info(">>> Flattening grouped config dict")
        flat_cfg = {
            k: v for group in cfg.values() if isinstance(group, dict)
            for k, v in group.items()
        }

        for k, v in flat_cfg.items():
            if v is None:
                logger.warning("⚠️ Null or empty field in config: %s", k)

        if not flat_cfg.get("opex_usd_mwh"):
            comp = flat_cfg.get("opex_components", {})
            flat_cfg["opex_usd_mwh"] = round(sum(comp.values()), 2)
            logger.info("Computed opex_usd_mwh: %.2f", flat_cfg["opex_usd_mwh"])

        p_keys = Params.__annotations__.keys()
        d_keys = DebtTerms.__annotations__.keys()
        p_cfg = {k: v for k, v in flat_cfg.items() if k in p_keys}
        d_cfg = {k: v for k, v in flat_cfg.items() if k in d_keys}

        logger.info(">>> Splitting Params and DebtTerms")
        logger.info(">>> Constructing Params with %d fields", len(p_cfg))
        logger.info(">>> Constructing DebtTerms with %d fields", len(d_cfg))

        p = Params(**p_cfg)
        d = DebtTerms(**d_cfg)

        logger.info(">>> Generating front-loaded debt amortization schedule")
        total_debt = p.total_capex * d.debt_ratio
        debt_schedule = amortization_schedule(total_debt, d, p.project_life_years)
        logger.info(">>> Debt schedule created: %d years", len(debt_schedule))

        logger.info(">>> Running financial calculation")
        rows, equity_irr, project_irr, npv, min_dscr, avg_dscr = build_financials(p, d)

        print("\n--- IRR / NPV / DSCR RESULTS ---")
        print("Equity IRR: ", round(equity_irr * 100, 2), "%")
        print("Project IRR:", round(project_irr * 100, 2), "%")
        print("NPV @ 12%:  ", round(npv / 1_000_000, 2), "Million USD")
        print("Min DSCR:   ", round(min_dscr, 2))
        print("Avg DSCR:   ", round(avg_dscr, 2))
        print("-------------------------------\n")

    except Exception:
        import traceback
        logger.error("🚨 run_irr_demo crashed:")
        traceback.print_exc()
