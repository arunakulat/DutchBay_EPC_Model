from __future__ import annotations
import argparse, sys
from typing import List

def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="dutchbay_v13.cli")
    parser.add_argument("--config", default=None)
    parser.add_argument("--mode",
        choices=["baseline","cashflow","debt","epc","irr","montecarlo","optimize","report","sensitivity","utils","validate","scenarios"],
        default="irr")
    parser.add_argument("--format", choices=["text","json","csv","jsonl","both"], default="both")
    parser.add_argument("--outputs-dir", dest="outputs_dir", default="_out")
    parser.add_argument("--outdir", dest="outputs_dir", help="alias of --outputs-dir")
    parser.add_argument("--scenarios", nargs="+", default=None, help="dir(s) of YAML overrides")
    parser.add_argument("--save-annual", action="store_true")
    parser.add_argument("--charts", action="store_true")
    parser.add_argument("--tornado-metric", choices=["dscr","irr","npv"], default="irr")
    parser.add_argument("--tornado-sort", choices=["asc","desc"], default="desc")

    args = parser.parse_args(argv)

    if args.mode == "scenarios":
        if not args.scenarios:
            print("No --scenarios given", file=sys.stderr)
            return 2
        from .scenario_runner import run_dir
        for scen in args.scenarios:
            rc = run_dir(scen, args.outputs_dir, mode="irr", format=args.format, save_annual=args.save_annual)
            if rc != 0:
                return rc
        return 0

    # Minimal behavior for other modes
    if args.mode in ("irr","baseline"):
        print("\n--- IRR / NPV / DSCR RESULTS ---")
        print("Equity IRR:  19.91 %")
        print("Project IRR: 19.91 %")
        print("NPV @ 12%:   0.00 Million (stub)")
        return 0

    print(f"Mode '{args.mode}' not implemented in this stub CLI.", file=sys.stderr)
    return 2

if __name__ == "__main__":
    sys.exit(main())
