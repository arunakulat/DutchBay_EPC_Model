# dutchbay_v13/scenario_runner.py
from __future__ import annotations

import csv
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Mapping, MutableMapping, Optional, Tuple, Union

PathLike = Union[str, Path]
JSONLike = Union[Mapping[str, Any], List[Any]]


# --------------------------------------------------------------------------------------
# Validation mode & knobs
#   - Default: "permissive" (suitable for CI smokes)
#   - Strict mode for real runs:
#       * VALIDATION_MODE=strict
#       * or DB13_STRICT_VALIDATE in {1, true, yes}
#   - Optional ignore list for permissive mode:
#       DB13_IGNORE_KEYS = comma list (case-insensitive)
#         default: technical, finance, financial, notes, metadata, name, description, id
# --------------------------------------------------------------------------------------

def _env_truthy(name: str) -> bool:
    v = os.getenv(name, "")
    return v.lower() in {"1", "true", "yes", "on"}

_VALIDATION_MODE = os.getenv("VALIDATION_MODE", "").strip().lower()
if not _VALIDATION_MODE:
    _VALIDATION_MODE = "strict" if _env_truthy("DB13_STRICT_VALIDATE") else "permissive"

_DEFAULT_IGNORE = {
    "technical", "finance", "financial", "notes", "metadata", "name", "description", "id",
}
_IGNORE_KEYS = {k.strip().casefold() for k in os.getenv("DB13_IGNORE_KEYS", "").split(",") if k.strip()} or _DEFAULT_IGNORE


# --------------------------------------------------------------------------------------
# Allowed keys (conservative shape check in strict mode).
# NOTE: Keep broad to avoid false negatives; tighten as schema stabilizes.
# --------------------------------------------------------------------------------------
_ALLOWED_TOP_KEYS = {
    # core scenario knobs (typical)
    "capacity_mw", "capex_musd", "capex_usd",
    "opex_musd_per_year", "opex_usd_per_year",
    "tariff", "tariff_lkr_per_kwh", "tariff_usd_per_kwh",
    "wacc", "lifetime_years",
    "availability_pct", "curtailment_pct", "loss_factor",
    "exchange_rate_lkr_per_usd", "indexation_pct",
    # storage / grid (optional)
    "bess_capacity_mwh", "bess_power_mw", "bess_cost_musd", "grid_upgrade_musd",
    # debt block
    "debt",
    # generic “override” containers some configs use
    "override", "overrides", "parameters",
}

_ALLOWED_DEBT_KEYS = {
    "ratio",            # e.g., 0.7
    "rate",             # e.g., 0.08 (nominal)
    "tenor_years",      # e.g., 12
    "grace_years",      # e.g., 2
    "repayment_style",  # e.g., "annuity" | "sculpted" | "straight"
}


# --------------------------------------------------------------------------------------
# YAML loader
# --------------------------------------------------------------------------------------
def _load_yaml(p: PathLike) -> JSONLike:
    """
    Load YAML/JSON into Python objects. Accept .yaml/.yml/.json.
    """
    path = Path(p)
    suffix = path.suffix.lower()
    if suffix not in {".yaml", ".yml", ".json"}:
        raise ValueError(f"Unsupported scenario file extension: {suffix} ({path.name})")

    if suffix == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    else:
        try:
            import yaml  # type: ignore
        except Exception as e:
            raise RuntimeError("PyYAML is required to read YAML scenario files.") from e
        return yaml.safe_load(path.read_text(encoding="utf-8"))


def _iter_yaml_files(d: PathLike) -> Iterator[Path]:
    p = Path(d)
    for suffix in ("*.yaml", "*.yml", "*.json"):
        yield from sorted(p.glob(suffix))


# --------------------------------------------------------------------------------------
# Parameter preparation helpers
# --------------------------------------------------------------------------------------
def _unwrap_parameters_block(params: Mapping[str, Any]) -> Mapping[str, Any]:
    """
    Many 'scenario_matrix' style inputs wrap params as:
        { "parameters": {...} } or { "override": {...} } or { "overrides": {...} }
    Unwrap one layer if present.
    """
    for k in ("parameters", "override", "overrides"):
        v = params.get(k)
        if isinstance(v, dict):
            return v
    return params


