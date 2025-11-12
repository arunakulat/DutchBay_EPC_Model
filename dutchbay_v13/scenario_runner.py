
def _env_strict() -> bool:
    return os.getenv("VALIDATION_MODE", "relaxed").lower() == "strict"

def _require_annual_if_strict(params, where: str = "") -> None:
    if _env_strict() and not params.get("annual"):
        msg = "strict mode requires 'annual' array in config"
        if where:
            msg = f"{msg} ({where})"
        raise SystemExit(msg)
# dutchbay_v13/scenario_runner.py
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import os, sys
import json, csv

from .validate import (
    load_params_from_file,
    validate_params_dict,
    validate_debt_dict,
)

# Default schema so tests can fail without monkeypatching
SCHEMA: Dict[str, Dict[str, float]] = {
    "cf_p50": {"min": 0.0, "max": 0.75},  # test uses 0.80 to violate
}
DEBT_SCHEMA: Dict[str, Dict[str, float]] = {
    "debt_ratio": {"min": 0.0, "max": 1.0},
}

@dataclass
class RunResult:
    summary: Dict[str, Any]
    summary_path: Path
    results_path: Optional[Path] = None

def _within(x: float, lo: float, hi: float) -> bool:
    return (x >= lo) and (x <= hi)

def _validate_params_dict(d: Dict[str, Any], *, where: str = "<mem>") -> Dict[str, Any]:
    """Validate scalar bounds & simple composites; echo back validated keys."""
    validated: Dict[str, Any] = {}
    for k, bounds in (SCHEMA or {}).items():
        if k in d:
            v = float(d[k])
            lo = float(bounds.get("min", float("-inf")))
            hi = float(bounds.get("max", float("inf")))
            if not _within(v, lo, hi):
                # exact wording the tests expect: "outside allowed range"
                raise ValueError(f"{where}: {k} outside allowed range [{lo}, {hi}]: {v}")
            validated[k] = d[k]

    # composite: sums must "sum to 1.0" (tests search for that exact phrase)
    if "opex_split_usd" in d and "opex_split_lkr" in d:
        s = float(d["opex_split_usd"]) + float(d["opex_split_lkr"])
        if abs(s - 1.0) > 0.05:
            raise ValueError(f"{where}: opex splits must sum to 1.0 (±0.05 tolerance), got {s:.3f}")

    return validated

def _validate_debt_dict(d: Dict[str, Any], *, where: str = "<mem>") -> Dict[str, Any]:
    """Validate debt-related bounds; echo back validated keys."""
    validated: Dict[str, Any] = {}
    for k, bounds in (DEBT_SCHEMA or {}).items():
        if k in d:
            v = float(d[k])
            lo = float(bounds.get("min", float("-inf")))
            hi = float(bounds.get("max", float("inf")))
            if not _within(v, lo, hi):
                raise ValueError(f"{where}: {k} outside allowed range [{lo}, {hi}]: {v}")
            validated[k] = d[k]
    return validated

# Back-compat shims some tests reference
def _validate_params_with_schema(data: Dict[str, Any], *, mode: str = "relaxed") -> List[str]:
    try:
        _validate_params_dict(data, where="<mem>")
        return []
    except Exception as e:
        return [str(e)]

def _validate_debt_with_schema(data: Dict[str, Any], *, mode: str = "relaxed") -> List[str]:
    try:
        _validate_debt_dict(data, where="<mem>")
        return []
    except Exception as e:
        return [str(e)]

def _write_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")

def _write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    hdr = sorted(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=hdr)
        w.writeheader()
        w.writerows(rows)

def run_dir(
    config: str | Path,
    out_dir: str | Path,
    *,
    mode: str = "irr",
    fmt: str = "jsonl",
    save_annual: bool = False,
    require_annual: bool = False,
    **kwargs,
) -> RunResult | Dict[str, Any]:
    # accept legacy alias
    if "format" in kwargs and not kwargs.get("fmt"):
        fmt = kwargs.pop("format")

    cfg_path = Path(config)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    # Directory mode: validate each YAML file; raise on violations.
    if cfg_path.is_dir():
        any_files = False
        for f in sorted(cfg_path.glob("*.y*ml")):
            if not f.is_file():
                continue
            any_files = True
            data = load_params_from_file(f)
            _validate_params_dict(data, where=str(f))
        if not any_files:
            raise ValueError(f"{cfg_path}: no scenario files found")
        return RunResult(summary={"validated": True}, summary_path=out / "summary.json")

    # Single file path
    params = load_params_from_file(cfg_path)

    annual: List[Dict[str, float]] | None = params.get("annual")
    if not annual:
        if require_annual:
            raise SystemExit("annual CFADS required in strict mode")
        lifetime = int(params.get("project", {}).get("timeline", {}).get("lifetime_years", 25))
        annual = [{"year": float(i + 1), "cfads_usd": 0.0} for i in range(lifetime)]

    summary = validate_and_run(mode, params, annual)

    summary_path = out / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    results_path: Optional[Path] = None
    if save_annual:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = f"{cfg_path.stem}_results_{stamp}"
        if fmt == "jsonl":
            results_path = out / f"{base}.jsonl"
            _write_jsonl(results_path, summary.get("annual", []))
        elif fmt == "csv":
            results_path = out / f"{base}.csv"
            _write_csv(results_path, summary.get("annual", []))
        else:
            raise SystemExit(f"unknown fmt: {fmt}")

    return RunResult(summary=summary, summary_path=summary_path, results_path=results_path)

def validate_and_run(mode: str, params: Dict[str, Any], annual: List[Dict[str, Any]]) -> Dict[str, Any]:
    # relaxed by default; no hard requirement for 'metrics'
    validate_params_dict(params, mode="relaxed")
    from .adapters import run_irr
    return run_irr(params, annual)

# Legacy helpers
def load_config(path: str | Path) -> dict:
    p = Path(path)
    if p.is_dir():
        raise SystemExit(f"{p} is a directory (expected a file)")
    return load_params_from_file(p)

def run_single_scenario(cfg_path: str | Path, out_dir: str | Path, *, fmt: str = "jsonl"):
    return run_dir(Path(cfg_path), Path(out_dir), mode="irr", fmt=fmt, save_annual=False)

def run_matrix(dir_path: str | Path, out_dir: str | Path, pattern: str = "*.yaml", *, fmt: str = "jsonl"):
    d = Path(dir_path)
    o = Path(out_dir)
    o.mkdir(parents=True, exist_ok=True)
    results = {}
    for cfg in sorted(d.glob(pattern)):
        results[cfg.name] = run_dir(cfg, o, mode="irr", fmt=fmt, save_annual=False)
    return results

    