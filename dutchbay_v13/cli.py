<<<<<<< Updated upstream
import argparse
import yaml
from dutchbay_v13.adapters import run_irr_demo
=======
from __future__ import annotations
import argparse
import json
from .scenario_runner import run_single_scenario, load_config
>>>>>>> Stashed changes


def main():
<<<<<<< Updated upstream
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=str, required=True)
    parser.add_argument('--mode', type=str, required=True)
    args = parser.parse_args()
=======
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--mode", required=True, choices=["irr"])
    ap.add_argument("--format", choices=["text", "json", "jsonl"], default="text")
    args = ap.parse_args()
>>>>>>> Stashed changes

    with open(args.config, 'r') as f:
        cfg = yaml.safe_load(f)

    if args.mode == "irr":
<<<<<<< Updated upstream
        print("Dispatching mode irr -> dutchbay_v13.adapters::run_irr_demo")
        run_irr_demo(cfg)
    else:
        print(f"Unknown mode: {args.mode}")
=======
        result = run_single_scenario(cfg)
        if args.format in ("json", "jsonl"):
            print(json.dumps(result))
        else:
            # pretty text block similar to user's log
            print("\n--- IRR / NPV / DSCR RESULTS ---")
            print(f"Equity IRR:  {result['equity_irr_pct']:.2f} %")
            print(f"Project IRR: {result['project_irr_pct']:.2f} %")
            print(f"NPV @ 12%:   {result['npv_12_musd']:.2f} Million USD")
            print(f"Min DSCR:    {result['min_dscr']:.2f}")
            print(f"Avg DSCR:    {result['avg_dscr']:.2f}")
            if result.get("llcr") is not None:
                print(f"LLCR:        {result['llcr']:.2f}")
            if result.get("plcr") is not None:
                print(f"PLCR:        {result['plcr']:.2f}")
            if result.get("wacc_pct") is not None:
                print(f"WACC:        {result['wacc_pct']:.2f} %")
            print("-------------------------------\n")
>>>>>>> Stashed changes


if __name__ == "__main__":
    main()
