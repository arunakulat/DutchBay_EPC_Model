"""
Finance metrics façade.

Design:
- IRR/NPV implementations live only in dutchbay_v13.finance.irr (singleton).
- This module must not *define* irr/npv (no 'def irr' / 'def npv' here).
- It can re-export helper(s) used by tests/pipelines.
"""
from .irr import npv as npv, irr_bisection as irr_bisection  # re-exports only

__all__ = ["npv", "irr_bisection"]
