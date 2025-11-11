#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .validate import load_params_from_file
from .adapters import run_irr


@dataclass
class RunResult:
    summary: Dict[str, Any]
    summary_path: Optional[Path] = None
    results_path: Optional[Path] = None


def _ts() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _write_outputs(
    config_path: Path,
    outputs_dir: Path,
    summary: Dict[str, Any],
    *,
    fmt: str = "csv",
    save_annual: bool = False,
) -> RunResult:
    outputs_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(config_path).stem

    # summary.json
    summary_path = outputs_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    results_path: Optional[Path] = None
    annual_rows: List[Dict[str, Any]] = list(summary.get("annual") or [])
    if save_annual:
        if fmt == "csv":
            results_path = outputs_dir / f"{stem}_results_{_ts()}.csv"
            preferred = ["year", "revenue_usd", "cfads_usd", "equity_cf", "debt_service"]
            keys = list({k for r in annual_rows for k in r.keys()})
            ordered = [k for k in preferred if k in keys] + [k for k in keys if k not in preferred]
            if not ordered:
                ordered = ["year", "cfads_usd", "equity_cf"]
            with results_path.open("w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=ordered)
                w.writeheader()
                for row in annual_rows:
                    w.writerow({k: row.get(k) for k in ordered})
        elif fmt == "jsonl":
            results_path = outputs_dir / f"{stem}_results_{_ts()}.jsonl"
            with results_path.open("w", encoding="utf-8") as f:
                for row in annual_rows:
                    f.write(json.dumps(row) + "\n")

    return RunResult(summary=summary, summary_path=summary_path, results_path=results_path)


def _synthesize_annual_relaxed(params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Minimal placeholder CFADS stream for relaxed mode only.
    Goal: keep IRR calculable when analysts haven't provided `annual` yet.
    This is *not* used in strict mode.
    """
    proj = params.get("project", {}) or {}
    tl = (proj.get("timeline") or {})
    years = int(tl.get("lifetime_years") or 25)

    capex = params.get("capex", {}) or {}
    cap_total = capex.get("usd_total")
    if cap_total is None:
        cap_per_mw = float(capex.get("usd_per_mw") or 1_000_000.0)
        cap = float(proj.get("capacity_mw") or 1.0)
        cap_total = cap_per_mw * cap
    cap_total = float(cap_total)

    # Tiny positive CFADS so IRR is defined; deliberately conservative.
    # ~2% of CAPEX per year as placeholder.
    cfads_year = max(cap_total * 0.02, 1_000_000.0)
    return [{"year": i + 1, "cfads_usd": cfads_year} for i in range(years)]


def run_dir(
    config_path: Path | str,
    outputs_dir: Path,
    *,
    mode: str = "irr",
    fmt: str = "csv",
    save_annual: bool = False,
    require_annual: bool = False,
) -> RunResult:
    outputs_dir.mkdir(parents=True, exist_ok=True)

    params: Dict[str, Any] = load_params_from_file(Path(config_path))
    mode_env = (os.environ.get("VALIDATION_MODE") or "relaxed").strip().lower()
    has_annual = bool(params.get("annual"))

    if (require_annual or mode_env == "strict") and not has_annual:
        raise SystemExit("Strict run requires explicit 'annual' CFADS in config (no placeholders).")

    annual: List[Dict[str, Any]] = list(params.get("annual") or [])
    if not annual and mode_env != "strict":
        annual = _synthesize_annual_relaxed(params)

    if mode == "irr":
        summary = run_irr(params, annual)
    else:
        raise SystemExit(f"Unknown mode: {mode}")

    return _write_outputs(Path(config_path), outputs_dir, summary, fmt=fmt, save_annual=save_annual)


__all__ = ["RunResult", "run_dir"]