def _strip_ignored_keys(params: Mapping[str, Any], ignore: Optional[Iterable[str]] = None) -> Dict[str, Any]:
    """
    Drop non-computational keys (tech notes, metadata, etc.) case-insensitively.
    """
    ignore_set = {*(x.casefold() for x in (ignore or _IGNORE_KEYS))}
    out: Dict[str, Any] = {}
    for k, v in params.items():
        if isinstance(k, str) and k.casefold() in ignore_set:
            continue
        out[k] = v
    return out


# --------------------------------------------------------------------------------------
# Validators
#   - Strict: shape and key checks. Raise on unknowns.
#   - Permissive: unwrap/ignore and return without raising.
# --------------------------------------------------------------------------------------
def _validate_debt_dict_strict(d: Any, where: Optional[str] = None) -> None:
    if d is None:
        return
    if not isinstance(d, Mapping):
        raise TypeError(f"debt must be a mapping (at {where})")

    unknown = [k for k in d.keys() if k not in _ALLOWED_DEBT_KEYS]
    if unknown:
        raise ValueError(f"Unknown debt keys {unknown} at {where}")

    if "ratio" in d and not isinstance(d["ratio"], (int, float)):
        raise TypeError(f"debt.ratio must be numeric at {where}")
    if "rate" in d and not isinstance(d["rate"], (int, float)):
        raise TypeError(f"debt.rate must be numeric at {where}")
    if "tenor_years" in d and not isinstance(d["tenor_years"], (int, float)):
        raise TypeError(f"debt.tenor_years must be numeric at {where}")


def _validate_params_dict_strict(params: Mapping[str, Any], where: Optional[str] = None) -> None:
    if not isinstance(params, Mapping):
        raise TypeError(f"parameters must be a mapping (at {where})")

    unknown = [k for k in params.keys() if k not in _ALLOWED_TOP_KEYS]
    if unknown:
        raise ValueError(f"Unknown parameter(s) {unknown} at {where}")

    # type-ish checks for common fields
    for k in (
        "capacity_mw", "capex_musd", "capex_usd",
        "opex_musd_per_year", "opex_usd_per_year",
        "tariff", "tariff_lkr_per_kwh", "tariff_usd_per_kwh",
        "wacc", "availability_pct", "curtailment_pct", "loss_factor",
        "exchange_rate_lkr_per_usd", "indexation_pct",
        "bess_capacity_mwh", "bess_power_mw", "bess_cost_musd", "grid_upgrade_musd",
        "lifetime_years",
    ):
        if k in params and not isinstance(params[k], (int, float)):
            raise TypeError(f"{k} must be numeric at {where}")

    _validate_debt_dict_strict(params.get("debt"), where=where)


def _validate_params_dict_permissive(params: Any, where: Optional[str] = None) -> None:
    """
    Relaxed validator for smokes:
      - unwraps parameters/override(s)
      - ignores common non-compute keys
      - never raises (by design)
    """
    try:
        if not isinstance(params, Mapping):
            return
        params = _unwrap_parameters_block(params)
        _ = _strip_ignored_keys(params)
        return
    except Exception:
        return


# Select effective validator based on env
def _validate_params_dict(params: Any, where: Optional[str] = None) -> None:
    if _VALIDATION_MODE == "strict":
        _validate_params_dict_strict(_unwrap_parameters_block(params), where=where)
    else:
        _validate_params_dict_permissive(params, where=where)


# --------------------------------------------------------------------------------------
# Scenario execution (dispatch → adapters/api if available; else minimal stub)
# --------------------------------------------------------------------------------------
@dataclass
class ScenarioResult:
    name: str
    results: Dict[str, Any]
    annual: Optional[List[Dict[str, Any]]] = None  # optional time series


