from __future__ import annotations
from typing import Dict, Any

# Parameter schema: units, type, min/max ranges, and description.
SCHEMA: Dict[str, Dict[str, Any]] = {
    "total_capex":       {"unit": "USD million", "type": "float", "min": 50.0,  "max": 500.0, "desc": "Total project CAPEX"},
    "project_life_years":{"unit": "years",       "type": "int",   "min": 10,    "max": 40,    "desc": "Model horizon"},
    "nameplate_mw":      {"unit": "MW",          "type": "float", "min": 10.0,  "max": 1000.0,"desc": "Installed capacity"},
    "cf_p50":            {"unit": "fraction",    "type": "float", "min": 0.20,  "max": 0.60,  "desc": "Net capacity factor (P50)"},
    "yearly_degradation":{"unit": "fraction",    "type": "float", "min": 0.00,  "max": 0.03,  "desc": "Annual energy degradation"},
    "hours_per_year":    {"unit": "hours",       "type": "float", "min": 7000,  "max": 9000,  "desc": "Operational hours per year"},
    "tariff_lkr_kwh":    {"unit": "LKR/kWh",     "type": "float", "min": 10.0,  "max": 200.0, "desc": "Feed-in tariff"},
    "fx_initial":        {"unit": "LKR/USD",     "type": "float", "min": 100.0, "max": 1000.0,"desc": "Initial FX rate (LKR per USD)"},
    "fx_depr":           {"unit": "fraction",    "type": "float", "min": 0.00,  "max": 0.20,  "desc": "Annual FX depreciation"},
    "opex_usd_mwh":      {"unit": "USD/MWh",     "type": "float", "min": 3.0,   "max": 50.0,  "desc": "Operational expenditure"},
    "opex_esc_usd":      {"unit": "fraction",    "type": "float", "min": 0.00,  "max": 0.15,  "desc": "USD OPEX escalation"},
    "opex_esc_lkr":      {"unit": "fraction",    "type": "float", "min": 0.00,  "max": 0.20,  "desc": "LKR OPEX escalation"},
    "opex_split_usd":    {"unit": "fraction",    "type": "float", "min": 0.00,  "max": 1.00,  "desc": "Share of OPEX in USD"},
    "opex_split_lkr":    {"unit": "fraction",    "type": "float", "min": 0.00,  "max": 1.00,  "desc": "Share of OPEX in LKR"},
    "sscl_rate":         {"unit": "fraction",    "type": "float", "min": 0.00,  "max": 0.10,  "desc": "Surcharge/levy rate"},
    "tax_rate":          {"unit": "fraction",    "type": "float", "min": 0.00,  "max": 0.50,  "desc": "Corporate tax rate"},
    "discount_rate":     {"unit": "fraction",    "type": "float", "min": 0.00,  "max": 0.50,  "desc": "NPV discount rate"},
}

# Composite constraints evaluated after scalar checks.

COMPOSITE_CONSTRAINTS = [
    {
        "name": "tariff_usd_guardrail",
        "check": lambda p: 0.05 <= (p.get("tariff_lkr_kwh", 20.36) / max(1.0, p.get("fx_initial", 300.0))) <= 0.25,
        "message": "Tariff in USD/kWh must be in [0.05, 0.25]; computed as tariff_lkr_kwh / fx_initial.",
    },
    {
        "name": "fx_high_tariff_min",
        "check": lambda p: (p.get("fx_depr", 0.03) <= 0.10) or ((p.get("tariff_lkr_kwh", 20.36) / max(1.0, p.get("fx_initial", 300.0))) >= 0.07),
        "message": "If fx_depr > 0.10 then USD tariff must be ≥ 0.07 (7¢/kWh).",
    },

    {
        "name": "opex_splits_sum_to_one",
        "check": lambda p: abs((p.get("opex_split_usd", 0.30) + p.get("opex_split_lkr", 0.70)) - 1.0) <= 0.05,
        "message": "opex_split_usd + opex_split_lkr must sum to 1.0 (±0.05 tolerance)",
    },
]

# DebtTerms schema for YAML-based overrides
DEBT_SCHEMA: Dict[str, Dict[str, Any]] = {
    "debt_ratio":        {"unit": "fraction", "type": "float", "min": 0.40, "max": 0.95, "desc": "Debt as % of CAPEX"},
    "usd_debt_ratio":    {"unit": "fraction", "type": "float", "min": 0.00, "max": 1.00, "desc": "Share of debt in USD"},
    "usd_dfi_pct":       {"unit": "fraction", "type": "float", "min": 0.00, "max": 1.00, "desc": "Share of USD debt at DFI rate"},
    "usd_dfi_rate":      {"unit": "rate/yr",  "type": "float", "min": 0.00, "max": 0.20, "desc": "USD DFI interest rate"},
    "usd_mkt_rate":      {"unit": "rate/yr",  "type": "float", "min": 0.00, "max": 0.25, "desc": "USD market interest rate"},
    "lkr_rate":          {"unit": "rate/yr",  "type": "float", "min": 0.00, "max": 0.40, "desc": "LKR nominal interest rate"},
    "tenor_years":       {"unit": "years",    "type": "int",   "min": 5,    "max": 30,   "desc": "Debt tenor"},
    "grace_years":       {"unit": "years",    "type": "int",   "min": 0,    "max": 5,    "desc": "Interest-only years"},
    "principal_pct_1_4": {"unit": "fraction", "type": "float", "min": 0.00, "max": 1.00, "desc": "Principal % in first 4 amort years"},
    "principal_pct_5_on":{"unit": "fraction", "type": "float", "min": 0.00, "max": 1.00, "desc": "Principal % thereafter"},
}


SCHEMA.update({
    "base_cost_usd": {"min": 1.0, "max": 1e10, "units": "USD", "desc": "EPC base cost in USD"},
    "freight_pct": {"min": 0.0, "max": 1.0, "units": "fraction", "desc": "Freight as a fraction of base EPC"},
    "contingency_pct": {"min": 0.0, "max": 1.0, "units": "fraction", "desc": "Contingency as a fraction of subtotal"},
    "fx_rate": {"min": 0.0001, "max": 1e6, "units": "LCY/USD", "desc": "FX rate (local currency per USD)"},
})
