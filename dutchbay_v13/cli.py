from __future__ import annotations

import argparse
import json
from typing import Any, Dict, Sequence

from .scenario_runner import load_config, run_single_scenario
from .finance.metrics import npv


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="dutchbay_v13.cli")
    p.add_argument("--config", "-c", default="inputs/full_model_variables_updated.yaml")
    p.add_argument("--mode", "-m", default="irr", choices=["irr"])
    p.add_argument("--format", "-f", default="text", choices=["text", "json"])
    return p.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    cfg = load_config(args.config)
    res = run_single_scenario(cfg, mode=args.mode)

    out: Dict[str, Any] = dict(res)

    for k in ("equity_irr", "project_irr", "wacc"):
        if k in out and f"{k}_pct" not in out:
            try:
                out[f"{k}_pct"] = float(out[k]) * 100.0
            except Exception:
                pass

    if "dscr_avg" in out and "avg_dscr" not in out:
        out["avg_dscr"] = out["dscr_avg"]

    cfs = cfg.get("cashflows") or [-100.0, 30.0, 30.0, 30.0, 30.0]
    try:
        out["npv_12_musd"] = npv(cfs, rate=0.12) / 1_000_000.0
    except Exception:
        out["npv_12_musd"] = 0.0

    if args.format == "json":
        print(json.dumps(out))
        return

    print("\n--- IRR / NPV / DSCR RESULTS ---")
    if (eq := out.get("equity_irr_pct")) is not None:
        print(f"Equity IRR:  {eq:.2f} %")
    if (pj := out.get("project_irr_pct")) is not None:
        print(f"Project IRR: {pj:.2f} %")


if __name__ == "__main__":
    main()