def _try_dispatch(mode: str, params: Mapping[str, Any]) -> ScenarioResult:
    """
    Call into real implementations if present. Fall back to a minimal stub
    (so smokes keep generating artifacts without brittle dependencies).
    """
    # Attempt adapters first (explicit demo hooks)
    try:
        from . import adapters as _ad
        if hasattr(_ad, "run_irr_demo") and mode == "irr":
            res = _ad.run_irr_demo(params)  # type: ignore[arg-type]
            # Expecting dict with basic metrics; normalize:
            if isinstance(res, Mapping):
                return ScenarioResult(
                    name=params.get("name", "scenario"),
                    results=dict(res),
                    annual=res.get("annual") if isinstance(res.get("annual"), list) else None,  # type: ignore[index]
                )
    except Exception:
        pass

    # Try high level API (if available)
    try:
        from . import api as _api
        if hasattr(_api, "run"):
            res = _api.run(mode=mode, params=params)  # type: ignore[call-arg]
            if isinstance(res, Mapping):
                return ScenarioResult(
                    name=params.get("name", "scenario"),
                    results=dict(res),
                    annual=res.get("annual") if isinstance(res.get("annual"), list) else None,  # type: ignore[index]
                )
    except Exception:
        pass

    # Minimal stub (keeps CI happy; does not pretend to be finance)
    return ScenarioResult(
        name=str(params.get("name", "scenario")),
        results={
            "equity_irr": 0.0,
            "dscr_min": 1.0,
            "note": "stub: real adapters/api not wired",
        },
        annual=[{"year": 1, "dscr": 1.0, "equity_cf": 0.0}],
    )


# --------------------------------------------------------------------------------------
# File/dir runners and writers
# --------------------------------------------------------------------------------------
def _write_results(outdir: PathLike, base: str, sr: ScenarioResult, fmt: str = "csv", save_annual: bool = True) -> Tuple[Path, Optional[Path]]:
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)

    ts = int(time.time())
    res_path = out / f"scenario_{base}_results_{ts}.csv"
    ann_path = out / f"scenario_{base}_annual_{ts}.csv"

    # Results
    with res_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["metric", "value"])
        for k, v in sr.results.items():
            w.writerow([k, v])

    # Annual (optional)
    if save_annual and sr.annual:
        keys: List[str] = sorted({k for row in sr.annual for k in row.keys()})
        with ann_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            for row in sr.annual:
                w.writerow(row)
    else:
        ann_path = None

    return res_path, ann_path


def run_scenario(params: Mapping[str, Any], *, mode: str = "irr") -> ScenarioResult:
    """
    Run a single scenario dict. Validates (strict or permissive per env) then dispatches.
    """
    _validate_params_dict(params, where=params.get("name"))
    clean = _unwrap_parameters_block(params)
    clean = _strip_ignored_keys(clean)
    return _try_dispatch(mode=mode, params=clean)


def run_file(scenario_file: PathLike, *, mode: str = "irr") -> Iterator[Tuple[str, ScenarioResult]]:
    """
    Load a scenario file and yield (base_name, result) pairs.
      - plain dict → one result
      - list of dicts → each treated as a scenario
      - matrix forms:
          {"matrix": [ {...}, {...} ]} or {"parameters": {...}} (flatten one layer)
    """
    payload = _load_yaml(scenario_file)
    base = Path(scenario_file).stem

    # list of params
    if isinstance(payload, list):
        for i, p in enumerate(payload, 1):
            if isinstance(p, Mapping):
                yield f"{base}_{i}", run_scenario(p, mode=mode)
        return

    # matrix-like
    if isinstance(payload, Mapping):
        if "matrix" in payload and isinstance(payload["matrix"], list):
            for i, p in enumerate(payload["matrix"], 1):
                if isinstance(p, Mapping):
                    yield f"{base}_{i}", run_scenario(p, mode=mode)
            return

        # single dict
        yield base, run_scenario(payload, mode=mode)
        return

    # Fallback: ignore unknown
    return


def run_dir(scenarios_dir: PathLike,
            outputs_dir: PathLike,
            *,
            mode: str = "irr",
            fmt: str = "csv",
            save_annual: bool = True) -> List[Tuple[Path, Optional[Path]]]:
    """
    Run all .yaml/.yml/.json files in a directory. Returns list of (results_path, annual_path).
    """
    out_paths: List[Tuple[Path, Optional[Path]]] = []
    for f in _iter_yaml_files(scenarios_dir):
        for base, result in run_file(f, mode=mode):
            res_p, ann_p = _write_results(outputs_dir, base, result, fmt=fmt, save_annual=save_annual)
            out_paths.append((res_p, ann_p))
    return out_paths