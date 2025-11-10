from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple
import os, json, csv
from pathlib import Path

try:
    import yaml  # type: ignore
except Exception as e:  # pragma: no cover
    yaml = None

try:
    from .schema import SCHEMA, DEBT_SCHEMA  # type: ignore
except Exception:  # pragma: no cover
    SCHEMA = {}
    DEBT_SCHEMA = {}

def _validate_params_dict(params: Dict[str, Any], where: str = "params") -> Dict[str, Any]:
    out: Dict[str, Any] = dict(params or {})
    if not SCHEMA:
        return out
    for k, meta in SCHEMA.items():
        if k not in out:
            continue
        v = out[k]
        try:
            fv = float(v) if isinstance(v, str) else float(v)  # type: ignore[arg-type]
        except Exception:
            continue
        mn = meta.get("min")
        mx = meta.get("max")
        if mn is not None and mx is not None:
            if not (float(mn) <= fv <= float(mx)):
                raise ValueError(f"{where}: {k} out of range [{mn}, {mx}] got {fv}")
    return out

def _validate_debt_dict(debt: Dict[str, Any], where: str = "debt") -> Dict[str, Any]:
    out: Dict[str, Any] = dict(debt or {})
    if not DEBT_SCHEMA:
        return out
    for k, meta in DEBT_SCHEMA.items():
        if k not in out:
            continue
        v = out[k]
        try:
            fv = float(v) if isinstance(v, str) else float(v)  # type: ignore[arg-type]
        except Exception:
            continue
        mn = meta.get("min")
        mx = meta.get("max")
        if mn is not None and mx is not None:
            if not (float(mn) <= fv <= float(mx)):
                raise ValueError(f"{where}: {k} out of range [{mn}, {mx}] got {fv}")
    return out

def _iter_yaml_files(paths: Iterable[str]) -> List[Path]:
    out: List[Path] = []
    for p in paths:
        P = Path(p)
        if P.is_file() and P.suffix.lower() in {".yaml", ".yml"}:
            out.append(P)
        elif P.is_dir():
            out.extend(sorted(x for x in P.rglob("*.yml")))
            out.extend(sorted(x for x in P.rglob("*.yaml")))
    # dedupe while preserving order
    seen = set()
    uniq: List[Path] = []
    for f in out:
        if f not in seen:
            uniq.append(f)
            seen.add(f)
    return uniq

def _load_yaml(path: Path) -> Dict[str, Any]:
    if yaml is None:
        raise RuntimeError("PyYAML is required to load scenarios")
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def _run_model(params: Dict[str, Any]) -> Dict[str, Any]:
    """Run the financial model; if implementation is missing, return safe placeholders."""
    # Strip expected_metrics if present
    params = dict(params)
    params.pop("expected_metrics", None)
    try:
        # Preferred API
        from .core import build_financial_model  # type: ignore
        result = build_financial_model(params)
        if isinstance(result, dict):
            return result
        # gracefully coerce tuple returns if your API returns (df, proj_cf, eq_cf, cap, metrics)
        if isinstance(result, tuple) and len(result) >= 1 and isinstance(result[-1], dict):
            return result[-1]
    except Exception:
        pass
    # Fallback minimal metrics
    return {
        "project_irr": None,
        "equity_irr": None,
        "min_dscr": None,
        "llcr": None,
        "plcr": None,
    }

def run_scenario_matrix(config_paths: Iterable[str], outputs_dir: str, *, fmt: str = "csv", save_annual: bool = False) -> Tuple[int, int]:
    """Read YAMLs, validate ranges, run model, and write JSONL/CSV outputs.
    Returns (num_scenarios, num_written).
    """
    outs = Path(outputs_dir)
    outs.mkdir(parents=True, exist_ok=True)
    files = _iter_yaml_files(config_paths)
    rows: List[Dict[str, Any]] = []
    jsonl_lines = 0

    for f in files:
        data = _load_yaml(f)
        # Split top-level into params/debt/expected
        debt = _validate_debt_dict(data.get("debt") or {}, where=f"{f.name}:debt")
        params = {k: v for k, v in data.items() if k not in {"debt", "expected_metrics"}}
        params = _validate_params_dict(params, where=f"{f.name}:params")
        merged = dict(params)
        if debt:
            merged["debt"] = debt
        metrics = _run_model(merged)
        rec = {
            "scenario": f.stem,
            **{k: merged.get(k) for k in sorted(merged.keys())},
            **{k: metrics.get(k) for k in ["project_irr", "equity_irr", "min_dscr", "llcr", "plcr"] if k in metrics},
        }
        rows.append(rec)

    # Write JSONL
    if fmt in {"jsonl", "both"}:
        jpath = outs / "scenarios.jsonl"
        with jpath.open("w", encoding="utf-8") as jf:
            for r in rows:
                jf.write(json.dumps(r) + "\n")
                jsonl_lines += 1

    # Write CSV
    if fmt in {"csv", "both"} and rows:
        cpath = outs / "scenarios.csv"
        # union of keys across rows
        keys = []
        seen = set()
        for r in rows:
            for k in r.keys():
                if k not in seen:
                    keys.append(k)
                    seen.add(k)
        with cpath.open("w", encoding="utf-8", newline="") as cf:
            w = csv.DictWriter(cf, fieldnames=keys)
            w.writeheader()
            w.writerows(rows)

    return (len(files), len(rows))
