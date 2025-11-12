# dutchbay_v13/core.py
"""
Thin legacy facade expected by older tests. Use adapters.run_irr under the hood.
"""

from __future__ import annotations
from typing import Dict, Any, Iterable, List

from .adapters import run_irr

def build_financial_model(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Minimal adapter: returns the summary dict produced by run_irr. If `params`
    does not include an `annual` CFADS stream, we fabricate zeros over project life.
    """
    annual: Iterable[Dict[str, float]] | None = params.get("annual")
    if not annual:
        lifetime = int(params.get("project", {}).get("timeline", {}).get("lifetime_years", 25))
        annual = [{"year": float(i + 1), "cfads_usd": 0.0} for i in range(lifetime)]
    return run_irr(params, list(annual))  # returns a mapping

    