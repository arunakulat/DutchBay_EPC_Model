from __future__ import annotations
from pathlib import Path
from typing import Dict, Any

<<<<<<< Updated upstream
def _parse_yaml_fallback(text: str) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    for line in text.splitlines():
        if not line.strip() or line.strip().startswith("#") or ":" not in line:
            continue
        k, v = line.split(":", 1)
        k = k.strip(); v = v.strip().strip('"').strip("'")
        try:
            if v.lower() in ("true","false"):
                data[k] = (v.lower() == "true")
            elif "." in v or "e" in v.lower():
                data[k] = float(v)
            else:
                data[k] = int(v)
        except Exception:
            data[k] = v
    return data

def load_params(path: str | Path) -> Dict[str, Any]:
    p = Path(path)
    text = p.read_text(encoding="utf-8", errors="ignore")
    if p.suffix.lower() in (".yaml",".yml"):
        try:
            import yaml
            data = yaml.safe_load(text) or {}
        except Exception:
            data = _parse_yaml_fallback(text)
        return data
    elif p.suffix.lower() == ".json":
        import json
        return json.loads(text)
    else:
        raise ValueError(f"Unsupported params format: {p.suffix}")

def load_all_params(path: str | Path) -> tuple[dict, dict]:
    """Return (params_dict, debt_dict) from YAML/JSON.
    Accepts optional top-level 'debt' mapping.
    """
    d = load_params(path)
    debt = {}
    if isinstance(d, dict) and "debt" in d and isinstance(d["debt"], dict):
        debt = d.pop("debt")
    return d, debt
=======

def _flatten_grouped(cfg: Dict[str, Any]) -> Dict[str, Any]:
    flat = {}
    for k, v in cfg.items():
        if isinstance(v, dict):
            for kk, vv in v.items():
                flat[kk] = vv
        else:
            flat[k] = v
    return flat


def load_config(path: str | None) -> Tuple[Params, DebtTerms]:
    if path is None:
        path = "inputs/full_model_variables_updated.yaml"
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    flat = _flatten_grouped(cfg)
    # Map into dataclasses with robust defaults
    p = Params(
        total_capex=flat.get("total_capex", 155.0),
        project_life_years=flat.get("project_life_years", 20),
        nameplate_mw=flat.get("nameplate_mw", flat.get("nameplate", 150.0)),
        cf_p50=flat.get("capacity_factor", flat.get("cf_p50", 0.40)),
        yearly_degradation=flat.get("yearly_degradation", 0.006),
        hours_per_year=flat.get("hours_per_year", 8760.0),
        tariff_lkr_kwh=flat.get("tariff_lkr_per_kwh", 20.30),
        fx_initial=flat.get("fx_today_lkr_per_usd", 300.0),
        fx_depr=flat.get("fx_depr_pct", 0.03),
        opex_usd_mwh=flat.get("opex_usd_per_mwh", flat.get("opex_usd_mwh")),
        opex_split_usd=flat.get("opex_split_usd", 0.80),
        opex_esc_usd=flat.get("opex_esc_usd", 0.02),
        opex_esc_lkr=flat.get("opex_esc_lkr", 0.03),
    )
    d = DebtTerms(
        debt_ratio=flat.get("debt_ratio", 0.7),
        usd_debt_ratio=flat.get("usd_debt_ratio", 0.6),
        usd_dfi_pct=flat.get("usd_dfi_pct", 0.5),
        usd_mkt_rate=flat.get("usd_mkt_rate", 0.07),
        usd_dfi_rate=flat.get("usd_dfi_rate", 0.065),
        lkr_rate=flat.get("lkr_rate", 0.075),
        grace_years=flat.get("grace_years", 2),
        tenor_years=flat.get("tenor_years", 12),
        principal_pct_1_4=flat.get("principal_pct_1_4", 0.35),
        principal_pct_5_on=flat.get("principal_pct_5_on", 0.65),
    )
    return p, d
>>>>>>> Stashed changes
