# dutchbay_v13/cli.py
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .scenario_runner import run_dir  # run_dir(config, out_dir, mode, fmt, save_annual=False, require_annual=False)


def _fmt_pct(x):
    return "n/a" if x is None else f"{100.0 * float(x):,.2f} %"


def _fmt_musd(x):
    try:
        return f"{float(x) / 1e6:,.2f} Million"
    except Exception:
        return "n/a"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="dutchbay_v13",
        description=(
            "DutchBay wind model CLI\n\n"
            "Typical usage:\n"
            "  python -m dutchbay_v13 --mode irr --config full_model_variables_updated.yaml --out _out\n\n"
            "Validation modes:\n"
            "  • --strict   -> VALIDATION_MODE=strict (unknown keys = error)\n"
            "  • --relaxed  -> VALIDATION_MODE unset (unknown keys allowed)\n\n"
            "Annual stream:\n"
            "  • --require-annual enforces an explicit 'annual' CFADS array in the input file.\n"
            "  • If omitted (relaxed), a placeholder flat-zero annual may be synthesized."
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--mode", choices=["irr"], default="irr", help="Computation mode (default: irr).")
    parser.add_argument("--config", required=True, help="Path to YAML config.")
    parser.add_argument("--out", default="_out", help="Output directory (default: _out).")
    parser.add_argument("--fmt", choices=["csv", "jsonl"], default="csv", help="Output format for results (default: csv).")
    parser.add_argument("--save-annual", action="store_true", help="Emit annual row outputs alongside summary.")
    parser.add_argument("--require-annual", action="store_true", help="Require explicit 'annual' CFADS in inputs (strict annual).")

    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--strict", action="store_true", help="Force strict validation (VALIDATION_MODE=strict).")
    mode_group.add_argument("--relaxed", action="store_true", help="Force relaxed validation (unset VALIDATION_MODE).")

    args = parser.parse_args(argv)

    # Wire VALIDATION_MODE according to flags
    if args.strict:
        os.environ["VALIDATION_MODE"] = "strict"
    elif args.relaxed:
        os.environ.pop("VALIDATION_MODE", None)
    # else: respect existing env

    config_path = Path(args.config)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Delegate
    res = run_dir(
        config_path,
        out_dir,
        mode=args.mode,
        fmt=args.fmt,
        save_annual=bool(args.save_annual),
        require_annual=bool(args.require_annual),
    )

    summary = res.summary  # dict
    print("\n--- IRR / NPV / DSCR RESULTS ---")
    print(f"Equity IRR:   {_fmt_pct(summary.get('equity_irr'))}")
    print(f"Project IRR:  {_fmt_pct(summary.get('project_irr'))}")
    print(f"NPV @ 12%:    {_fmt_musd(summary.get('npv_12'))}")

    if res.results_path:
        print(str(res.results_path))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

    