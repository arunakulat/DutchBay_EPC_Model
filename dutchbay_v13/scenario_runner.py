# dutchbay_v13/scenario_runner.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import json
import os
import sys

try:
    import yaml  # type: ignore
except Exception as e:  # pragma: no cover
    raise RuntimeError("PyYAML is required") from e

# Local, lightweight deps only
from .validate import validate_params  # env-aware via VALIDATION_MODE handled inside validate.py
from .adapters import run_irr  # core calc; debt layer applied inside adapters


# ---------------------------
# Helpers (pure & side-effect free)
# ---------------------------

@dataclass(frozen=True)
class RunResult:
    name: str
    summary: Dict[str, Any]
    annual: List[Dict[str, Any]]


def _iter_yaml_files(conf: Path) -> Iterable[Tuple[str, Path]]:
    """Yield (name, path) from a YAML file or a directory containing YAMLs."""
    if conf.is_dir():
        for p in sorted(conf.glob("*.y*ml")):
            yield (p.stem, p)
    else:
        yield (conf.stem, conf)


def _load_yaml(p: Path) -> Dict[str, Any]:
    with p.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config {p} must be a mapping at top level.")
    return data


def _dump_result_csv(dst: Path, rows: List[Dict[str, Any]]) -> None:
    """Write simple CSV with keys from the first row (stable order)."""
    if not rows:
        dst.write_text("", encoding="utf-8")
        return
    headers = list(rows[0].keys())
    lines = [",".join(headers)]
    for r in rows:
        line = ",".join(str(r.get(h, "")) for h in headers)
        lines.append(line)
    dst.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _dump_result_jsonl(dst: Path, rows: List[Dict[str, Any]]) -> None:
    with dst.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def _write_outputs(
    outdir: Path,
    base_name: str,
    fmt: str,
    summary: Dict[str, Any],
    annual: List[Dict[str, Any]],
) -> Tuple[Path | None, Path | None]:
    """Write result files; return (summary_path, annual_path)."""
    outdir.mkdir(parents=True, exist_ok=True)
    suffix = {"csv": ".csv", "jsonl": ".jsonl"}[fmt]

    # Summary one-liner
    sum_path = outdir / f"{base_name}_results{suffix}"
    if fmt == "csv":
        _dump_result_csv(sum_path, [summary])
    else:
        _dump_result_jsonl(sum_path, [summary])

    # Optional per-year
    ann_path = outdir / f"{base_name}_annual{suffix}"
    if annual:
        if fmt == "csv":
            _dump_result_csv(ann_path, annual)
        else:
            _dump_result_jsonl(ann_path, annual)
    else:
        ann_path = None

    return sum_path, ann_path


# ---------------------------
# Public runner
# ---------------------------

def run_dir(
    config: str | Path,
    outputs_dir: Path,
    *,
    mode: str = "irr",
    fmt: str = "csv",
    save_annual: bool = False,
) -> int:
    """
    Execute a single YAML or all YAMLs in a directory.

    Parameters
    ----------
    config : str|Path
        Path to YAML (or directory of YAMLs). If empty string, falls back to CWD 'full_model_variables_updated.yaml'.
    outputs_dir : Path
        Where to write outputs (created if missing).
    mode : str
        Currently supports 'irr' (others may be wired separately).
    fmt : str
        'csv' or 'jsonl'.
    save_annual : bool
        If True, write per-year rows.

    Returns
    -------
    int
        0 on success, non-zero on error (strict mode may raise SystemExit earlier).
    """
    if fmt not in ("csv", "jsonl"):
        raise ValueError("fmt must be 'csv' or 'jsonl'")

    if not config:
        conf_path = Path("full_model_variables_updated.yaml").resolve()
    else:
        conf_path = Path(config).resolve()

    outputs_dir = outputs_dir.resolve()
    outputs_dir.mkdir(parents=True, exist_ok=True)

    if mode != "irr":
        # Keep runner focused; other modes have their own drivers
        raise NotImplementedError(f"Mode '{mode}' is not implemented in scenario_runner.run_dir")

    results: List[RunResult] = []
    for name, path in _iter_yaml_files(conf_path):
        params = _load_yaml(path)

        # Validate (env-aware inside validate_params)
        # where=... is used only for error context
        validate_params(params, where=name)

        # Run model
        summary = run_irr(params)
        if not isinstance(summary, dict):
            raise ValueError(f"run_irr returned non-mapping for {name}")

        # Normalize outputs
        ann = summary.get("annual") if isinstance(summary.get("annual"), list) else []
        # Keep summary flat for CSV: remove heavy lists
        flat_summary = {k: v for k, v in summary.items() if k != "annual"}
        # Ensure a few canonical keys exist
        flat_summary.setdefault("name", name)
        flat_summary.setdefault("equity_irr", None)
        flat_summary.setdefault("project_irr", None)
        flat_summary.setdefault("npv_12", None)
        flat_summary.setdefault("dscr_min", None)
        flat_summary.setdefault("balloon_remaining", summary.get("balloon_remaining"))

        # Write
        base = f"scenario_{name}"
        _write_outputs(outputs_dir, base, fmt, flat_summary, ann if save_annual else [])

        results.append(RunResult(name=name, summary=flat_summary, annual=ann if save_annual else []))

    # Print a tiny banner if a single run (keeps your CLI UX)
    if len(results) == 1:
        r = results[0].summary
        print("\n--- IRR / NPV / DSCR RESULTS ---")
        print(f"Equity IRR:  {float(r.get('equity_irr') or 0.0)*100:5.2f} %")
        print(f"Project IRR: {float(r.get('project_irr') or 0.0)*100:5.2f} %")
        # NPV placeholder or computed upstream
        npv_val = r.get("npv_12")
        try:
            npv_str = f"{float(npv_val):.2f} Million"
        except Exception:
            npv_str = str(npv_val)
        print(f"NPV @ 12%:   {npv_str}")

    return 0


__all__ = ["run_dir"]

